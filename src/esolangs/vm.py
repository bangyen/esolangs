"""A step-and-inspect interface for the interpreter suite.

:func:`make_vm` wraps a registered interpreter in a
:class:`~esolangs.runtime._vm_protocol.VM` exposing the run state;
``ip``/``memory``/``stack`` are language-shaped.

Three conventions defeat ``while not vm.halted: vm.step()``, so the VM
reports them: ``self_halts`` (``halted`` never becomes true),
``dumps_on_the_post_halt_step`` (output lands one step after the halt),
and ``steppable_to_answer`` (use :func:`esolangs.run` where it is false).

The five hang detectors -- :func:`run_until_halt_or_cycle`,
:func:`run_until_halt_or_all_branches_cycle`,
:func:`run_until_halt_or_ancestor`, :func:`run_until_halt_or_growth`,
:func:`run_until_halt_or_value_growth` -- take a
:class:`~esolangs.runtime._vm_protocol.VM` or the state it wraps, and raise
:class:`TypeError` for a language lacking their
sub-protocol.  :func:`run_until_halt` proves nothing.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Hashable
from contextlib import AbstractContextManager
from dataclasses import replace
from functools import partial
from inspect import getattr_static
from types import FunctionType, ModuleType
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

import esolangs._cycles as _cycles
from esolangs._cycles import _check_driver, _check_driver_fields, _drive_until_halt
from esolangs._cycles import (
    run_until_halt as run_until_halt,
)
from esolangs._cycles import (
    run_until_halt_or_all_branches_cycle as run_until_halt_or_all_branches_cycle,
)
from esolangs._cycles import (
    run_until_halt_or_ancestor as run_until_halt_or_ancestor,
)
from esolangs._cycles import (
    run_until_halt_or_cycle as run_until_halt_or_cycle,
)
from esolangs._cycles import (
    run_until_halt_or_growth as run_until_halt_or_growth,
)
from esolangs._cycles import (
    run_until_halt_or_value_growth as run_until_halt_or_value_growth,
)
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    InterpreterLimitError,
    steps_exhausted,
)
from esolangs.registry._catalog import Catalog
from esolangs.results import ExecutionResult
from esolangs.runtime._capabilities import IpShape as _IpShape
from esolangs.runtime._drive import (
    PeriodicMachine,
    _check_snapshot_hash,
    _SnapshotUnavailableError,
    drive_periodic,
    drive_until_repeat,
    finalize,
)
from esolangs.runtime._execution import (
    check_seed_for,
    interpreter_errors,
    interpreter_module,
)
from esolangs.runtime._input import CheckedInput, InputSource, check_input
from esolangs.runtime._lifecycle import Completion, CompletionReport
from esolangs.runtime._source import ProgramSource
from esolangs.runtime._state import WorkspaceSnapshot
from esolangs.runtime._traits import trait, traits
from esolangs.runtime._validate import check_seed, check_whole
from esolangs.runtime._vm_protocol import VM
from esolangs.runtime._vm_views import machine_views
from esolangs.runtime.io import ScriptedIO, _scripted_io
from esolangs.settings import DialectSettings

if TYPE_CHECKING:
    # A runtime import would close the cycle PreparedProgram.make_debugger opens.
    from esolangs.runtime._prepared import PreparedProgram


def complete_vm(vm: VM, max_steps: int | None = 100_000) -> str:
    """Return finalized raw output after a proved halt, including a final dump.

    An exhausted step budget retains the unfinished IO observation. Faults
    observed by this VM include the commands completed during this call.
    An active machine must be able to self-halt. Repeated completion is safe:
    the post-halt step is idempotent by the VM contract.
    """
    if max_steps is not None:
        max_steps = check_whole(max_steps, "max_steps")
    _check_driver(vm, "vm", "self_halts")
    if not vm.self_halts and not vm.halted:
        raise ArgumentError("completion requires a machine that self-halts")
    steps = _drive_until_halt(vm, max_steps, on_fault=partial(_retain_fault_steps, vm))
    if steps is None:
        _check_driver_fields(vm, "vm", "output")
        error = steps_exhausted("VM completion exhausted max_steps")
        # Without a stop predicate, an active return has used the full budget.
        error.observation = replace(_capture_observation(vm), steps=max_steps)
        error.partial_output = error.observation.output
        raise error
    _check_driver_fields(vm, "vm", "dumps_on_the_post_halt_step")
    dump_pending = vm.dumps_on_the_post_halt_step and not _post_halt_dumped(vm)
    try:
        finalize(vm, policy=Completion.POST_HALT if dump_pending else Completion.HALTED)
    except EsolangError as error:
        _retain_fault_steps(vm, error, steps)
        raise
    _check_driver_fields(vm, "vm", "output")
    return vm.output


def _retain_fault_steps(vm: VM, error: EsolangError, steps: int) -> None:
    """Add measured commands to a fault observed by this VM."""
    if error.observation is not None:
        owner = _controller_vm(vm)
        observation = replace(error.observation, steps=steps)
        if isinstance(owner, _DelegatingVM):
            _record_vm_fault(owner, error, observation)
        else:
            error.observation = observation


class _DelegatingVM:
    """Wrap a registered interpreter, copying its exposed memory and stack."""

    _machine: _cycles._StepMachine
    _fault_observation: ExecutionResult | None = None
    _halt_fault: EsolangError | None = None
    _replayed_halt_fault = False

    def __init__(
        self,
        language: str,
        program: PreparedProgram,
        stdin: CheckedInput = "",
        *,
        seed: int | None = None,
        reproducible: bool = True,
        observe_initialization: bool = False,
        catalog: Catalog | None = None,
        io_factory: Callable[[InputSource], ScriptedIO] = ScriptedIO,
    ) -> None:
        from esolangs.registry._catalog import get_catalog

        catalog = get_catalog(catalog)
        self.language = language
        self._io = _scripted_io(stdin, io_factory)
        runtime = catalog.languages[language].runtime
        self._runtime = runtime
        self._capabilities = runtime.capabilities
        self._random = runtime.random
        # None denotes other completion policies.
        self._dump_pending: bool | None = (
            True if self._capabilities.completion is Completion.POST_HALT else None
        )
        with interpreter_errors(
            f"the {language} interpreter recursed deeper than CPython's stack "
            "limit allows while loading this program",
            self._io,
            language=language,
            omit_empty_io=not observe_initialization,
        ):
            factory = program._factory(  # noqa: SLF001
                seed=seed, reproducible=reproducible
            )
            machine = factory(self._io)
            _check_driver(
                machine,
                f"{language}'s machine factory result",
                error_type=InterpreterLimitError,
            )
            self._machine = machine

    @property
    def output(self) -> str:
        return self._io.getvalue()

    def _result(self, report: CompletionReport | None) -> ExecutionResult:
        """Capture public output with this VM's owned input counters."""
        return ExecutionResult(
            self.output,
            self._io.position(),
            self._io.reads,
            self._io.past_end,
            completion=report,
        )

    def _remember_fault(self, observation: ExecutionResult) -> None:
        self._fault_observation = observation

    def _interpreter_errors(self) -> AbstractContextManager[None]:
        return interpreter_errors(
            f"the {self.language} interpreter recursed deeper than "
            "CPython's stack limit allows on this program",
            self._io,
            language=self.language,
            on_observation=self._remember_fault,
        )

    @property
    def halted(self) -> bool:
        try:
            return self._machine.halted
        except Exception:
            with self._interpreter_errors():
                raise

    def step(self) -> None:
        """Execute one instruction, translating what the interpreter raises.

        The same promise as :func:`esolangs.run`: a bare ``ValueError``
        becomes :class:`~esolangs.exceptions.ProgramError`, a
        ``RecursionError`` :class:`~esolangs.exceptions.InterpreterLimitError`.
        """
        dumping: bool | None = False
        started = False
        try:
            dumping = self._dump_pending and self._machine.halted
            started = True
            self._machine.step()
        except Exception:
            # Translation is needed only on failure; a context per instruction
            # dominated the wrapper cost in the generator-size sweep.
            try:
                with self._interpreter_errors():
                    raise
            except EsolangError as error:
                # A pending dump can be retried. A failed command that moved
                # the machine to its halt position supplies no completion.
                if (
                    started
                    and not dumping
                    and self._dump_pending is not False
                    and self._halt_fault is None
                ):
                    try:
                        if self._machine.halted:
                            self._halt_fault = error
                    except Exception:
                        # A failed inspection cannot replace the command fault.
                        pass
                raise
        if dumping:
            self._dump_pending = False

    def _complete_repeating(self, step: Callable[[], None]) -> CompletionReport | None:
        """Retain the declared run boundary for periodic execution."""
        machine = self._machine
        exact_repeat = self._capabilities.complete_on_exact_repeat
        if not exact_repeat and self.steppable_to_answer:
            return None
        with self._interpreter_errors():
            if exact_repeat:
                return drive_until_repeat(machine, step=step)
            stride = getattr(machine, "commands_per_pass", None)
            try:
                stride = check_whole(stride, "commands_per_pass")
            except ArgumentError as error:
                raise InterpreterLimitError(
                    "periodic execution requires a nonnegative integer pass stride"
                ) from error
            cycle = drive_periodic(
                cast(PeriodicMachine, machine),
                stride,
                policy=Completion.PERIODIC,
                step=step,
                check_each_snapshot=not self._uses_installed_snapshots(),
            )
        return CompletionReport(Completion.PERIODIC, cycle)

    def _uses_installed_snapshots(self) -> bool:
        """Recognize shipped stepping and snapshot code for the proof fast path."""
        from esolangs.registry._table import LANGUAGES

        declaration = LANGUAGES.get(self.language)
        if (
            declaration is None
            or declaration.runtime is not self._runtime
            or self._runtime.interpreter is None
        ):
            return False
        module = f"esolangs.languages.{self._runtime.interpreter}.interpreter"
        machine_type = type(self._machine)
        if type(machine_type) is not type:
            return False
        origin = machine_type.__module__
        if type(origin) is not str or (
            origin != module and not origin.startswith(f"{module}.")
        ):
            return False
        loaded = sys.modules.get(origin)
        if (
            type(loaded) is not ModuleType
            or vars(loaded).get(machine_type.__name__) is not machine_type
        ):
            return False
        for name in ("step", "snapshot"):
            hook = getattr_static(self._machine, name, None)
            if type(hook) is not FunctionType:
                return False
            origin = hook.__module__
            if type(origin) is not str or (
                origin != module and not origin.startswith(f"{module}.")
            ):
                return False
            loaded = sys.modules.get(origin)
            if type(loaded) is not ModuleType or hook.__globals__ is not vars(loaded):
                return False
        return True

    def snapshot(self) -> Hashable:
        """Return the underlying machine's complete hashable state."""
        return _check_snapshot_hash(self._snapshot_value(), ArgumentError)

    def _snapshot_value(self) -> Hashable:
        """Read a state for a consumer that handles its own evidence validation."""
        snapshot: Callable[[], Hashable] | None
        try:
            snapshot = self._machine.snapshot
        except AttributeError:
            snapshot = None
        if not callable(snapshot):
            raise _SnapshotUnavailableError(self)
        return snapshot()

    # The views come off the machine by ``getattr`` too, so a language
    # with no stack or no addressable cells says nothing, and one whose
    # position is a plain ``ind`` need not repeat it as ``ip``.

    def _view(self, name: str, default: object) -> Any:
        """Read the declared debug attribute, or the absent-view default."""
        debug = self._capabilities.debug
        attribute = getattr(debug, name) if debug is not None else None
        return getattr(self._machine, attribute) if attribute is not None else default

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        """The declared current code position, or ``None``."""
        return cast("int | tuple[int, ...] | None", self._view("ip", None))

    @property
    def memory(self) -> list[int]:
        """The addressable integer cells, or empty where there is no such store.

        Empty too where the store is not integer cells (Caballo's mapping,
        Crement's instructions, B-tapemark's grids): they leaked through as
        ``list[int]``, and ``break_on_cell`` could not name a value.
        """
        cells = list(self._view("memory", ()))
        if all(type(cell) is int for cell in cells):
            return cells
        return []

    @property
    def ptr(self) -> int | None:
        value = self._view("ptr", None)
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @property
    def stack(self) -> list[object]:
        """The stack, or empty where the language has none."""
        return list(self._view("stack", ()))

    @property
    def self_halts(self) -> bool:
        return trait(self._capabilities, "self_halts")

    @property
    def ip_shape(self) -> _IpShape:
        debug = self._capabilities.debug
        return debug.ip_shape if debug is not None else "offset"

    @property
    def views(self) -> tuple[tuple[str, str], ...]:
        debug = self._capabilities.debug
        return machine_views(self._machine, debug.views if debug is not None else ())

    @property
    def dumps_on_the_post_halt_step(self) -> bool:
        return self._dump_pending is not None

    @property
    def steppable_to_answer(self) -> bool:
        return trait(self._capabilities, "steppable_to_answer")

    @property
    def eof_is_a_value(self) -> bool:
        return trait(self._capabilities, "eof_is_a_value")


