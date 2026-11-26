"""Execute in a disposable interpreter with a portable wall-clock deadline."""

from __future__ import annotations

import os
import subprocess  # fixed Python worker; source travels over stdin.
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic

from esolangs import exceptions
from esolangs.artifacts import Artifact, ProgramArtifact
from esolangs.outcomes import ExecutionOutcome, _capture_outcome, _failed_outcome
from esolangs.registry._catalog import Catalog
from esolangs.results import ExecutionResult
from esolangs.runtime._acquire import acquire, preparation_expired
from esolangs.runtime._execution import (
    check_seed_for,
    check_worker_runtime,
)
from esolangs.runtime._files import stream_read_deadline
from esolangs.runtime._input import InputSource, check_input, read_input
from esolangs.runtime._json import worker_request
from esolangs.runtime._program import Program
from esolangs.runtime._proof import TerminationResult
from esolangs.runtime._request_wire import encode_request
from esolangs.runtime._source import ProgramSource, check_scale_for, effective_scale
from esolangs.runtime._validate import (
    _ISOLATED_TIMEOUT,
    _TIMEOUT_CEILING,
    check_memory_size,
    check_seed,
    check_timeout,
    check_whole,
)
from esolangs.runtime._worker_pipe import communicate
from esolangs.runtime._worker_response import (
    _bounded_output,
    _decode_outcome,
    _WorkerResponse,
)
from esolangs.runtime.source_hints import with_hint
from esolangs.settings import DialectSettings

_ACQUISITION_STARTED: ContextVar[float | None] = ContextVar(
    "_ACQUISITION_STARTED", default=None
)


@contextmanager
def _acquisition_started_at(started: float) -> Iterator[None]:
    """Include source and stdin acquisition by the caller in a worker deadline."""
    token = _ACQUISITION_STARTED.set(started)
    try:
        yield
    finally:
        _ACQUISITION_STARTED.reset(token)


def check_memory(max_memory: int | None, *, isolated: bool) -> int | None:
    """Validate a Linux worker address-space budget in bytes before acquisition."""
    if max_memory is None:
        return None
    max_memory = check_memory_size(max_memory)
    if not isolated:
        raise exceptions.ArgumentError("max_memory requires isolated=True")
    # A local, not ``sys.platform`` inline: mypy narrows that per host and
    # called the next check unreachable on macOS.
    platform: str = sys.platform
    if platform != "linux":
        raise exceptions.ArgumentError("max_memory is supported only on Linux")
    if max_memory >= 1 << 63:
        raise exceptions.ArgumentError("max_memory exceeds the platform limit")
    return max_memory


