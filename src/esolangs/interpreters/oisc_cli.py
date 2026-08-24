"""Shared instruction-limited run loop and CLI entry point for the OISCs.

Decleq and AddSubJump both self-modify their memory, so neither can rely on
state-cycle detection to prove a hang (every instruction can change the
state a later step would revisit); both instead run a step-capable machine
up to a fixed instruction ``limit`` and raise :class:`HaltError` past it.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Protocol

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


class _StepMachine(Protocol):
    """The minimal step-capable surface :func:`run_with_limit` steps on."""

    def step(self) -> None:
        """Execute one instruction, advancing the machine."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""


def run_with_limit(machine: _StepMachine, limit: int) -> None:
    """Step ``machine`` until it halts, or raise past ``limit`` steps."""
    for _ in range(limit):
        if machine.halted:
            return
        machine.step()
    raise HaltError(f"execution exceeded the {limit}-instruction limit")


def run_until_halt(machine: _StepMachine) -> None:
    """Step ``machine`` until it halts, letting its own budget end the run.

    The companion to :func:`run_with_limit`, for languages whose programs are
    specified to loop forever: Suffolk and ABCDirection have no halt
    instruction, so reaching the budget is how every program ends rather than
    a failure to report.  Those machines carry the budget themselves and set
    ``halted`` when it runs out, so this returns instead of raising.

    What the budget counts is the machine's own business -- Suffolk counts
    full passes over the code, ABCDirection counts steps -- and this only
    needs ``halted`` to become true eventually.  A Painter Ant loops forever
    too but never sets ``halted``, so it needs the VM's cycle detector
    instead of this.
    """
    while not machine.halted:
        machine.step()


def main_with_limit(run: Callable[..., None]) -> None:
    """Run ``sys.argv``'s program file through ``run``, with an optional limit."""
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            if len(sys.argv) > 2:
                run(data, IO(), limit=int(sys.argv[2]))
            else:
                run(data, IO())
