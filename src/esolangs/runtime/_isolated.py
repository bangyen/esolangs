"""Execute in a disposable interpreter with a portable wall-clock deadline."""

from __future__ import annotations

import base64
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
from esolangs.artifacts import Artifact, ProgramArtifact
from esolangs.compressed import CompressedText
from esolangs.outcomes import ExecutionOutcome, _capture_outcome, _failed_outcome
from esolangs.raster import Pixel, Raster, Rows
from esolangs.registry._catalog import Catalog
from esolangs.results import ExecutionResult
from esolangs.runtime._input import InputSource, read_input
from esolangs.runtime._json import canonical_integer, worker_dumps, worker_loads
from esolangs.runtime._program import Program
from esolangs.runtime._proof import TerminationResult
from esolangs.runtime._result_wire import (
    _counter,
    decode_result,
    decode_termination,
    encode_decision,
    encode_result,
)
from esolangs.runtime._source import ProgramSource, effective_scale
from esolangs.runtime._validate import check_timeout, check_whole
from esolangs.runtime.source_hints import with_hint
from esolangs.settings import (
    DialectSettings,
    _settings_for,
    dialect_options,
    effective_settings,
)

type _WorkerResponse = ExecutionOutcome | TerminationResult

type _RasterRuns = tuple[tuple[int, tuple[tuple[int, Pixel], ...]], ...]

_REQUEST_FIELDS = frozenset(
    {
        "language",
        "program",
        "raster",
        "compressed",
        "stdin",
        "settings",
        "integer_settings",
        "seed",
        "integer_seed",
        "scale",
        "max_memory",
        "max_output",
        "integer_max_output",
        "max_steps",
        "integer_max_steps",
        "termination",
        "report_prepared",
    }
)


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


def _error_from_wire(result: dict[str, Any], partial: str) -> exceptions.EsolangError:
    """Restore only the canonical error envelope and its explicit observation."""
    kind = result["error"]
    cls = getattr(exceptions, kind, None) if isinstance(kind, str) else None
    if not isinstance(cls, type) or not issubclass(cls, exceptions.EsolangError):
        raise ValueError("unknown isolated error kind")
    fields = {"error", "args", "notes", "execution", "output_limit"}
    if issubclass(cls, exceptions.ExecutionTimeoutError):
        fields.add("bound")
    if set(result) != fields or not isinstance(result["args"], list):
        raise ValueError("invalid isolated error fields")
    if type(result["output_limit"]) is not bool or not isinstance(
        result["notes"], list
    ):
        raise ValueError("invalid isolated error options")
    if any(not isinstance(note, str) for note in result["notes"]):
        raise ValueError("invalid isolated error notes")
    args = result["args"]
    # The wire keeps every argument positional; these options are keyword-only.
    options: dict[str, Any] = {}
    if kind == "UnknownLanguageError":
        if (
            len(args) != 2
            or not isinstance(args[0], str)
            or not isinstance(args[1], list)
            or any(not isinstance(name, str) for name in args[1])
        ):
            raise ValueError("invalid unknown-language error arguments")
        args, options = args[:1], {"suggestions": tuple(args[1])}
    elif kind == "InputExhaustedError":
        if len(args) != 3 or not isinstance(args[2], str):
            raise ValueError("invalid input-exhaustion error arguments")
        args, options = [_counter(args[0]), _counter(args[1])], {"unit": args[2]}
    error: exceptions.EsolangError = cls(*args, **options)
    if result["output_limit"] != (
        isinstance(error, exceptions.InterpreterLimitError)
        and str(error) == _OUTPUT_LIMIT
    ):
        raise ValueError("inconsistent isolated output-limit marker")
    error.partial_output = partial
    error.__notes__ = list(result["notes"])
    if isinstance(error, exceptions.ExecutionTimeoutError):
        if result["bound"] not in (
            "timeout",
            "max_steps",
            "execution_timeout",
            "total_timeout",
        ):
            raise ValueError("invalid timeout bound")
        error.bound = result["bound"]
    if result["execution"] is not None:
        error.observation = decode_result(partial, result["execution"])
        if error.observation.completion is not None:
            raise ValueError("failed execution cannot declare completion")
    return error