def _capture_result(vm: VM) -> ExecutionResult:
    """Capture a finalized, halted VM without taking another step."""
    _raise_halt_fault(vm)
    if not vm.halted:
        raise ArgumentError("execution result requires a halted VM")
    owner = _controller_vm(vm)
    if isinstance(owner, _DelegatingVM) and owner._dump_pending:  # noqa: SLF001
        raise ArgumentError("execution result requires a completed post-halt dump")
    report = CompletionReport(
        Completion.POST_HALT if vm.dumps_on_the_post_halt_step else Completion.HALTED
    )
    return _capture_observation(vm, report)


def _recorded_halt_fault(vm: object, *, replay: bool = False) -> EsolangError | None:
    """Find a registered or controller-observed fault at the live halt position."""
    if isinstance(vm, _DelegatingVM):
        fault = vm._halt_fault  # noqa: SLF001
        if replay and fault is not None:
            vm._replayed_halt_fault = True  # noqa: SLF001
        return fault

    from esolangs.runtime._controller import ExecutionController

    if isinstance(vm, ExecutionController):
        saved = vm._active_fault  # noqa: SLF001
        if saved is not None:
            wrapped, owner, error = saved
            # A caller can replace its VM or move it off its failed halt.
            if vm.vm is wrapped and _controller_vm(wrapped) is owner and vm.halted:
                return error
        return _recorded_halt_fault(vm.vm, replay=replay)
    return None


