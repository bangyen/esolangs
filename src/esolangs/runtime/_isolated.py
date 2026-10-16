"""Execute in a disposable interpreter with a portable wall-clock deadline."""

from __future__ import annotations

import base64
import json
import os
import subprocess  # fixed Python worker; source travels over stdin.
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from itertools import chain, groupby, repeat
from queue import Empty, Full, Queue
from threading import Event, Thread
from time import monotonic, sleep
from typing import Any, TextIO, cast

from esolangs import exceptions
from esolangs.compressed import CompressedText
from esolangs.raster import Pixel, Raster, Rows
from esolangs.registry import resolve
from esolangs.runtime._program import Program
from esolangs.runtime._source import InputSource, ProgramSource, read_input
from esolangs.runtime._validate import check_timeout, check_whole
from esolangs.runtime.source_hints import with_hint
from esolangs.settings import DialectSettings, dialect_options, effective_settings

type _RasterRuns = tuple[tuple[int, tuple[tuple[int, Pixel], ...]], ...]


# Scale-3 raster JSON: 13,759,407 -> 18,621 bytes; four rows 5.71s -> 0.62s.
def _raster_runs(rows: Rows) -> _RasterRuns:
    """Encode repeated rows and pixels without transmitting renderer payloads."""
    return tuple(
        (
            len(list(repeated_rows)),
            tuple((len(list(pixels)), pixel) for pixel, pixels in groupby(row)),
        )
        for row, repeated_rows in groupby(rows)
    )


@lru_cache(maxsize=4)
def _raster_transport(image: Raster) -> _RasterRuns:
    """Reuse immutable pixel transport across rows of isolated evaluation."""
    return _raster_runs(image.rows)


def _raster_rows(runs: _RasterRuns) -> Rows:
    """Decode pixel-exact rows, sharing immutable repeats."""
    return tuple(
        chain.from_iterable(
            repeat(
                tuple(
                    chain.from_iterable(
                        repeat((pixel[0], pixel[1], pixel[2]), count)
                        for count, pixel in row
                    )
                ),
                count,
            )
            for count, row in runs
        )
    )


def _decode(text: str, *, expired: bool) -> str:
    error: exceptions.EsolangError
    output: list[str] = []
    result: dict[str, Any] | None = None
    for line in text.splitlines():
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            break  # A killed write may leave only part of its last JSON record.
        if "output" in message:
            output.append(message["output"])
        else:
            result = message
    partial = "".join(output)
    if expired:
        error = exceptions.ExecutionTimeoutError(
            "isolated execution exceeded its deadline"
        )
        error.partial_output = partial
        raise error
    if result is None:
        error = exceptions.InterpreterLimitError(
            "isolated interpreter exited without a result",
            hint="check the worker exit status and available system resources",
        )
        error.partial_output = partial
        raise error
    if "error" in result:
        kind = result["error"]
        cls = getattr(exceptions, kind, exceptions.InterpreterLimitError)
        args = result["args"]
        if kind == "UnknownLanguageError":
            args = [args[0], tuple(args[1])]
        error = cls(*args)
        error.partial_output = partial
        if "notes" in result:
            error.__notes__ = list(result["notes"])
        raise error
    return cast("str", result["result"])


#: The worker's output-cap message, which also tells the parent the cap hit.
_OUTPUT_LIMIT = "isolated output limit exceeded"


def check_memory(max_memory: int | None, *, isolated: bool) -> None:
    """Validate a Linux worker address-space budget in bytes before acquisition."""
    if max_memory is None:
        return
    check_whole(max_memory, "max_memory")
    if max_memory == 0:
        raise exceptions.ArgumentError("max_memory must be positive")
    if not isolated:
        raise exceptions.ArgumentError("max_memory requires isolated=True")
    if max_memory >= 1 << 63:
        raise exceptions.ArgumentError("max_memory exceeds the platform limit")
    if sys.platform != "linux":
        raise exceptions.ArgumentError("max_memory is supported only on Linux")