def _decode_outcome(text: str, *, expired: bool) -> _WorkerResponse:
    error: exceptions.EsolangError
    output: list[str] = []
    result: dict[str, Any] | None = None
    malformed = False
    for line in text.splitlines():
        try:
            message = worker_loads(line)
        except ValueError:
            malformed = True
            break  # A killed write may leave only part of its last JSON record.
        if not isinstance(message, dict) or result is not None:
            malformed = True
            break
        if "output" in message:
            if set(message) != {"output"} or not isinstance(message["output"], str):
                malformed = True
                break
            output.append(message["output"])
        else:
            result = message
    partial = "".join(output)
    if expired:
        error = exceptions.ExecutionTimeoutError(
            "isolated execution exceeded its deadline"
        )
        error.partial_output = partial
        return _failed_outcome(error)
    if result is None and not malformed:
        error = exceptions.InterpreterLimitError(
            "isolated interpreter exited without a result",
            hint="check the worker exit status and available system resources",
        )
        error.partial_output = partial
        return _failed_outcome(error)
    try:
        if malformed or result is None:
            raise ValueError("invalid isolated stream")
        if "error" in result:
            error = _error_from_wire(result, partial)
        else:
            fields = {"result", "execution"}
            if "termination" in result:
                fields.add("termination")
            if set(result) != fields or result["result"] != partial:
                raise ValueError("invalid isolated result fields or output")
            if "termination" in result:
                return decode_termination(
                    result["result"], result["execution"], result["termination"]
                )
            execution = decode_result(result["result"], result["execution"])
            if execution.completion is None:
                raise ValueError("worker omitted output completion")
            return ExecutionOutcome("completed", execution)
    except (TypeError, ValueError, KeyError) as cause:
        error = exceptions.InterpreterLimitError("invalid isolated execution result")
        error.partial_output = partial
        error.__cause__ = cause
        return _failed_outcome(error)
    return _failed_outcome(error)


#: The worker's output-cap message, which also tells the parent the cap hit.
_OUTPUT_LIMIT = "isolated output limit exceeded"


def check_memory(max_memory: int | None, *, isolated: bool) -> None:
    """Validate a Linux worker address-space budget in bytes before acquisition."""
    if max_memory is None:
        return
    check_whole(max_memory, "max_memory")
    if max_memory == 0:
        raise exceptions.ArgumentError("max_memory must be a positive integer, got 0")
    if not isolated:
        raise exceptions.ArgumentError("max_memory requires isolated=True")
    # A local, not ``sys.platform`` inline: mypy narrows that per host and
    # called the next check unreachable on macOS.
    platform: str = sys.platform
    if platform != "linux":
        raise exceptions.ArgumentError("max_memory is supported only on Linux")
    if max_memory >= 1 << 63:
        raise exceptions.ArgumentError("max_memory exceeds the platform limit")


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


def _check_worker_runtime(name: str, catalog: Catalog) -> None:
    """Refuse scoped declarations that the fresh worker cannot reproduce."""
    from esolangs.registry._catalog import get_catalog

    default = get_catalog().languages.get(name)
    selected = catalog.languages[name]
    if (
        default is None
        or selected.id != default.id
        or selected.runtime != default.runtime
    ):
        raise exceptions.ArgumentError(
            "isolated execution requires a runtime declared in the installed catalog"
        )


@_capture_outcome
def execute_isolated(
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
    max_steps: int | None = None,
    execution_timeout: float | None = None,
    preparation_timeout: float | None = None,
    catalog: Catalog | None = None,
) -> ExecutionOutcome:
    """Return a result from a subprocess; the deadline includes loading and startup.

    Works on Windows and worker threads. Errors retain their public class,
    notes and output; timeout kills and reaps the child.
    A blocked caller-owned stream read may finish in the background after timeout.
    """
    result = _invoke_worker(
        language,
        program,
        stdin,
        timeout,
        seed=seed,
        scale=scale,
        max_output=max_output,
        max_memory=max_memory,
        settings=settings,
        max_steps=max_steps,
        execution_timeout=execution_timeout,
        preparation_timeout=preparation_timeout,
        catalog=catalog,
    )
    if isinstance(result, ExecutionOutcome):
        return result
    error = exceptions.InterpreterLimitError(
        "isolated worker omitted execution metadata"
    )
    error.partial_output = (
        result.output
        if isinstance(result, ExecutionResult)
        else result.observation.output
    )
    return _failed_outcome(error)


