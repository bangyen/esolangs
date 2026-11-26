"""Bind registered interpreter machines to the VM and observation protocol."""

from __future__ import annotations

import sys
from collections.abc import Callable, Hashable, Mapping
from contextlib import AbstractContextManager
from dataclasses import replace
from inspect import getattr_static
from types import FunctionType, MethodType, ModuleType
from typing import Any, cast

from esolangs.exceptions import ArgumentError, EsolangError, InterpreterLimitError
from esolangs.registry._catalog import Catalog
from esolangs.results import ExecutionResult
from esolangs.runtime._capabilities import IpShape as _IpShape
from esolangs.runtime._drive import (
    PeriodicMachine,
    _check_snapshot_hash,
    _checked_halted,
    _invalid_halted,
    _SnapshotUnavailableError,
    drive_periodic,
    drive_until_repeat,
)
from esolangs.runtime._input import CheckedInput, InputSource
from esolangs.runtime._interpreter_errors import interpreter_errors
from esolangs.runtime._lifecycle import Completion, CompletionReport
from esolangs.runtime._prepared import _PreparedRuntime
from esolangs.runtime._state import WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime._traits import trait
from esolangs.runtime._validate import check_whole
from esolangs.runtime._vm_protocol import VM, _check_driver, _StepMachine
from esolangs.runtime._vm_views import machine_views
from esolangs.runtime.io import ScriptedIO, _scripted_io


def _retain_observer_steps(vm: object, error: EsolangError, steps: int) -> bool:
    """Treat a failed observation separately from the accepted command or dump."""
    if isinstance(vm, _DelegatingVM):
        return False
    from esolangs.runtime._controller import ExecutionController

    if not isinstance(vm, ExecutionController):
        return False
    observer_fault = vm._observer_fault  # noqa: SLF001
    if observer_fault is None or observer_fault[0] is not error:
        return False
    owner = _controller_vm(vm)
    if isinstance(owner, _DelegatingVM) and error.observation is not None:
        observation = replace(error.observation, steps=steps + int(observer_fault[1]))
        _record_vm_fault(owner, error, observation)
    return True


def _retain_fault_steps(vm: VM, error: EsolangError, steps: int) -> None:
    """Add measured commands to a fault observed by this VM."""
    if error.observation is not None and not _retain_observer_steps(vm, error, steps):
        owner = _controller_vm(vm)
        observation = replace(error.observation, steps=steps)
        if isinstance(owner, _DelegatingVM):
            _record_vm_fault(owner, error, observation)
        else:
            error.observation = observation


class _DelegatingVM:
    """Wrap a registered interpreter, copying its exposed memory and stack."""

    _machine: _StepMachine
    _fault_observation: ExecutionResult | None = None
    _halt_fault: EsolangError | None = None
    _replayed_halt_fault = False

    def __init__(
        self,
        language: str,
        program: _PreparedRuntime,
        stdin: CheckedInput = "",
        *,
        seed: int | None = None,
        reproducible: bool = True,
        catalog: Catalog | None = None,
        io_factory: Callable[[InputSource], ScriptedIO] = ScriptedIO,
    ) -> None:
        from esolangs.registry._catalog import get_catalog

        catalog = get_catalog(catalog)
        self.language = language
        self._io = _scripted_io(stdin, io_factory, frame=program._input_frame)  # noqa: SLF001
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
            halted = self._machine.halted
            if halted is not False and halted is not True:
                raise _invalid_halted()
            return halted
        except Exception:
            with self._interpreter_errors():
                raise

    def step(self) -> None:
        """Execute one instruction, translating what the interpreter raises.

        The same promise as :func:`esolangs.run`: a bare ``ValueError``
        becomes :class:`~esolangs.exceptions.ProgramError`, a
        ``RecursionError`` :class:`~esolangs.exceptions.InterpreterLimitError`.
        """
        dumping = self._dump_pending and self.halted
        try:
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
                    not dumping
                    and self._dump_pending is not False
                    and self._halt_fault is None
                ):
                    try:
                        if self._machine.halted is True:
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
        return _check_snapshot_hash(
            self._snapshot_value(),
            ArgumentError,
            on_fault=self._observe_snapshot_key_fault,
        )

    def _observe_snapshot_key_fault(
        self, error: EsolangError, steps: int | None = None
    ) -> None:
        if error.observation is None and not error.partial_output:
            observation = self._result(None)
            if steps is not None:
                observation = replace(observation, steps=steps)
            _record_vm_fault(self, error, observation)

    def _snapshot_value(self) -> Hashable:
        """Read a state for a consumer that handles its own evidence validation."""
        snapshot: Callable[[], Hashable] | None
        try:
            try:
                snapshot = self._machine.snapshot
            except AttributeError:
                snapshot = None
            if not callable(snapshot):
                raise _SnapshotUnavailableError(self)
            state = snapshot()
            pending = self._io._pending_input_scan  # noqa: SLF001
            return (
                state
                if pending is None
                else (state, WorkspaceVariant("pending_input_scan", pending))
            )
        except _SnapshotUnavailableError:
            raise
        except EsolangError as error:
            _record_vm_fault(self, error, self._result(None))
            raise

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
        memory = self._view("memory", ())
        if isinstance(memory, Mapping):
            return []
        cells = list(memory)
        if all(type(cell) is int for cell in cells):
            return cells
        return []

    def _memory_reader(self) -> Callable[[int], int | None] | None:
        return cast("Callable[[int], int | None] | None", self._view("memory_at", None))

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
    if not _checked_halted(vm.halted):
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
            owner, error = saved
            # Rewrapping the leaf preserves evidence from its failed halt.
            if _controller_vm(vm.vm) is owner and vm.halted:
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


def _retain_snapshot_key_fault(
    reader: Callable[[], Hashable], error: EsolangError, steps: int | None
) -> None:
    """Attach IO only when the proof used the registered VM's own snapshot."""
    if (
        type(reader) is MethodType
        and reader.__func__ is _DelegatingVM._snapshot_value  # noqa: SLF001
        and isinstance(owner := reader.__self__, _DelegatingVM)
    ):
        owner._observe_snapshot_key_fault(error, steps)  # noqa: SLF001


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
    pending = vm._io._pending_input_scan  # noqa: SLF001 - owned adapter
    if pending is not None and "input_cursor" in state.model.components:
        index = state.model.components.index("input_cursor")
        parts = state.parts
        cursor = WorkspaceVariant("pending_input_scan", (parts[index], *pending))
        return WorkspaceSnapshot(
            state.model, (*parts[:index], cursor, *parts[index + 1 :])
        )
    return state
