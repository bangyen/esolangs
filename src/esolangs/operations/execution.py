"""Execute source through native, cooperative or isolated routes."""

from collections.abc import Callable
from functools import partial

from esolangs.debugger import make_debugger
from esolangs.exceptions import EsolangError, ExecutionTimeoutError
from esolangs.operations.source import _check_program
from esolangs.registry import LANGUAGES, resolve
from esolangs.results import ExecutionResult
from esolangs.runtime._context import ExecutionContext
from esolangs.runtime._execution import (
    check_signal_timeout,
    interpreter_module,
    prepare_call,
    run_prepared,
)
from esolangs.runtime._input import InputSource
from esolangs.runtime._isolated import check_limits
from esolangs.runtime._isolated import run_isolated_result as _run_isolated_result
from esolangs.runtime._source import ProgramSource, check_scale_for, effective_scale
from esolangs.runtime._validate import (
    check_flag,
    check_seed,
    check_timeout,
    check_whole,
)
from esolangs.runtime.io import ScriptedIO
from esolangs.settings import DialectSettings, dialect_options, effective_settings
from esolangs.vm import _capture_observation, _capture_result

io_factory: Callable[[InputSource], ScriptedIO] = ScriptedIO

_ISOLATED_TIMEOUT = 30.0


def _run_bounded_result(
    language: str,
    program: ProgramSource,
    stdin: InputSource = "",
    *,
    max_steps: int,
    settings: DialectSettings | None = None,
    timeout: float | None = None,
    scale: int | None = None,
    seed: int | None = None,
) -> ExecutionResult:
    """Execute cooperatively, returning a result only after completed halt.

    Supply at least one bound. Limits raise :class:`ExecutionTimeoutError`
    with ``partial_output``. Works on Windows and worker threads; loading
    and individual steps cannot be interrupted.
    """
    check_whole(max_steps, "max_steps")
    check_timeout(timeout)
    debugger = make_debugger(
        language, program, stdin=stdin, scale=scale, settings=settings, seed=seed
    )
    try:
        reason = debugger.run(max_steps=max_steps, timeout=timeout)
    except EsolangError as exc:
        exc.partial_output = debugger.output
        observation = exc.execution or _capture_observation(debugger.vm)
        exc.execution = observation._replace(steps=debugger._steps)  # noqa: SLF001
        raise
    if reason != "halted":
        # One wording per bound: a timeout reads as it does unstepped.
        error = ExecutionTimeoutError(
            f"execution exceeded the {timeout}-second timeout"
            if reason == "timeout"
            else f"execution stopped at the {reason} bound"
        )
        error.partial_output = debugger.output
        error.bound = "timeout" if reason == "timeout" else "max_steps"
        error.execution = _capture_observation(debugger.vm)._replace(
            steps=debugger._steps  # noqa: SLF001
        )
        raise error
    return _capture_result(debugger.vm)._replace(steps=debugger._steps)  # noqa: SLF001