def _invoke_worker(
    language: str,
    program: ProgramSource,
    stdin: InputSource,
    timeout: float,
    *,
    seed: int | None = None,
    scale: int | None = None,
    max_output: int | None = None,
    max_memory: int | None = None,
    settings: DialectSettings | None = None,
    max_steps: int | None = None,
    execution_timeout: float | None = None,
    preparation_timeout: float | None = None,
    catalog: Catalog | None = None,
    termination: bool = False,
) -> _WorkerResponse:
    """Acquire source and enforce phase budgets for execution or proof."""
    from esolangs.operations.source import _check_program
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)

    check_limits(max_output, max_memory, isolated=True)
    if max_steps is not None:
        check_whole(max_steps, "max_steps")
    check_timeout(timeout)
    check_timeout(execution_timeout)
    check_timeout(preparation_timeout)
    if timeout is None:
        raise with_hint(
            exceptions.ArgumentError("isolated execution requires a finite timeout"),
            ("set a positive finite timeout, for example timeout=5.0"),
        )
    name = catalog.resolve(language)
    _check_worker_runtime(name, catalog)
    scale = effective_scale(name, program, scale, catalog=catalog)
    settings = effective_settings(name, program, settings, catalog=catalog)
    dialect_options(name, settings, catalog=catalog)
    started = monotonic()
    deadline = started + timeout
    preparation_deadline = (
        None if preparation_timeout is None else started + preparation_timeout
    )
    # The execution budget also bounds acquisition: a caller's blocking stdin
    # otherwise waited out the 30-second default total (run(timeout=2) took
    # 32 s), while worker startup stays uncharged.
    execution_deadline = (
        None if execution_timeout is None else started + execution_timeout
    )
    acquisition_deadline = min(
        d for d in (deadline, preparation_deadline, execution_deadline) if d is not None
    )
    box: list[str | BaseException] = []

    def prepare() -> None:
        try:
            artifact = _check_program(name, program, stdin, catalog=catalog)
            source = artifact.source
            retained = effective_settings(name, artifact, settings, catalog=catalog)
            box.append(
                worker_dumps(
                    _request_wire(
                        name,
                        source,
                        read_input(stdin),
                        settings=retained,
                        seed=seed,
                        scale=effective_scale(name, artifact, scale, catalog=catalog),
                        max_memory=max_memory,
                        max_output=max_output,
                        max_steps=max_steps,
                        report_prepared=(
                            preparation_deadline is not None
                            or execution_timeout is not None
                        ),
                        termination=termination,
                        catalog=catalog,
                    )
                )
            )
        except BaseException as exc:
            box.append(exc)

    # Caller-owned streams need not be picklable or interruptible. A daemon
    # bounds acquisition without transferring or closing their handles.
    reader = Thread(target=prepare, daemon=True)
    reader.start()
    reader.join(max(0.0, acquisition_deadline - monotonic()))
    now = monotonic()
    if reader.is_alive() or now >= acquisition_deadline:
        if preparation_deadline == acquisition_deadline < deadline:
            raise _preparation_expired()
        error = exceptions.ExecutionTimeoutError(
            "execution timed out while loading input"
        )
        if execution_deadline == acquisition_deadline < deadline:
            error.bound = "execution_timeout"
        raise error
    request = box[0]
    if isinstance(request, BaseException):
        raise request
    with _timeout_named(timeout):
        if preparation_deadline is None and execution_timeout is None:
            result = _launch(request, deadline - now, max_output=max_output)
        else:
            result = _launch(
                request,
                deadline - now,
                max_output=max_output,
                preparation_deadline=preparation_deadline,
                execution_timeout=execution_timeout,
            )
    if (
        isinstance(result, ExecutionOutcome)
        and isinstance(result.error, exceptions.ExecutionTimeoutError)
        and result.bound == "timeout"
    ):
        result.error.args = (f"execution exceeded the {timeout}-second timeout",)
    return result


@contextmanager
def _timeout_named(timeout: float) -> Iterator[None]:
    """Word a deadline as an in-process run does, naming the caller's timeout."""
    try:
        yield
    except exceptions.ExecutionTimeoutError as error:
        # It said "isolated execution exceeded its deadline", a second
        # wording of one error for the same ``timeout=``.
        if error.bound == "timeout":
            error.args = (f"execution exceeded the {timeout}-second timeout",)
        raise


def _preparation_expired() -> exceptions.ExecutionTimeoutError:
    error = exceptions.ExecutionTimeoutError("execution timed out during preparation")
    error.bound = "preparation_timeout"
    return error


