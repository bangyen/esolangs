"""Shared driving and output finalization for interpreter shells and VMs."""

from collections.abc import Callable, Hashable
from typing import Protocol, runtime_checkable

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


@runtime_checkable
class PeriodicMachine(Machine, Protocol):
    """A machine whose final image follows a repeated complete pass."""

    def snapshot(self) -> Hashable:
        """Return future computational state, including input progress."""

    def interrupt(self) -> None: ...


def finalize(
    machine: Machine,
    *,
    cycle: BoundaryCycle | None = None,
    policy: Completion,
) -> None:
    """Write final output after a halt or an evidenced boundary repetition."""
    if not isinstance(policy, Completion):
        raise TypeError("completion must be a Completion policy")
    if policy is Completion.PERIODIC:
        if cycle is None:
            raise ValueError("periodic completion needs boundary-cycle evidence")
        if not isinstance(machine, PeriodicMachine):
            raise TypeError("periodic completion needs snapshot and interrupt")
        if machine.snapshot() != cycle.state:
            raise ValueError("boundary-cycle evidence no longer matches the machine")
        machine.interrupt()
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
    if not isinstance(policy, Completion):
        raise TypeError("completion must be a Completion policy")
    while not machine.halted:
        machine.step()
    finalize(machine, policy=policy)
    return POST_HALT_REPORT if policy is Completion.POST_HALT else HALTED_REPORT


def drive_periodic(
    machine: PeriodicMachine,
    commands_per_pass: int,
    *,
    policy: Completion,
    step: Callable[[], None] | None = None,
) -> BoundaryCycle:
    """Detect a boundary cycle with Brent's rule; the stride is one whole pass."""
    check_whole(commands_per_pass, "commands_per_pass")
    if policy is not Completion.PERIODIC:
        raise ValueError("periodic driving requires periodic completion")
    take_step = machine.step if step is None else step
    anchor = machine.snapshot()
    first_pass = 0
    repeat_pass = 0
    power = 1
    passes = 0
    while True:
        for _ in range(commands_per_pass):
            take_step()
        passes += 1
        repeat_pass += 1
        state = machine.snapshot()
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