def _halt_faulted(vm: object) -> bool:
    """Whether the observed VM halted during a failing command."""
    return _recorded_halt_fault(vm) is not None


def _raise_halt_fault(vm: object) -> None:
    """Re-raise the original fault at a previously observed failed halt."""
    fault = _recorded_halt_fault(vm, replay=True)
    if fault is not None:
        raise fault


def _post_halt_dumped(vm: VM) -> bool:
    """Whether this VM or its controller chain observed a completed dump."""
    if isinstance(vm, _DelegatingVM):
        return vm._dump_pending is False  # noqa: SLF001

    from esolangs.runtime._controller import ExecutionController

    return isinstance(vm, ExecutionController) and vm._has_dumped()  # noqa: SLF001


def _controller_vm[T](vm: T) -> T | VM:
    """Find the VM whose state and I/O a library controller observes."""
    if isinstance(vm, _DelegatingVM):
        return vm
    from esolangs.runtime._controller import ExecutionController

    return _controller_vm(vm.vm) if isinstance(vm, ExecutionController) else vm


def _capture_observation(
    vm: VM, report: CompletionReport | None = None
) -> ExecutionResult:
    """Capture live IO without stepping or claiming output finalization."""
    owner = _controller_vm(vm)
    if isinstance(owner, _DelegatingVM):
        # Use owned code; unrelated instance attributes remain caller-owned.
        return _DelegatingVM._result(owner, report)  # noqa: SLF001
    return ExecutionResult(owner.output, None, None, None, completion=report)