def _launch(
    request: str,
    timeout: float,
    *,
    max_output: int | None = None,
    preparation_deadline: float | None = None,
    execution_timeout: float | None = None,
) -> _WorkerResponse:
    """Run one JSON request, killing and reaping on deadline."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    deadline = monotonic() + timeout
    report_prepared = preparation_deadline is not None or execution_timeout is not None
    streaming = max_output is not None or report_prepared
    with subprocess.Popen(  # fixed executable and code, no shell.
        [
            sys.executable,
            "-c",
            "from esolangs.runtime._isolated import _worker; _worker()",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL if streaming else subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    ) as child:
        remaining = deadline - monotonic()
        if remaining <= 0:
            child.kill()
            output, _stderr = child.communicate()
            return _decode_outcome(output, expired=True)
        if report_prepared:
            return _bounded_output(
                child,
                request,
                remaining,
                preparation_deadline=preparation_deadline,
                execution_timeout=execution_timeout,
            )
        if streaming:
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
    return _decode_outcome(output, expired=expired)


def _bounded_output(
    child: subprocess.Popen[str],
    request: str,
    timeout: float,
    *,
    preparation_deadline: float | None = None,
    execution_timeout: float | None = None,
) -> _WorkerResponse:
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
    try:
        return _read_worker_output(
            child, records, deadline, preparation_deadline, execution_timeout
        )
    finally:
        stopped.set()
        child.kill()
        child.wait()
        reader.join()


def _read_worker_output(
    child: subprocess.Popen[str],
    records: Queue[str | BaseException | None],
    deadline: float,
    preparation_deadline: float | None,
    execution_timeout: float | None,
) -> _WorkerResponse:
    """Read the worker stream under the active phase deadline."""
    output: list[str] = []
    expired = False
    limited = False
    execution_deadline = None
    awaiting_prepared = (
        preparation_deadline is not None or execution_timeout is not None
    )

    while True:
        active_deadline = min(
            phase
            for phase in (deadline, preparation_deadline, execution_deadline)
            if phase is not None
        )
        try:
            now = monotonic()
            if now >= active_deadline:
                raise Empty
            record = records.get(timeout=active_deadline - now)
        except Empty:
            if preparation_deadline is not None and preparation_deadline < deadline:
                raise _preparation_expired() from None
            expired = True
            break
        if record is None:
            break
        if isinstance(record, BaseException):
            raise record
        try:
            message = worker_loads(record)
        except ValueError:
            output.append(record)
            break
        if (
            awaiting_prepared
            and isinstance(message, dict)
            and message.keys() == {"prepared"}
            and message["prepared"] is True
        ):
            awaiting_prepared = False
            preparation_deadline = None
            if execution_timeout is not None:
                execution_deadline = monotonic() + execution_timeout
            continue
        output.append(record)
        limited = isinstance(message, dict) and message.get("output_limit") is True
        if limited:
            break
    # A complete verdict must still leave the worker within its deadline.
    if not expired and not limited:
        try:
            child.wait(timeout=max(0.0, active_deadline - monotonic()))
        except subprocess.TimeoutExpired:
            if preparation_deadline is not None and preparation_deadline < deadline:
                raise _preparation_expired() from None
            expired = True
    result = _decode_outcome("".join(output), expired=expired)
    if (
        expired
        and execution_deadline is not None
        and execution_deadline < deadline
        and isinstance(result, ExecutionOutcome)
        and isinstance(result.error, exceptions.ExecutionTimeoutError)
    ):
        result.error.bound = "execution_timeout"
        result.error.args = (
            f"execution exceeded the {execution_timeout}-second timeout",
        )
    return result


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
        "compressed": False,
    }


def _request_wire(
    name: str,
    source: Program,
    stdin: str,
    *,
    settings: DialectSettings | None = None,
    seed: int | None = None,
    scale: int | None = None,
    max_memory: int | None = None,
    max_output: int | None = None,
    max_steps: int | None = None,
    termination: bool = False,
    report_prepared: bool = False,
    catalog: Catalog | None = None,
) -> dict[str, Any]:
    """Encode one complete worker request, including unavailable options."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    choices = dialect_options(name, settings, catalog=catalog)
    return {
        "language": name,
        **_source_transport(source),
        "stdin": stdin,
        "settings": {
            key: hex(value) if type(value) is int else value
            for key, value in choices.items()
        },
        "integer_settings": [
            key for key, value in choices.items() if type(value) is int
        ],
        # Decimal JSON rendering rejects valid 4301-digit integers.
        "seed": hex(seed) if seed is not None else None,
        "integer_seed": seed is not None,
        "scale": scale,
        "max_memory": max_memory,
        "max_output": hex(max_output) if max_output is not None else None,
        "integer_max_output": max_output is not None,
        "max_steps": hex(max_steps) if max_steps is not None else None,
        "integer_max_steps": max_steps is not None,
        "termination": termination,
        "report_prepared": report_prepared,
    }