def check_limits(
    max_output: int | None, max_memory: int | None, *, isolated: bool
) -> None:
    """Validate the output and memory caps, which only a worker can enforce."""
    check_memory(max_memory, isolated=isolated)
    if max_output is None:
        return
    check_whole(max_output, "max_output")
    if not isolated:
        raise with_hint(
            exceptions.ArgumentError("max_output requires isolated=True"),
            "set isolated=True to bound output, or omit max_output",
        )


def _limit_memory(max_memory: int) -> None:
    """Lower the worker's virtual address-space ceiling without raising a hard cap."""
    import resource

    _, hard = resource.getrlimit(resource.RLIMIT_AS)
    ceiling = max_memory if hard == resource.RLIM_INFINITY else min(max_memory, hard)
    resource.setrlimit(resource.RLIMIT_AS, (ceiling, hard))


def run_isolated(
    language: str,
    program: ProgramSource,
    stdin: InputSource = "",
    timeout: float = 30.0,
    *,
    seed: int | None = None,
    scale: int | None = None,
    max_output: int | None = None,
    max_memory: int | None = None,
    settings: DialectSettings | None = None,
) -> str:
    """Return output from a subprocess; the deadline includes loading and startup.

    Works on Windows and worker threads. Errors retain their public class,
    notes and output; timeout kills and reaps the child.
    A blocked caller-owned stream read may finish in the background after timeout.
    """
    import esolangs

    check_limits(max_output, max_memory, isolated=True)
    check_timeout(timeout)
    if timeout is None:
        raise with_hint(
            exceptions.ArgumentError("isolated execution requires a finite timeout"),
            ("set a positive finite timeout, for example timeout=5.0"),
        )
    name = resolve(language)
    dialect_options(name, settings)
    deadline = monotonic() + timeout
    box: list[str | BaseException] = []

    def prepare() -> None:
        try:
            source = esolangs._check_program(name, program, stdin)  # noqa: SLF001
            retained = effective_settings(name, source, settings)
            choices = dialect_options(name, retained)
            box.append(
                json.dumps(
                    {
                        "settings": {
                            key: hex(value) if type(value) is int else value
                            for key, value in choices.items()
                        },
                        "integer_settings": [
                            key for key, value in choices.items() if type(value) is int
                        ],
                        "language": name,
                        **_source_transport(source),
                        "stdin": read_input(stdin),
                        # Decimal JSON rendering rejects valid 4301-digit seeds.
                        "seed": hex(seed) if isinstance(seed, int) else seed,
                        "integer_seed": isinstance(seed, int),
                        "max_memory": max_memory,
                        "scale": scale
                        if scale is not None
                        else source.scale
                        if isinstance(source, Raster)
                        else None,
                        "max_output": hex(max_output)
                        if max_output is not None
                        else None,
                        "integer_max_output": max_output is not None,
                    }
                )
            )
        except BaseException as exc:
            box.append(exc)

    # Caller-owned streams need not be picklable or interruptible. A daemon
    # bounds acquisition without transferring or closing their handles.
    reader = Thread(target=prepare, daemon=True)
    reader.start()
    reader.join(max(0.0, deadline - monotonic()))
    remaining = deadline - monotonic()
    if reader.is_alive() or remaining <= 0:
        raise exceptions.ExecutionTimeoutError(
            "execution timed out while loading input"
        )
    request = box[0]
    if isinstance(request, BaseException):
        raise request
    with _timeout_named(timeout):
        return _launch(request, remaining, max_output=max_output)


@contextmanager
def _timeout_named(timeout: float) -> Iterator[None]:
    """Word a deadline as an in-process run does, naming the caller's timeout."""
    try:
        yield
    except exceptions.ExecutionTimeoutError as error:
        # It said "isolated execution exceeded its deadline", a second
        # wording of one error for the same ``timeout=``.
        error.args = (f"execution exceeded the {timeout}-second timeout",)
        raise


