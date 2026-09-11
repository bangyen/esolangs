"""A debugger on top of the step-and-inspect VM.

:class:`Debugger` wraps a :class:`esolangs.vm.VM` and adds the two
affordances a study tool needs beyond stepping: breakpoints (stop the run
when a condition holds, before the step that would change it) and watches
(record how a cell or stack slot evolves step by step).

Breakpoints are checked *before* each step, so a ``break_at`` on the initial
instruction position fires immediately without executing it, and a
``break_on_cell`` fires while the cell still holds the watched value (before
the step that would move past it).
"""

from __future__ import annotations

from collections.abc import Callable
from time import monotonic
from typing import Literal

from esolangs.exceptions import HaltError
from esolangs.vm import VM, make_vm, run_until_halt

#: Why a :meth:`Debugger.run` returned.
StopReason = Literal["halted", "breakpoint", "max_steps"]


class Debugger:
    """Breakpoints and watches over a :class:`VM`.

    ``step()`` advances one command; ``run()`` advances until the machine
    halts or a breakpoint fires.  The ``halted``/``output``/``ip``/``memory``/
    ``stack`` properties mirror the wrapped VM, and ``watch_cell``/
    ``watch_stack`` accumulate a per-step history.
    """

    def __init__(self, vm: VM) -> None:
        """Wrap ``vm`` with an empty breakpoint and watch set."""
        self.vm = vm
        self._breakpoints: list[Callable[[VM], bool]] = []
        self._cell_history: dict[int, list[int | None]] = {}
        self._stack_history: dict[int, list[object]] = {}
        self._suppressed: set[int] = set()
        self._hits: set[int] = set()

    # -- passthrough to the wrapped VM --------------------------------

    @property
    def halted(self) -> bool:
        """Whether the wrapped VM has finished executing."""
        return self.vm.halted

    @property
    def output(self) -> str:
        """Everything the wrapped VM has written so far."""
        return self.vm.output

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        """The wrapped VM's current position."""
        return self.vm.ip

    @property
    def memory(self) -> list[int]:
        """The wrapped VM's addressable cells."""
        return self.vm.memory

    @property
    def stack(self) -> list[object]:
        """The wrapped VM's stack."""
        return self.vm.stack

    # -- breakpoints --------------------------------------------------

    def break_at(self, ip: int | tuple[int, ...]) -> None:
        """Stop when the program counter reaches ``ip``."""
        self._breakpoints.append(lambda vm: vm.ip == ip)

    def break_on_cell(self, index: int, value: int) -> None:
        """Stop when ``memory[index]`` holds ``value``."""
        self._breakpoints.append(
            lambda vm: index < len(vm.memory) and vm.memory[index] == value
        )

    def break_on_stack(self, slot: int, value: object) -> None:
        """Stop when the ``slot``-th stack value from the top holds ``value``."""
        self._breakpoints.append(
            lambda vm: slot < len(vm.stack) and vm.stack[-1 - slot] == value
        )

    def break_on_output(self, text: str) -> None:
        """Stop once ``text`` has been written so far."""
        self._breakpoints.append(lambda vm: text in vm.output)

    def break_when(self, predicate: Callable[[VM], bool]) -> None:
        """Stop when ``predicate(vm)`` holds; a catch-all for the rest."""
        self._breakpoints.append(predicate)

    def clear_breakpoints(self) -> None:
        """Drop every breakpoint, leaving the watches and the run intact.

        The counterpart the breakpoint setters lacked.  Without it a
        condition that stays true -- :meth:`break_on_output`'s does, since
        output only accumulates -- could not be taken back, and the session
        that set one had no way to reach the end of its program.
        """
        self._breakpoints.clear()
        self._suppressed.clear()
        self._hits.clear()

    # -- watches ------------------------------------------------------

    def watch_cell(self, index: int) -> list[int | None]:
        """Record ``memory[index]`` each step, returning the history.

        A cell that does not exist yet records ``None`` (the tape has not
        grown there); the list grows by one per :meth:`step`.  Watching a
        cell again returns the existing history.
        """
        if index not in self._cell_history:
            self._cell_history[index] = []
        return self._cell_history[index]

    def watch_stack(self, slot: int) -> list[object]:
        """Record the ``slot``-th stack value from the top each step."""
        if slot not in self._stack_history:
            self._stack_history[slot] = []
        return self._stack_history[slot]

    def _record(self) -> None:
        memory = self.vm.memory
        for index, cell_history in self._cell_history.items():
            cell_history.append(memory[index] if index < len(memory) else None)
        stack = self.vm.stack
        for slot, stack_history in self._stack_history.items():
            stack_history.append(stack[-1 - slot] if slot < len(stack) else None)

    # -- execution ----------------------------------------------------

    def step(self) -> None:
        """Execute one command, recording any watches."""
        if self.halted:
            return
        self.vm.step()
        self._record()

    def run(
        self, max_steps: int | None = None, timeout: float | None = None
    ) -> StopReason:
        """Execute until the machine halts, a breakpoint fires, or a bound ends it.

        Returns *why* it stopped -- ``"halted"``, ``"breakpoint"`` or
        ``"max_steps"``.  It used to return ``None``, on the argument that
        the contract was to stop rather than to report why; but ``halted``
        only separates the first case from the other two, so a caller could
        not tell a breakpoint from an exhausted budget at all, and the CLI
        one layer up was already reporting exactly this.

        A breakpoint is checked before each step, so the run stops with the
        watched condition still true.  **A breakpoint that stopped the last
        run does not fire again until its condition goes false**, which is
        what lets a resumed run advance; see :meth:`_at_breakpoint`.  A
        breakpoint that has not fired yet is checked as it always was, so
        ``break_at(ip)`` on the initial position still stops before the
        first step executes.

        ``max_steps`` bounds the run in steps and ``timeout`` in wall-clock
        seconds, raising :class:`~esolangs.exceptions.HaltError` when it
        expires; the default of ``None`` for both is unbounded, which is
        right for a machine known to halt and a hang for one that is not.
        The timeout is checked in the same place as a breakpoint rather than
        through a signal, so it needs no main thread and leaves the machine
        inspectable where it stopped.

        The drive itself is :func:`~esolangs.vm.run_until_halt`, and what is
        stepped is ``self`` rather than ``self.vm`` -- :meth:`step` already
        records the watches, so recording stays part of a step instead of
        becoming a hook the shared loop would have to grow.
        """
        deadline = None if timeout is None else monotonic() + timeout
        halted = run_until_halt(self, max_steps, stop=lambda: self._stop(deadline))
        if halted:
            return "halted"
        if self._at_breakpoint():
            self._suppressed = set(self._hits)
            return "breakpoint"
        return "max_steps"

    def _stop(self, deadline: float | None) -> bool:
        """Whether to stop before the next step: a breakpoint, or the clock."""
        if deadline is not None and monotonic() > deadline:
            raise HaltError("execution exceeded the debugger's timeout")
        return self._at_breakpoint()

    def _at_breakpoint(self) -> bool:
        """Whether a breakpoint fires now: one that holds and did not already.

        A breakpoint that *stopped* the last run is suppressed until its
        condition goes false again, which is what makes a resumed run
        advance.  The distinction is invisible for the position and value
        breakpoints, whose conditions stop holding as soon as the machine
        moves, and it is the whole story for :meth:`break_on_output`: output
        only accumulates, so ``text in vm.output`` is true forever after the
        first time and re-firing on it meant the run never progressed.

        Suppression is per condition, so a second breakpoint still stops a
        resumed run, and it is dropped the moment the condition is false --
        an output breakpoint on a language that can rewrite its output would
        re-arm itself like any other.
        """
        hits = {i for i, cond in enumerate(self._breakpoints) if cond(self.vm)}
        self._suppressed &= hits
        self._hits = hits
        return bool(hits - self._suppressed)


def make_debugger(language: str, program: str, stdin: str = "") -> Debugger:
    """Return a :class:`Debugger` over a fresh :class:`VM` for ``language``.

    ``stdin`` is fed to the program line by line, like :func:`esolangs.run`.
    A language without a step-capable interpreter raises
    :class:`UnknownLanguageError`, as with :func:`esolangs.make_vm`.
    """
    return Debugger(make_vm(language, program, stdin))