def termination_result_isolated(
    name: str,
    source: Program | Artifact,
    stdin: str,
    timeout: float,
    *,
    settings: DialectSettings | None = None,
    max_output: int | None = None,
    max_memory: int | None = None,
    max_steps: int | None = None,
    execution_timeout: float | None = None,
    preparation_timeout: float | None = None,
    catalog: Catalog | None = None,
) -> TerminationResult:
    """Retain worker IO and exact proof evidence; a deadline remains undecided."""
    response = _invoke_worker(
        name,
        source,
        stdin,
        timeout,
        settings=settings,
        max_output=max_output,
        max_memory=max_memory,
        max_steps=max_steps,
        execution_timeout=execution_timeout,
        preparation_timeout=preparation_timeout,
        catalog=catalog,
        termination=True,
    )
    result = response.unwrap() if isinstance(response, ExecutionOutcome) else response
    if not isinstance(result, TerminationResult):
        error = exceptions.InterpreterLimitError(
            "termination worker omitted decision evidence"
        )
        error.partial_output = result.output
        raise error
    return result


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


def _worker(*, catalog: Catalog | None = None) -> None:
    """Serve one request with invocation-owned streaming I/O."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)

    _serve_request(catalog=catalog)


def _read_request(stream: TextIO) -> dict[str, Any]:
    """Decode the canonical request; omitted options are protocol errors."""
    request = worker_loads(stream.read())
    if not isinstance(request, dict) or set(request) != _REQUEST_FIELDS:
        raise ValueError("invalid worker request fields")
    flags = (
        "raster",
        "compressed",
        "termination",
        "integer_seed",
        "integer_max_output",
        "integer_max_steps",
    )
    if (
        any(type(request[key]) is not bool for key in flags)
        or (request["raster"] and request["compressed"])
        or any(not isinstance(request[key], str) for key in ("language", "stdin"))
        or not isinstance(request["settings"], dict)
        or not isinstance(request["integer_settings"], list)
    ):
        raise ValueError("invalid worker request values")
    integer_settings = request["integer_settings"]
    if (
        any(not isinstance(key, str) for key in integer_settings)
        or len(set(integer_settings)) != len(integer_settings)
        or set(integer_settings) - request["settings"].keys()
    ):
        raise ValueError("invalid worker integer settings")
    for key, value in request["settings"].items():
        if not isinstance(value, str):
            raise ValueError("invalid worker setting")
        if key in integer_settings:
            canonical_integer(value)
    for key in ("seed", "max_output", "max_steps"):
        value = request[key]
        if request[f"integer_{key}"]:
            decoded = canonical_integer(value)
            if key != "seed" and decoded < 0:
                raise ValueError("invalid worker limit")
            if key != "seed":
                request[key] = decoded
        elif value is not None:
            raise ValueError("untagged worker integer")
    for key in ("scale", "max_memory"):
        value = request[key]
        if value is not None and (type(value) is not int or value < 1):
            raise ValueError("invalid worker size")
    if type(request["report_prepared"]) is not bool:
        raise ValueError("invalid worker preparation flag")
    if request["raster"]:
        _check_raster_request(request["program"])
    elif not isinstance(request["program"], str):
        raise ValueError("invalid worker source")
    return cast("dict[str, Any]", request)


def _check_raster_request(runs: Any) -> None:
    """Refuse malformed runs before expansion can drop counts or channels."""
    if not isinstance(runs, list):
        raise ValueError("invalid worker raster")
    for run in runs:
        if (
            not isinstance(run, list)
            or len(run) != 2
            or type(run[0]) is not int
            or run[0] < 1
            or not isinstance(run[1], list)
        ):
            raise ValueError("invalid worker raster row")
        for pixel in run[1]:
            if (
                not isinstance(pixel, list)
                or len(pixel) != 2
                or type(pixel[0]) is not int
                or pixel[0] < 1
                or not isinstance(pixel[1], list)
                or len(pixel[1]) != 3
                or any(type(c) is not int or not 0 <= c <= 255 for c in pixel[1])
            ):
                raise ValueError("invalid worker raster pixel")


def _failure_wire(error: BaseException) -> dict[str, Any]:
    """Encode one retained failure for the worker's validated wire protocol."""
    args: tuple[object, ...] = error.args
    if isinstance(error, exceptions.UnknownLanguageError):
        args = (error.language, error.suggestions)
    elif isinstance(error, exceptions.InputExhaustedError):
        args = (error.reads, error.supplied, error.unit)
    observation = getattr(error, "observation", None)
    return {
        "error": type(error).__name__,
        "args": args,
        "notes": getattr(error, "__notes__", []),
        "execution": encode_result(observation) if observation is not None else None,
        **(
            {"bound": error.bound}
            if isinstance(error, exceptions.ExecutionTimeoutError)
            else {}
        ),
        "output_limit": isinstance(error, exceptions.InterpreterLimitError)
        and str(error) == _OUTPUT_LIMIT,
    }