def _record_vm_fault(vm: VM, error: EsolangError, observation: ExecutionResult) -> None:
    """Update a VM's own fault evidence while preserving a propagated error."""
    vm = _controller_vm(vm)
    if isinstance(vm, _DelegatingVM):
        # Another driver replaying an error executed no additional command.
        if vm._replayed_halt_fault and error is vm._halt_fault:  # noqa: SLF001
            return
        previous = error.observation
        if previous is not None and previous is not vm._fault_observation:  # noqa: SLF001
            return
        vm._remember_fault(observation)  # noqa: SLF001 - owned adapter
    error.observation = observation
    error.partial_output = observation.output


def _capture_workspace(vm: VM) -> WorkspaceSnapshot:
    """Require a registered interpreter's declared semantic accounting model."""
    if not isinstance(vm, _DelegatingVM):
        raise TypeError("workspace accounting requires a registered VM")
    machine = vm._machine  # noqa: SLF001 - owned adapter
    capture = getattr(type(machine), "workspace_snapshot", None)
    if not callable(capture):
        raise TypeError("workspace accounting requires workspace_snapshot")
    state = capture(machine)
    if not isinstance(state, WorkspaceSnapshot):
        raise TypeError("workspace_snapshot must return a WorkspaceSnapshot")
    return state


