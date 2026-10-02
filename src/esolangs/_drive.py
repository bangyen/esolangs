"""Unbounded execution for ordinary interpreter shells."""

from typing import Protocol


class Machine(Protocol):
    @property
    def halted(self) -> bool: ...

    def step(self) -> None: ...


def drive(machine: Machine) -> None:
    """Run to halt, including a language's declared final output step."""
    while not machine.halted:
        machine.step()
    if getattr(machine, "dumps_on_the_post_halt_step", False):
        machine.step()