def _launch(request: str, timeout: float, *, max_output: int | None = None) -> str:
    """Run one JSON request, killing and reaping on deadline."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    deadline = monotonic() + timeout
    with subprocess.Popen(  # fixed executable and code, no shell.
        [
            sys.executable,
            "-c",
            "from esolangs.runtime._isolated import _worker; _worker()",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE if max_output is None else subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        env=env,
    ) as child:
        remaining = deadline - monotonic()
        if remaining <= 0:
            child.kill()
            output, _stderr = child.communicate()
            return _decode(output, expired=True)
        if max_output is not None:
            return _bounded_output(child, request, remaining)
        expired = False
        try:
            output, _stderr = child.communicate(request, timeout=remaining)
        except subprocess.TimeoutExpired:
            expired = True
            child.kill()
            output, _stderr = child.communicate()
        except BaseException:
            child.kill()
            child.communicate()
            raise
    return _decode(output, expired=expired)


def _bounded_output(child: subprocess.Popen[str], request: str, timeout: float) -> str:
    """Read bounded worker records; kill and reap on an output limit or deadline."""
    records: Queue[str | BaseException | None] = Queue(maxsize=16)
    stopped = Event()

    def publish(record: str | BaseException | None) -> bool:
        while not stopped.is_set():
            try:
                records.put(record, timeout=0.05)
                return True
            except Full:
                pass
        return False

    def transfer() -> None:
        try:
            # _launch always opens both streams with PIPE.
            stdin = cast("TextIO", child.stdin)
            stdout = cast("TextIO", child.stdout)
            stdin.write(request)
            stdin.close()
            for line in stdout:
                if not publish(line):
                    return
        except Exception as error:
            publish(error)
        finally:
            publish(None)

    reader = Thread(target=transfer, daemon=True)
    deadline = monotonic() + timeout
    reader.start()
    output: list[str] = []
    expired = False
    limited = False
    try:
        while True:
            if monotonic() >= deadline:
                expired = True
                break
            try:
                record = records.get(timeout=max(0.0, deadline - monotonic()))
            except Empty:
                expired = True
                break
            if record is None:
                break
            if isinstance(record, BaseException):
                raise record
            output.append(record)
            try:
                limited = bool(json.loads(record).get("output_limit"))
            except json.JSONDecodeError:
                break
            if limited:
                break
        # A complete verdict must still leave the worker within its deadline.
        if not expired and not limited:
            try:
                child.wait(timeout=max(0.0, deadline - monotonic()))
            except subprocess.TimeoutExpired:
                expired = True
    finally:
        stopped.set()
        child.kill()
        child.wait()
        reader.join()
    return _decode("".join(output), expired=expired)


def _source_transport(source: Program) -> dict[str, Any]:
    """Encode all source containers for the JSON worker protocol."""
    if isinstance(source, CompressedText):
        return {
            "program": base64.b64encode(source.to_gzip()).decode("ascii"),
            "raster": False,
            "compressed": True,
        }
    return {
        "program": _raster_transport(source) if isinstance(source, Raster) else source,
        "raster": isinstance(source, Raster),
    }


def termination_isolated(
    name: str,
    source: Program,
    stdin: str,
    timeout: float,
    halts: str,
    diverges: str,
    *,
    settings: DialectSettings | None = None,
    max_output: int | None = None,
    max_memory: int | None = None,
) -> str:
    """Prove halt or cycle in a child; deadline never means divergence."""
    check_memory(max_memory, isolated=True)
    choices = dialect_options(name, settings)
    request = json.dumps(
        {
            "language": name,
            **_source_transport(source),
            "stdin": stdin,
            "max_memory": max_memory,
            "termination": [halts, diverges],
            "settings": choices,
            "max_output": hex(max_output) if max_output is not None else None,
            "integer_max_output": max_output is not None,
        }
    )
    with _timeout_named(timeout):
        return _launch(request, timeout, max_output=max_output)


def _exit_with_parent() -> None:
    """End this worker once its parent is gone.

    A SIGTERM or SIGHUP to the parent skips its kill-and-reap, and the
    orphan (reparented to 1) ran a looping program for hours.
    """
    parent = os.getppid()
    if sys.platform == "linux":
        # The kernel delivers it, with no thread: a watcher's stack counted
        # against max_memory's RLIMIT_AS and tight budgets failed in CI.
        import ctypes
        import signal

        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) == 0:  # PR_SET_PDEATHSIG
            if os.getppid() != parent:  # Died before the request took.
                os._exit(1)
            return

    def watch() -> None:
        while os.getppid() == parent:
            sleep(0.25)
        os._exit(1)

    Thread(target=watch, daemon=True).start()


def _worker() -> None:
    """Stream output and a structured verdict to the parent."""
    import esolangs
    from esolangs.runtime.io import ScriptedIO

    _exit_with_parent()

    def send(message: dict[str, Any]) -> None:
        print(json.dumps(message), flush=True)

    class StreamingIO(ScriptedIO):
        def __init__(self, stdin: InputSource = "") -> None:
            super().__init__(stdin)
            self.written = 0

        def _write(self, value: object) -> None:
            text = str(value)
            limit = request.get("max_output")
            accepted = text if limit is None else text[: max(0, limit - self.written)]
            super()._write(accepted)
            self.written += len(accepted)
            # One write may contain an entire dump; keep protocol records bounded.
            for at in range(0, len(accepted), 4096):
                send({"output": accepted[at : at + 4096]})
            if len(accepted) != len(text):
                raise exceptions.InterpreterLimitError(
                    _OUTPUT_LIMIT,
                    hint="reduce output or raise max_output if the output is needed",
                )

    # The worker swaps the IO class process-wide so program output streams
    # to the parent. ScriptedIO is deliberately absent from __all__; the
    # ignore marks this patch as intentional, not a typo.
    esolangs.ScriptedIO = StreamingIO  # type: ignore[attr-defined]
    request = json.load(sys.stdin)
    if request.get("integer_max_output", False):
        request["max_output"] = int(request["max_output"], 16)
    # Release a small reserve before reporting allocation failure under RLIMIT_AS.
    reserve = bytearray(65_536)
    try:
        if request.get("max_memory") is not None:
            try:
                _limit_memory(request["max_memory"])
            except (OSError, OverflowError, ValueError) as error:
                raise exceptions.InterpreterLimitError(
                    f"cannot enforce memory limit: {error}"
                ) from error
        program = request["program"]
        if request.get("compressed", False):
            program = CompressedText(base64.b64decode(program, validate=True))
        if request["raster"]:
            program = Raster(_raster_rows(program))
        settings = DialectSettings(
            **{
                key: int(value, 16)
                if key in request.get("integer_settings", [])
                else value
                for key, value in request.get("settings", {}).items()
            }
        )
        if "termination" in request:
            from esolangs import vm
            from esolangs.runtime._evaluate import _terminates

            if request.get("max_output") is not None:
                # Same process-wide swap for the termination checker's vm import.
                vm.ScriptedIO = StreamingIO  # type: ignore[attr-defined]

            halts, diverges = request["termination"]
            output = _terminates(
                request["language"],
                program,
                request["stdin"],
                None,
                halts,
                diverges,
                settings=settings,
            )
        else:
            output = esolangs.run(
                request["language"],
                program,
                stdin=request["stdin"],
                timeout=None,
                seed=int(request["seed"], 16)
                if request.get("integer_seed", False)
                else request["seed"],
                scale=request.get("scale"),
                settings=settings,
            )
    except (MemoryError, exceptions.EsolangError) as error:
        # ``run`` translates an in-process MemoryError; here it is the cap.
        cause: BaseException | None = error
        while cause is not None and not isinstance(cause, MemoryError):
            cause = cause.__cause__
        if cause is not None:
            del reserve
            send(
                {
                    "error": "InterpreterLimitError",
                    "args": ["isolated memory limit exceeded"],
                }
            )
            return
        args: tuple[object, ...] = error.args
        if isinstance(error, exceptions.UnknownLanguageError):
            args = (error.language, error.suggestions)
        elif isinstance(error, exceptions.InputExhaustedError):
            args = (error.reads, error.supplied, error.unit)
        send(
            {
                "error": type(error).__name__,
                "args": args,
                "notes": getattr(error, "__notes__", []),
                "output_limit": isinstance(error, exceptions.InterpreterLimitError)
                and str(error) == _OUTPUT_LIMIT,
            }
        )
    else:
        send({"result": output})


if __name__ == "__main__":
    _worker()
