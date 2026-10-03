"""Execute in a disposable interpreter with a portable wall-clock deadline."""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404 -- fixed Python worker; source travels over stdin.
import sys
from queue import Empty, Full, Queue
from threading import Event, Thread
from time import monotonic
from typing import Any, TextIO, cast

from esolangs import exceptions
from esolangs._source import InputSource, ProgramSource, read_input
from esolangs._validate import check_timeout, check_whole
from esolangs.interpreters.source_hints import with_hint
from esolangs.raster import Raster
from esolangs.registry import resolve


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


def run_isolated(
    language: str,
    program: ProgramSource,
    stdin: InputSource = "",
    timeout: float = 30.0,
    *,
    seed: int | None = None,
    scale: int | None = None,
    max_output: int | None = None,
) -> str:
    """Return output from a subprocess; the deadline includes loading and startup.

    Works on Windows and worker threads. Errors retain their public class,
    notes and output; timeout kills and reaps the child.
    A blocked caller-owned stream read may finish in the background after timeout.
    """
    import esolangs

    check_timeout(timeout)
    if max_output is not None:
        check_whole(max_output, "max_output")
    if timeout is None:
        raise with_hint(
            exceptions.ArgumentError("isolated execution requires a finite timeout"),
            ("set a positive finite timeout, for example timeout=5.0"),
        )
    name = resolve(language)
    deadline = monotonic() + timeout
    box: list[str | BaseException] = []

    def prepare() -> None:
        try:
            source = esolangs.check_program(name, program, stdin)
            box.append(
                json.dumps(
                    {
                        "language": name,
                        "program": source.rows
                        if isinstance(source, Raster)
                        else source,
                        "raster": isinstance(source, Raster),
                        "stdin": read_input(stdin),
                        "seed": seed,
                        "scale": scale,
                        "max_output": max_output,
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
    return _launch(request, remaining, max_output=max_output)


def _launch(request: str, timeout: float, *, max_output: int | None = None) -> str:
    """Run one JSON request, killing and reaping on deadline."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    with subprocess.Popen(  # nosec B603 -- fixed executable and code, no shell.
        [sys.executable, "-c", "from esolangs._isolated import _worker; _worker()"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE if max_output is None else subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        env=env,
    ) as child:
        if max_output is not None:
            return _bounded_output(child, request, timeout)
        expired = False
        try:
            output, _stderr = child.communicate(request, timeout=timeout)
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


def termination_isolated(
    name: str,
    source: str,
    stdin: str,
    timeout: float,
    halts: str,
    diverges: str,
) -> str:
    """Prove halt or cycle in a child; deadline never means divergence."""
    return _launch(
        json.dumps(
            {
                "language": name,
                "program": source,
                "stdin": stdin,
                "raster": False,
                "termination": [halts, diverges],
            }
        ),
        timeout,
    )


def _worker() -> None:
    """Stream output and a structured verdict to the parent."""
    import esolangs
    from esolangs.interpreters.io import ScriptedIO

    def send(message: dict[str, Any]) -> None:
        print(json.dumps(message), flush=True)

    class StreamingIO(ScriptedIO):
        written = 0

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
                    "isolated output limit exceeded",
                    hint="reduce output or raise max_output if the output is needed",
                )

    vars(esolangs)["ScriptedIO"] = StreamingIO
    request = json.load(sys.stdin)
    program = request["program"]
    if request["raster"]:
        program = Raster(tuple(tuple(tuple(pixel) for pixel in row) for row in program))
    try:
        if "termination" in request:
            from esolangs._evaluate import _terminates

            halts, diverges = request["termination"]
            output = _terminates(
                request["language"], program, request["stdin"], None, halts, diverges
            )
        else:
            output = esolangs.run(
                request["language"],
                program,
                request["stdin"],
                timeout=None,
                seed=request["seed"],
                scale=request.get("scale"),
            )
    except exceptions.EsolangError as error:
        args: tuple[object, ...] = error.args
        if isinstance(error, exceptions.UnknownLanguageError):
            args = (error.language, error.suggestions)
        elif isinstance(error, exceptions.InputExhaustedError):
            args = (error.reads, error.supplied)
        send(
            {
                "error": type(error).__name__,
                "args": args,
                "notes": getattr(error, "__notes__", []),
                "output_limit": isinstance(error, exceptions.InterpreterLimitError)
                and str(error) == "isolated output limit exceeded",
            }
        )
    else:
        send({"result": output})


if __name__ == "__main__":
    _worker()
