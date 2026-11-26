"""Execute source through native, cooperative or isolated routes."""

from collections.abc import Callable

from esolangs.artifacts import ProgramArtifact
from esolangs.exceptions import ArgumentError
from esolangs.limits import ExecutionLimits
from esolangs.operations.prepared import PreparedProgram
from esolangs.outcomes import ExecutionOutcome, _capture_outcome
from esolangs.registry._catalog import Catalog
from esolangs.runtime._acquire import PendingInput, bind_prepared_input
from esolangs.runtime._controller import ExecutionController
from esolangs.runtime._execution import (
    check_seed_for,
    interpreter_module,
)
from esolangs.runtime._input import InputSource, check_input
from esolangs.runtime._isolated import check_limits
from esolangs.runtime._isolated import execute_isolated as _execute_isolated
from esolangs.runtime._prepared import (
    _check_source_options,
    _prepare_checked_program,
    _PreparedRuntime,
    _runtime_reads_stdin,
    prepare_program,
)
from esolangs.runtime._program import Program
from esolangs.runtime._source import ProgramSource, anchor_program_source
from esolangs.runtime._validate import (
    _ISOLATED_TIMEOUT,
    _has_backing_type,
    check_flag,
    check_seed,
    check_timeout,
    check_whole,
)
from esolangs.runtime.io import ScriptedIO
from esolangs.settings import DialectSettings
from esolangs.vm import _make_checked_vm


def default_total(total: float | None, execution: float | None) -> float:
    """Return the worker's whole-invocation deadline.

    Absent a total, loading gets 30 seconds on top of the execution budget; a
    flat 30 cut a 33-second execution deadline short at 30.0 seconds.
    """
    if total is not None:
        return total
    return _ISOLATED_TIMEOUT + (0.0 if execution is None else execution)


def _execute_loaded(
    program: ProgramArtifact[Program],
    *,
    stdin: InputSource,
    limits: ExecutionLimits,
    seed: int | None,
    isolated: bool,
    scale: int | None,
    catalog: Catalog,
) -> ExecutionOutcome:
    """Run the native snapshot already validated before CLI stdin acquisition."""
    return _execute_outcome(
        program.language,
        program,
        stdin=stdin,
        limits=limits,
        seed=seed,
        isolated=isolated,
        scale=scale,
        catalog=catalog,
        _loaded=program,
    )


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
    prepared: _PreparedRuntime | None = None,
    execution_timeout: float | None = None,
    preparation_timeout: float | None = None,
    _loaded: ProgramArtifact[Program] | None = None,
) -> ExecutionOutcome:
    """Execute through one route, retaining its result metadata."""
    from esolangs.registry._catalog import get_catalog

    program = anchor_program_source(program)
    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    if not isolated:
        if prepared is None:
            settings, scale = _check_source_options(
                name, program, settings, scale, catalog=catalog, _loaded=_loaded
            )
        seed = check_seed(seed)
        check_seed_for(name, seed, catalog=catalog)
    timeout = check_timeout(timeout)
    check_flag(isolated, "isolated")
    max_output, max_memory = check_limits(max_output, max_memory, isolated=isolated)
    if max_steps is not None:
        max_steps = check_whole(max_steps, "max_steps")
    if isolated:
        if io_factory is not ScriptedIO:
            raise ArgumentError("custom I/O factories require in-process execution")
        deadline = default_total(timeout, execution_timeout)
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
            _loaded=_loaded,
        )
    if not _runtime_reads_stdin(catalog.languages[name].runtime):
        stdin = ""
    checked = (
        check_input(stdin)
        if preparation_timeout is None or prepared is None
        else bind_prepared_input(stdin, preparation_timeout)
    )
    if prepared is None and (max_steps is None or _loaded is not None):
        prepared = _prepare_checked_program(
            _PreparedRuntime,
            name,
            program,
            settings=settings,
            scale=scale,
            catalog=catalog,
            module_loader=interpreter_module,
            _loaded=_loaded,
        )
    if max_steps is not None:
        if isinstance(checked, PendingInput):
            assert prepared is not None
            checked = checked.snapshot(frame=prepared._input_frame)  # noqa: SLF001
        machine = _make_checked_vm(
            name,
            program,
            stdin=checked,
            scale=scale,
            settings=settings,
            seed=seed,
            catalog=catalog,
            io_factory=io_factory,
            prepared=prepared,
            reproducible=False,
        )
        return ExecutionController(machine)._execute(max_steps=max_steps)  # noqa: SLF001
    assert prepared is not None
    return prepared._execute_native(  # noqa: SLF001
        checked, seed=seed, io_factory=io_factory
    )