def machine_traits(language: str, *, catalog: Catalog | None = None) -> dict[str, bool]:
    """Return a fresh dictionary of declared traits without loading execution."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    return traits(catalog.languages[name].runtime.capabilities)


@runtime_checkable
class SnapshotVM(VM, Protocol):
    """A VM with the state cycle detection compares; internal.

    Out of the public protocol (2.0): users reach it as
    :meth:`~esolangs.debugger.Debugger.snapshot`.
    """

    def snapshot(self) -> Hashable:
        """Return the internal state cycle detection compares, hashable.

        For deterministic machines with the same program and input, equal live
        snapshots imply the same future transitions. Output history is excluded.
        Thue captures its rewrite relation; external draws are excluded.
        Random-machine cycle proofs require the branching protocol.

        The post-halt dump (``dumps_on_the_post_halt_step``) writes output without
        changing most snapshots (Cyclic tag records the dump in its snapshot).
        """


def _make_vm(
    language: str,
    program: ProgramSource,
    *,
    stdin: InputSource = "",
    seed: int | None = None,
    settings: DialectSettings | None = None,
    scale: int | None = None,
    catalog: Catalog | None = None,
    io_factory: Callable[[InputSource], ScriptedIO] = ScriptedIO,
    prepared: PreparedProgram | None = None,
    observe_initialization: bool = False,
) -> VM:
    """Prepare a scoped VM with an invocation-owned input/output factory."""
    from esolangs.registry._catalog import get_catalog
    from esolangs.runtime._prepared import _check_source_options
    from esolangs.runtime._source import anchor_program_source

    program = anchor_program_source(program)
    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    if prepared is None:
        settings, scale = _check_source_options(
            name, program, settings, scale, catalog=catalog
        )
    seed = check_seed(seed)
    check_seed_for(name, seed, catalog=catalog)
    return _make_checked_vm(
        name,
        program,
        stdin=check_input(stdin),
        settings=settings,
        scale=scale,
        seed=seed,
        catalog=catalog,
        io_factory=io_factory,
        prepared=prepared,
        observe_initialization=observe_initialization,
    )


def _make_checked_vm(
    name: str,
    program: ProgramSource,
    *,
    stdin: CheckedInput,
    seed: int | None,
    settings: DialectSettings | None,
    scale: int | None,
    catalog: Catalog,
    io_factory: Callable[[InputSource], ScriptedIO],
    prepared: PreparedProgram | None,
    reproducible: bool = True,
    observe_initialization: bool = False,
) -> VM:
    """Load a step machine after validating invocation choices and input shape."""
    if prepared is None:
        from esolangs.runtime._prepared import _prepare_checked_program

        prepared = _prepare_checked_program(
            name,
            program,
            settings=settings,
            scale=scale,
            catalog=catalog,
            module_loader=interpreter_module,
        )
    with interpreter_errors(
        f"the {name} interpreter recursed deeper than CPython's stack "
        "limit allows while loading this program",
        language=name,
    ):
        return _DelegatingVM(
            name,
            prepared,
            stdin,
            seed=seed,
            reproducible=reproducible,
            observe_initialization=observe_initialization,
            catalog=catalog,
            io_factory=io_factory,
        )


def make_vm(
    language: str,
    program: ProgramSource,
    *,
    stdin: InputSource = "",
    seed: int | None = None,
    settings: DialectSettings | None = None,
    scale: int | None = None,
    catalog: Catalog | None = None,
) -> VM:
    """Return a step-and-inspect wrapper around ``language``'s interpreter.

    ``stdin`` is consumed verbatim using the language's input unit. The name
    resolves case-insensitively via
    :func:`~esolangs.registry.resolve`. Text and raster use the same step
    interface. TemplateArtifact must be filled first;
    literal text is interpreted without template guessing. A seed overrides
    reproducible stepping's language default;
    the checked value is what reaches the interpreter.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ProgramError: The program does not load, as for :func:`esolangs.run`.
        TemplateError: ``program`` is an unfilled template.
        ArgumentError: ``stdin``, ``seed``, ``scale`` or ``settings`` is
            invalid, as :func:`esolangs.run` checks them.
    """
    return _make_vm(
        language,
        program,
        stdin=stdin,
        scale=scale,
        settings=settings,
        seed=seed,
        catalog=catalog,
    )
