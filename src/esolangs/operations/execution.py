"""Execute source through native, cooperative or isolated routes."""

from collections.abc import Callable

from esolangs.exceptions import ArgumentError, ExecutionTimeoutError
from esolangs.limits import ExecutionLimits
from esolangs.outcomes import ExecutionOutcome, _capture_outcome
from esolangs.registry._catalog import Catalog
from esolangs.results import ExecutionResult
from esolangs.runtime._controller import ExecutionController
from esolangs.runtime._execution import (
    check_seed_for,
    check_signal_timeout,
    interpreter_module,
)
from esolangs.runtime._input import InputSource
from esolangs.runtime._isolated import check_limits
from esolangs.runtime._isolated import execute_isolated as _execute_isolated
from esolangs.runtime._prepared import PreparedProgram, prepare_program
from esolangs.runtime._source import ProgramSource, check_scale_for, effective_scale
from esolangs.runtime._validate import (
    check_flag,
    check_seed,
    check_timeout,
    check_whole,
)
from esolangs.runtime.io import ScriptedIO
from esolangs.settings import DialectSettings, dialect_options, effective_settings
from esolangs.vm import _make_vm

_ISOLATED_TIMEOUT = 30.0


@_capture_outcome
def _execute_bounded(
    language: str,
    program: ProgramSource,
    stdin: InputSource = "",
    *,
    max_steps: int,
    settings: DialectSettings | None = None,
    timeout: float | None = None,
    scale: int | None = None,
    seed: int | None = None,
    catalog: "Catalog | None" = None,
    io_factory: Callable[[InputSource], ScriptedIO] = ScriptedIO,
    prepared: PreparedProgram | None = None,
) -> ExecutionOutcome:
    """Execute cooperatively; loading and individual steps cannot be interrupted."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    check_whole(max_steps, "max_steps")
    check_timeout(timeout)
    controller = ExecutionController(
        _make_vm(
            language,
            program,
            stdin=stdin,
            scale=scale,
            settings=settings,
            seed=seed,
            catalog=catalog,
            io_factory=io_factory,
            prepared=prepared,
        )
    )
    return controller._execute(max_steps=max_steps, timeout=timeout)  # noqa: SLF001


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
    catalog: "Catalog | None" = None,
) -> ExecutionResult:
    """Execute ``program`` and return output, input usage and completion evidence.

    Args:
        program: Literal source or a :class:`~pathlib.Path` naming a file.
            Text retains line endings and terminators in every container.
            Bytes hold UTF-8 text or PNG; a readable stream is consumed from
            its current position and left open. Use ``Language.from_file``
            with ``normalize=True`` for native newline handling.
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
    return _execute_invocation(
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
        catalog=catalog,
    ).unwrap()


@_capture_outcome
def _execute_invocation(
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
    catalog: "Catalog | None" = None,
    io_factory: Callable[[InputSource], ScriptedIO] = ScriptedIO,
    prepared: PreparedProgram | None = None,
    execution_timeout: float | None = None,
    preparation_timeout: float | None = None,
) -> ExecutionOutcome:
    """Execute through one route, retaining its result metadata."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    settings = effective_settings(language, program, settings, catalog=catalog)
    scale = effective_scale(language, program, scale, catalog=catalog)
    dialect_options(language, settings, catalog=catalog)  # validate before any route
    check_scale_for(language, scale, catalog=catalog)
    check_seed(seed)
    check_seed_for(catalog.resolve(language), seed, catalog=catalog)
    check_timeout(timeout)
    check_flag(isolated, "isolated")
    check_limits(max_output, max_memory, isolated=isolated)
    if max_steps is not None:
        check_whole(max_steps, "max_steps")
    if isolated:
        if io_factory is not ScriptedIO:
            raise ArgumentError("custom I/O factories require in-process execution")
        deadline = _ISOLATED_TIMEOUT if timeout is None else timeout
        # Every option defaults to None, so passing them unconditionally
        # matches the old per-combination cascade exactly.
        return _execute_isolated(
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
            execution_timeout=execution_timeout,
            preparation_timeout=preparation_timeout,
            catalog=catalog,
        )
    if max_steps is not None:
        return _execute_bounded(
            language,
            program,
            stdin,
            max_steps=max_steps,
            timeout=timeout,
            scale=scale,
            settings=settings,
            seed=seed,
            catalog=catalog,
            io_factory=io_factory,
            prepared=prepared,
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
    if prepared is None:
        prepared = prepare_program(
            language,
            program,
            settings=settings,
            scale=scale,
            catalog=catalog,
            module_loader=interpreter_module,
        )
    from esolangs.runtime._input import check_input

    check_input(stdin)
    return prepared._execute_native(  # noqa: SLF001
        stdin, timeout=timeout, seed=seed, io_factory=io_factory
    )


@_capture_outcome
def _execute_outcome(
    language: str,
    program: ProgramSource,
    *,
    stdin: InputSource = "",
    limits: ExecutionLimits | None = None,
    seed: int | None = None,
    isolated: bool = False,
    settings: DialectSettings | None = None,
    scale: int | None = None,
    catalog: Catalog | None = None,
    prepared: PreparedProgram | None = None,
) -> ExecutionOutcome:
    """Apply explicit phase budgets and retain one outcome across all routes."""
    selected = ExecutionLimits() if limits is None else limits
    if not isinstance(selected, ExecutionLimits):
        raise ArgumentError("limits must be ExecutionLimits or None")
    check_flag(isolated, "isolated")
    use_worker = isolated or any(
        value is not None
        for value in (
            selected.total_timeout,
            selected.max_output,
            selected.max_memory,
        )
    )
    preparation_timeout = selected.preparation_timeout
    if prepared is not None and not use_worker:
        preparation_timeout = None
    use_worker = use_worker or preparation_timeout is not None
    outcome = _execute_invocation(
        language,
        program,
        stdin=stdin,
        timeout=selected.total_timeout if use_worker else selected.execution_timeout,
        execution_timeout=selected.execution_timeout if use_worker else None,
        preparation_timeout=preparation_timeout,
        seed=seed,
        isolated=use_worker,
        max_steps=selected.max_steps,
        max_output=selected.max_output,
        max_memory=selected.max_memory,
        settings=settings,
        scale=scale,
        catalog=catalog,
        prepared=prepared,
    )
    if isinstance(outcome.error, ExecutionTimeoutError) and outcome.bound == "timeout":
        outcome.error.bound = "total_timeout" if use_worker else "execution_timeout"
    return outcome