def _serve_request(*, catalog: Catalog | None = None) -> None:
    """Stream live output and validated execution or termination metadata."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    import esolangs.operations.execution as _execution_operations
    from esolangs.runtime.io import ScriptedIO

    request = _read_request(sys.stdin)
    _exit_with_parent()

    def send(message: dict[str, Any]) -> None:
        print(worker_dumps(message), flush=True)

    class StreamingIO(ScriptedIO):
        def __init__(self, stdin: InputSource = "") -> None:
            super().__init__(stdin)
            self.written = 0

        def _write(self, value: object) -> None:
            text = str(value)
            limit = request["max_output"]
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

    # Release a small reserve before reporting allocation failure under RLIMIT_AS.
    reserve = bytearray(65_536)

    def send_failure(error: BaseException) -> None:
        nonlocal reserve
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
                    "notes": [],
                    "execution": None,
                    "output_limit": False,
                }
            )
            return
        send(_failure_wire(error))

    try:
        if request["max_memory"] is not None:
            try:
                _limit_memory(request["max_memory"])
            except (OSError, OverflowError, ValueError) as error:
                raise exceptions.InterpreterLimitError(
                    f"cannot enforce memory limit: {error}"
                ) from error
        program = request["program"]
        if request["compressed"]:
            program = CompressedText(base64.b64decode(program, validate=True))
        if request["raster"]:
            program = Raster(_raster_rows(program))
        settings = _settings_for(
            request["language"],
            {
                key: int(value, 16) if key in request["integer_settings"] else value
                for key, value in request["settings"].items()
            },
            catalog=catalog,
        )
        # The parent already decoded and checked runnable source.
        program = ProgramArtifact(
            program,
            request["language"],
            settings,
            request["scale"] if request["termination"] else None,
        )
        prepared = None
        if request["report_prepared"]:
            from esolangs.runtime._prepared import prepare_program

            prepared = prepare_program(
                request["language"],
                program,
                settings=settings,
                scale=request["scale"],
                catalog=catalog,
                bind_machine=True,
            )
            send({"prepared": True})
        if request["termination"]:
            from esolangs.runtime._termination import _termination_result

            proved = _termination_result(
                request["language"],
                program,
                request["stdin"],
                max_steps=request["max_steps"],
                settings=settings,
                catalog=catalog,
                io_factory=StreamingIO,
                prepared=prepared,
            )
            result = proved.observation
        else:
            outcome = _execution_operations._execute_invocation(  # noqa: SLF001 - same outcome route as public execute
                request["language"],
                program,
                stdin=request["stdin"],
                seed=int(request["seed"], 16)
                if request["integer_seed"]
                else request["seed"],
                scale=request["scale"],
                settings=settings,
                max_steps=request["max_steps"],
                catalog=catalog,
                io_factory=StreamingIO,
                prepared=prepared,
            )
            if outcome.error is not None:
                send_failure(outcome.error)
                return
            result = outcome.observation
        try:
            message = {"result": result.output, "execution": encode_result(result)}
            if request["termination"]:
                message["termination"] = encode_decision(proved.decision)
            send(message)
        except (TypeError, ValueError) as encoding_error:
            raise exceptions.InterpreterLimitError(
                "cannot transport execution evidence"
            ) from encoding_error
    except (MemoryError, exceptions.EsolangError) as error:
        send_failure(error)


if __name__ == "__main__":
    _worker()