def _execution_route(
    limits: ExecutionLimits, *, isolated: bool, prepared: bool
) -> tuple[bool, float | None]:
    """Select a worker unless only fresh stdin needs a preparation budget."""
    use_worker = isolated or any(
        value is not None
        for value in (
            limits.execution_timeout,
            limits.total_timeout,
            limits.max_output,
            limits.max_memory,
        )
    )
    preparation_timeout = limits.preparation_timeout
    return (
        use_worker or (not prepared and preparation_timeout is not None),
        preparation_timeout,
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
    prepared: _PreparedRuntime | None = None,
    _loaded: ProgramArtifact[Program] | None = None,
) -> ExecutionOutcome:
    """Apply explicit phase budgets and retain one outcome across all routes."""
    selected = ExecutionLimits() if limits is None else limits
    if not _has_backing_type(selected, ExecutionLimits):
        raise ArgumentError("limits must be ExecutionLimits or None")
    check_flag(isolated, "isolated")
    use_worker, preparation_timeout = _execution_route(
        selected, isolated=isolated, prepared=prepared is not None
    )
    return _execute_invocation(
        language,
        program,
        stdin=stdin,
        timeout=selected.total_timeout,
        execution_timeout=selected.execution_timeout,
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
        _loaded=_loaded,
    )


def run(
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
) -> ExecutionOutcome:
    """Return completion, rejection, input exhaustion, fault or limit evidence.

    Use ``outcome.unwrap()`` for the result or original execution error.

    Args:
        program: Literal source or a :class:`~pathlib.Path` naming a file.
            Text retains line endings and terminators in every container.
            Bytes hold UTF-8 text or PNG; a readable stream is consumed from
            its current position and left open. Use ``Language.from_file``
            with ``normalize=True`` for native newline handling.
        stdin: Consumed verbatim in the language's input unit, without
            Boolean validation; binary is decoded as UTF-8. Installed hooks
            leave stdin untouched when the runtime declares no stdin. Build a
            Boolean-generated program's stdin with :func:`encode_inputs`,
            which validates the bits.
        limits: :class:`ExecutionLimits`; None is unbounded.  Every budget but
            ``max_steps`` selects isolation.
        seed: Integer fixing the languages that draw
            (``describe(language).random``); the rest refuse it.
        isolated: Run in a subprocess whose deadline covers startup and
            loading (30 seconds plus any ``execution_timeout``); works on
            Windows and in worker threads.  The catalog must match installed
            runtimes.
        settings: Dialect choices for plain source or choices the artifact
            does not retain. Conflicts return a rejected outcome with ProgramError.
        scale: Raster scale factor; detected when None.
    """
    return _execute_outcome(
        language,
        program,
        stdin=stdin,
        limits=limits,
        seed=seed,
        isolated=isolated,
        settings=settings,
        scale=scale,
        catalog=catalog,
    )


def prepare(
    language: str,
    program: ProgramSource,
    *,
    settings: DialectSettings | None = None,
    scale: int | None = None,
    catalog: Catalog | None = None,
) -> PreparedProgram:
    """Load reusable source; each run or VM owns fresh IO, state and randomness.

    Arguments: :func:`esolangs.run`.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ArgumentError: ``settings`` or ``scale`` is invalid or inapplicable.
        ProgramError: The program does not load.
        TemplateError: ``program`` is an unfilled template.
    """
    return prepare_program(
        PreparedProgram,
        language,
        program,
        settings=settings,
        scale=scale,
        catalog=catalog,
        bind_machine=True,
    )