def check_limits(
    max_output: int | None, max_memory: int | None, *, isolated: bool
) -> tuple[int | None, int | None]:
    """Validate the output and memory caps, which only a worker can enforce."""
    max_memory = check_memory(max_memory, isolated=isolated)
    if max_output is None:
        return None, max_memory
    max_output = check_whole(max_output, "max_output")
    if not isolated:
        raise with_hint(
            exceptions.ArgumentError("max_output requires isolated=True"),
            "set isolated=True to bound output, or omit max_output",
        )
    return max_output, max_memory


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
    _loaded: ProgramArtifact[Program] | None = None,
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
        _loaded=_loaded,
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
    _loaded: ProgramArtifact[Program] | None = None,
) -> _WorkerResponse:
    """Acquire source and enforce phase budgets for execution or proof."""
    from esolangs.registry._catalog import get_catalog
    from esolangs.runtime._artifact_source import check_program
    from esolangs.runtime._prepared import _artifact_input_frame, _check_source_options
    from esolangs.runtime._source import anchor_program_source

    program = anchor_program_source(program)
    catalog = get_catalog(catalog)

    max_output, max_memory = check_limits(max_output, max_memory, isolated=True)
    if max_steps is not None:
        max_steps = check_whole(max_steps, "max_steps")
    # The default total adds worker startup time to a validated execution budget.
    checked_timeout = check_timeout(
        timeout, ceiling=_TIMEOUT_CEILING + _ISOLATED_TIMEOUT
    )
    execution_timeout = check_timeout(execution_timeout)
    preparation_timeout = check_timeout(preparation_timeout)
    if checked_timeout is None:
        raise with_hint(
            exceptions.ArgumentError("isolated execution requires a finite timeout"),
            ("set a positive finite timeout, for example timeout=5.0"),
        )
    timeout = checked_timeout
    name = catalog.resolve(language)
    check_worker_runtime(name, catalog)
    settings, scale = _check_source_options(
        name, program, settings, scale, catalog=catalog, _loaded=_loaded
    )
    seed = check_seed(seed)
    check_seed_for(name, seed, catalog=catalog)
    if not catalog.languages[name].runtime.reads_stdin:
        stdin = ""
    started = _ACQUISITION_STARTED.get()
    if started is None:
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

    def capture(stopped: Callable[[], bool]) -> str | list[str] | None:
        with stream_read_deadline(acquisition_deadline):
            checked_input = check_input(stdin)
            if stopped():
                return None
            artifact = _loaded
            if artifact is None:
                artifact = check_program(
                    name,
                    program,
                    settings=settings,
                    catalog=catalog,
                    _settings_validated=True,
                )
            if stopped():
                return None
            retained_scale = effective_scale(name, artifact, scale, catalog=catalog)
            check_scale_for(name, retained_scale, catalog=catalog)
            if stopped():
                return None
            wire = encode_request(
                name,
                artifact.source,
                "",
                settings=artifact.settings,
                seed=seed,
                scale=retained_scale,
                max_memory=max_memory,
                max_output=max_output,
                max_steps=max_steps,
                report_prepared=(
                    preparation_deadline is not None or execution_timeout is not None
                ),
                termination=termination,
                catalog=catalog,
                _settings_validated=True,
                chunked=True,
                stopped=stopped,
            )
            if stopped():
                return None
            wire["stdin"] = read_input(
                checked_input, frame=_artifact_input_frame(artifact, catalog)
            )
        return worker_request(wire, stopped)

    def expired() -> exceptions.ExecutionTimeoutError:
        if preparation_deadline == acquisition_deadline < deadline:
            return preparation_expired()
        error = exceptions.ExecutionTimeoutError(
            "execution timed out while loading input"
        )
        if execution_deadline == acquisition_deadline < deadline:
            error.bound = "execution_timeout"
        return error

    request = acquire(capture, acquisition_deadline, expired, clock=monotonic)
    with _timeout_named(timeout):
        if preparation_deadline is None and execution_timeout is None:
            result = _launch(request, deadline, max_output=max_output)
        else:
            result = _launch(
                request,
                deadline,
                max_output=max_output,
                preparation_deadline=preparation_deadline,
                execution_timeout=execution_timeout,
            )
    if (
        isinstance(result, ExecutionOutcome)
        and isinstance(result.error, exceptions.ExecutionTimeoutError)
        and result.bound == "total_timeout"
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
        if error.bound == "total_timeout":
            error.args = (f"execution exceeded the {timeout}-second timeout",)
        raise


def _launch(
    request: Sequence[str],
    deadline: float,
    *,
    max_output: int | None = None,
    preparation_deadline: float | None = None,
    execution_timeout: float | None = None,
) -> _WorkerResponse:
    """Run one JSON request, killing and reaping on deadline."""
    env = {
        name: value
        for name, value in os.environ.items()
        if not (sys.flags.ignore_environment and name.startswith("PYTHON"))
    }
    env.pop("PYTHONPATH", None)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONINTMAXSTRDIGITS"] = str(sys.get_int_max_str_digits())
    # Use the running interpreter's effective cache policy, which may have
    # come from command-line flags or changed since startup.
    for name, value in (
        ("PYTHONDONTWRITEBYTECODE", "1" if sys.dont_write_bytecode else None),
        ("PYTHONPYCACHEPREFIX", sys.pycache_prefix),
        ("PYTHONOPTIMIZE", str(sys.flags.optimize) if sys.flags.optimize else None),
    ):
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    # Match the importer's string-only search without embedding custom reprs.
    search_path = [str.__str__(path) for path in sys.path if isinstance(path, str)]
    # Site hooks run before the worker can restore the parent's search path.
    startup_flags = ["-P"]
    if sys.flags.no_site:
        startup_flags.append("-S")
    if sys.flags.no_user_site:
        startup_flags.append("-s")
    phased = preparation_deadline is not None or execution_timeout is not None
    streaming = max_output is not None or phased or not isinstance(request, str)
    with subprocess.Popen(  # fixed executable and code, no shell.
        [
            sys.executable,
            *startup_flags,
            "-c",
            f"import sys; sys.path[:] = {search_path!r}; "
            "from esolangs.runtime._worker_main import _worker; "
            f"sys.setrecursionlimit({sys.getrecursionlimit()}); _worker()",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL if streaming else subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    ) as child:
        try:
            now = monotonic()
            if now >= deadline or (
                preparation_deadline is not None and now >= preparation_deadline
            ):
                child.kill()
                output, _stderr = child.communicate()
                result = _decode_outcome(output, expired=True)
                if preparation_deadline is not None and preparation_deadline < deadline:
                    raise preparation_expired(partial_output=result.observation.output)
                return result
            if phased:
                return _bounded_output(
                    child,
                    request,
                    deadline,
                    preparation_deadline=preparation_deadline,
                    execution_timeout=execution_timeout,
                )
            if max_output is not None or not isinstance(request, str):
                return _bounded_output(child, request, deadline)
            output, expired = communicate(child, request, deadline, clock=monotonic)
        except KeyboardInterrupt:
            if child.poll() is None:
                child.kill()
                child.wait()
            raise
    return _decode_outcome(output, expired=expired)


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


if __name__ == "__main__":
    from esolangs.runtime._worker_main import _worker

    _worker()
