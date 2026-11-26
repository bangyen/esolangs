"""Prove a halt or a repeated command-boundary state."""

from collections.abc import Callable, Hashable
from inspect import getattr_static

from esolangs.exceptions import EsolangError
from esolangs.runtime._drive import (
    _check_snapshot_hash,
    _checked_halted,
    _SnapshotUnavailableError,
)
from esolangs.runtime._lifecycle import BoundaryCycle
from esolangs.runtime._proof import CycleDecision
from esolangs.runtime._proof_runtime import (
    _exact_halt,
    _ProofBudgetExhaustedError,
    _ProofSnapshotUnavailableError,
)
from esolangs.runtime._vm_protocol import _StepMachine
from esolangs.runtime.source_hints import with_hint


def _proof_snapshot_reader(
    machine: _StepMachine,
) -> tuple[Callable[[], Hashable], bool]:
    """Choose a state reader and whether each returned snapshot needs checking."""
    from esolangs.debugger import Debugger
    from esolangs.runtime._vm_adapter import _DelegatingVM

    reader = getattr_static(machine, "snapshot", None)
    if isinstance(machine, _DelegatingVM) and reader is _DelegatingVM.snapshot:
        return (
            machine._snapshot_value,  # noqa: SLF001 - proof owns state validation
            not machine._uses_installed_snapshots(),  # noqa: SLF001
        )
    if isinstance(machine, Debugger) and reader is Debugger.snapshot:
        wrapped = machine.vm
        if isinstance(wrapped, Debugger) and (
            getattr_static(wrapped, "snapshot", None) is Debugger.snapshot
        ):
            return _proof_snapshot_reader(wrapped)
        if isinstance(wrapped, _DelegatingVM) and (
            getattr_static(wrapped, "snapshot", None) is _DelegatingVM.snapshot
        ):
            return (
                wrapped._snapshot_value,  # noqa: SLF001 - proof owns state validation
                not wrapped._uses_installed_snapshots(),  # noqa: SLF001
            )
        return machine._snapshot_value, True  # noqa: SLF001 - proof checks the state

    def read_live() -> Hashable:
        return machine.snapshot()

    return read_live, True


def _proof_snapshot(
    reader: Callable[[], Hashable],
    adapter: object,
    steps: int | None,
    *,
    check_hash: bool = False,
) -> Hashable:
    try:
        state = reader()
    except _SnapshotUnavailableError as error:
        if error.vm is not adapter:
            raise
        raise with_hint(
            _ProofSnapshotUnavailableError(
                "exact-cycle proof requires a callable snapshot()"
            ),
            "provide a machine with a snapshot of its complete state",
        ) from error
    except EsolangError as error:
        from esolangs.runtime._vm_adapter import _DelegatingVM, _retain_fault_steps

        if steps is not None and isinstance(adapter, _DelegatingVM):
            _retain_fault_steps(adapter, error, steps)
        raise
    if check_hash:
        try:
            _check_snapshot_hash(state, _ProofSnapshotUnavailableError)
        except EsolangError as error:
            from esolangs.runtime._vm_adapter import _retain_snapshot_key_fault

            _retain_snapshot_key_fault(reader, error, steps)
            raise
    return state


def _drive_exact_cycle(
    machine: _StepMachine,
    adapter: object,
    limit: int | None,
    check_receiver: Callable[[], None] | None,
    *,
    evidence: bool,
    record_commands: Callable[[int], None] | None,
) -> bool | CycleDecision:
    """Step a live machine until Brent's checkpoint repeats or it halts."""
    reader, check_each_snapshot = _proof_snapshot_reader(machine)
    tortoise = _proof_snapshot(
        reader, adapter, None if evidence else 0, check_hash=True
    )
    first_step = length = steps = 0
    power = 1
    while not _checked_halted(machine.halted):
        if check_receiver is not None:
            check_receiver()
        if limit is not None and steps >= limit:
            error = _ProofBudgetExhaustedError if evidence else TimeoutError
            raise with_hint(
                error(
                    f"undecided after {limit} steps: "
                    "neither halted nor repeated a state"
                ),
                "increase limit; for growing states try a supported growth detector",
            )
        try:
            machine.step()
        except EsolangError as error:
            if not evidence:
                from esolangs.runtime._vm_adapter import _retain_observer_steps

                _retain_observer_steps(machine, error, steps)
            raise
        steps += 1
        if record_commands is not None:
            record_commands(steps)
        length += 1
        if check_receiver is not None:
            check_receiver()
        if _checked_halted(machine.halted):
            return _exact_halt(steps, check_receiver, evidence=evidence)
        state = _proof_snapshot(reader, adapter, None if evidence else steps)
        at_checkpoint = length == power
        try:
            if check_each_snapshot:
                _check_snapshot_hash(state, _ProofSnapshotUnavailableError)
            repeated = bool(state == tortoise)
            if not check_each_snapshot and (
                state is not tortoise if repeated else at_checkpoint
            ):
                _check_snapshot_hash(state, _ProofSnapshotUnavailableError)
        except EsolangError as error:
            from esolangs.runtime._vm_adapter import _retain_snapshot_key_fault

            _retain_snapshot_key_fault(reader, error, None if evidence else steps)
            raise
        if repeated:
            return _exact_repeat(
                tortoise, first_step, steps, reader, check_receiver, evidence=evidence
            )
        if at_checkpoint:
            tortoise = state
            first_step = steps
            power *= 2
            length = 0
    return _exact_halt(steps, check_receiver, evidence=evidence)


def _exact_repeat(
    state: Hashable,
    first_step: int,
    steps: int,
    reader: Callable[[], Hashable],
    check_receiver: Callable[[], None] | None,
    *,
    evidence: bool,
) -> bool | CycleDecision:
    if check_receiver is not None:
        check_receiver()
    if not evidence:
        return False
    try:
        cycle = BoundaryCycle(state, first_step, steps, 1)
    except EsolangError as error:
        from esolangs.runtime._vm_adapter import _retain_snapshot_key_fault

        _retain_snapshot_key_fault(reader, error, None)
        raise
    return CycleDecision(halts=False, commands=steps, cycle=cycle)