def run(
    language: str,
    program: ProgramSource,
    *,
    stdin: InputSource = "",
    timeout: float | None = None,
    seed: int | None = None,
    isolated: bool = False,
    max_steps: int | None = None,
    scale: int | None = None,
    max_output: int | None = None,
    max_memory: int | None = None,
    settings: DialectSettings | None = None,
) -> ExecutionResult:
    """Execute ``program`` and return output, input usage and completion evidence.

    Args:
        program: Source or a :class:`~pathlib.Path`; a string shaped like a
            filename is refused.  A file loses one trailing newline and has
            CRLF and lone CR read as LF; a string keeps both.  Bytes hold UTF-8
            text or PNG; a readable stream is consumed from its current
            position and left open.
        stdin: Consumed verbatim in the language's input unit, without
            Boolean validation; binary is decoded as UTF-8.  Build a
            Boolean-generated program's stdin with :func:`encode_inputs`,
            which validates the bits.
        timeout: Wall-clock seconds (None: unbounded), via ``SIGALRM``, so it
            needs a Unix main thread; off it, use ``isolated`` or
            ``max_steps``.
        seed: Integer fixing the languages that draw
            (``describe(language)["random"]``); the rest refuse it.
        isolated: Run in a subprocess whose deadline covers startup and
            loading (``timeout``, or 30 seconds when None); works on Windows
            and in worker threads. Can combine with ``max_steps``.
        max_steps: Cooperative stepping bound, for text and raster programs;
            ``timeout`` then excludes loading and cannot interrupt a single
            step. With isolation, the worker also enforces its wall-clock
            deadline.
        scale: Raster scale factor; detected when None.
        max_output: Isolated output cap in Unicode characters (zero allowed);
            the prefix is kept.
        max_memory: Linux worker virtual address space cap in bytes, including
            Python overhead; other platforms refuse it.  Loading in the
            parent is not capped.
        settings: Dialect choices.  Artifacts retain their own; these
            override individual ones.  Plain source uses these.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ArgumentError: An option is invalid or inapplicable
            (for example, ``seed`` for a deterministic language).
        ProgramNotFoundError: ``program`` is a Path that does not exist.
        ProgramError: The program does not load (base of the above).
        TemplateError: ``program`` is an unfilled template; see
            :func:`instantiate`.
        InputExhaustedError: A read past the end of ``stdin``.  Languages with
            ``describe(language)["eof_is_a_value"]`` supply a value instead,
            and some halt.
        ExecutionTimeoutError: ``timeout`` elapsed or ``max_steps`` ran out.
            Also a :class:`TimeoutError` and a ``HaltError``; catch it, not the
            base.
        InterpreterLimitError: ``max_output`` was exceeded, or the interpreter
            hit another implementation limit.
        HaltError: The program halted on an invalid operation (base of the two
            above).
        MissingDependencyError: The language needs an uninstalled extra
            (``esolangs[image]`` for PNG).
    """
    return _run_result(
        language,
        program,
        stdin=stdin,
        timeout=timeout,
        seed=seed,
        isolated=isolated,
        max_steps=max_steps,
        scale=scale,
        max_output=max_output,
        max_memory=max_memory,
        settings=settings,
    )


def _run_result(
    language: str,
    program: ProgramSource,
    *,
    stdin: InputSource = "",
    timeout: float | None = None,
    seed: int | None = None,
    isolated: bool = False,
    max_steps: int | None = None,
    scale: int | None = None,
    max_output: int | None = None,
    max_memory: int | None = None,
    settings: DialectSettings | None = None,
) -> ExecutionResult:
    """Execute through one route, retaining its result metadata."""
    settings = effective_settings(language, program, settings)
    scale = effective_scale(language, program, scale)
    dialect_options(language, settings)  # validate before any route
    check_scale_for(language, scale)
    check_seed(seed)
    check_timeout(timeout)
    check_flag(isolated, "isolated")
    check_limits(max_output, max_memory, isolated=isolated)
    if max_steps is not None:
        check_whole(max_steps, "max_steps")
    if isolated:
        deadline = _ISOLATED_TIMEOUT if timeout is None else timeout
        # Every option defaults to None, so passing them unconditionally
        # matches the old per-combination cascade exactly.
        return _run_isolated_result(
            language,
            program,
            stdin,
            deadline,
            seed=seed,
            scale=scale,
            max_output=max_output,
            max_memory=max_memory,
            settings=settings,
            max_steps=max_steps,
        )
    if max_steps is not None:
        return _run_bounded_result(
            language,
            program,
            stdin,
            max_steps=max_steps,
            timeout=timeout,
            scale=scale,
            settings=settings,
            seed=seed,
        )
    # Before ``_run``, so every ValueError from the run is the
    # interpreter's.  The message names both routes out for a worker
    # thread.  Not a silent fallback to stepping: two paths for one
    # function is how they diverged (``tests/runtime/test_stepping_parity.py``).
    check_signal_timeout(
        timeout,
        "the timeout guard uses SIGALRM and needs a Unix main thread; "
        "off it, either pass isolated=True, which times a subprocess, or "
        "bound the run cooperatively with "
        "esolangs.debugger.make_debugger(language, program, stdin)"
        ".run(timeout=...), "
        "which steps and so needs no signal",
    )
    name = resolve(language)
    artifact = _check_program(name, program, stdin)
    settings = effective_settings(name, artifact, settings)
    scale = effective_scale(language, artifact, scale)
    program = artifact.source
    entrypoint = LANGUAGES[name].runtime.completion_entrypoint
    run_fn = getattr(interpreter_module(name), entrypoint)
    program_args, options = prepare_call(
        name, program, ExecutionContext(scale=scale, seed=seed, settings=settings)
    )
    if options:
        run_fn = partial(run_fn, **options)
    io_obj = io_factory(stdin)
    return run_prepared(
        name,
        run_fn,
        program_args,
        io_obj,
        timeout,
    )
