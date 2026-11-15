"""Shared driving and output finalization for interpreter shells and VMs."""

from collections.abc import Callable, Hashable
from typing import Protocol, runtime_checkable

from esolangs.exceptions import ArgumentError, InterpreterLimitError
from esolangs.runtime._lifecycle import (
    HALTED_REPORT,
    POST_HALT_REPORT,
    BoundaryCycle,
    Completion,
    CompletionReport,
)
from esolangs.runtime._validate import check_whole


class Machine(Protocol):
    @property
    def halted(self) -> bool: ...

    def step(self) -> None: ...


class SnapshotMachine(Machine, Protocol):
    def snapshot(self) -> Hashable:
        """Return future computational state, including input progress."""


@runtime_checkable
class PeriodicMachine(SnapshotMachine, Protocol):
    """A machine whose final image follows a repeated complete pass."""

    def interrupt(self) -> None: ...


class _SnapshotUnavailableError(ArgumentError):
    """An inspection requires a snapshot the underlying VM does not provide."""

    def __init__(self, vm: object) -> None:
        super().__init__("vm must provide snapshot() to inspect internal state")
        self.vm = vm


def _repeat_hook(machine: object, name: str) -> Callable[[], Hashable]:
    hook: Callable[[], Hashable] | None = getattr(machine, name, None)
    if not callable(hook):
        raise InterpreterLimitError(f"repeat execution requires a callable {name}()")
    return hook


def finalize(
    machine: Machine,
    *,
    cycle: BoundaryCycle | None = None,
    policy: Completion,
) -> None:
    """Write final output after a halt or an evidenced boundary repetition."""
    if type(policy) is not Completion:
        raise TypeError("completion must be a Completion policy")
    if policy is Completion.PERIODIC:
        if cycle is None:
            raise ValueError("periodic completion needs boundary-cycle evidence")
        if _repeat_hook(machine, "snapshot")() != cycle.state:
            raise ValueError("boundary-cycle evidence no longer matches the machine")
        _repeat_hook(machine, "interrupt")()
        machine.step()
    else:
        if cycle is not None:
            raise ValueError("boundary-cycle evidence requires periodic completion")
        if not machine.halted:
            raise ValueError("completion requires a halted machine")
        if policy is Completion.POST_HALT:
            machine.step()


def drive(machine: Machine, *, policy: Completion) -> CompletionReport:
    """Run to halt, including a language's declared final output step."""
    if type(policy) is not Completion:
        raise TypeError("completion must be a Completion policy")
    while not machine.halted:
        machine.step()
    finalize(machine, policy=policy)
    return POST_HALT_REPORT if policy is Completion.POST_HALT else HALTED_REPORT


def drive_until_repeat(
    machine: SnapshotMachine, *, step: Callable[[], None] | None = None
) -> CompletionReport:
    """Run to a halt or the first exact repeat without taking a dump step."""
    take_step = machine.step if step is None else step
    seen: set[Hashable] = set()
    history: list[Hashable] = []
    snapshot: Callable[[], Hashable] | None
    while not machine.halted:
        try:
            snapshot = machine.snapshot
        except AttributeError:
            snapshot = None
        if not callable(snapshot):
            raise InterpreterLimitError(
                "repeat execution requires a callable snapshot()"
            )
        state = snapshot()
        if state in seen:
            cycle = BoundaryCycle(state, history.index(state), len(history), 1)
            return CompletionReport(Completion.PERIODIC, cycle)
        # Ordinary EOF runs keep set lookups; index only on an actual repeat.
        seen.add(state)
        history.append(state)
        take_step()
    return HALTED_REPORT


def drive_periodic(
    machine: PeriodicMachine,
    commands_per_pass: int,
    *,
    policy: Completion,
    step: Callable[[], None] | None = None,
) -> BoundaryCycle:
    """Detect a boundary cycle with Brent's rule; the stride is one whole pass."""
    commands_per_pass = check_whole(commands_per_pass, "commands_per_pass")
    if policy is not Completion.PERIODIC:
        raise ValueError("periodic driving requires periodic completion")
    take_step = machine.step if step is None else step
    anchor = _repeat_hook(machine, "snapshot")()
    first_pass = 0
    repeat_pass = 0
    power = 1
    passes = 0
    while True:
        for _ in range(commands_per_pass):
            take_step()
        passes += 1
        repeat_pass += 1
        state = _repeat_hook(machine, "snapshot")()
        if state == anchor:
            break
        if passes == power:
            anchor = state
            first_pass = repeat_pass
            power *= 2
            passes = 0
    cycle = BoundaryCycle(state, first_pass, repeat_pass, commands_per_pass)
    finalize(machine, cycle=cycle, policy=policy)
    return cycle
