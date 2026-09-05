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

from esolangs.vm import VM, make_vm, run_until_halt


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

    def run(self, max_steps: int | None = None) -> None:
        """Execute until the machine halts or a breakpoint fires.

        A breakpoint is checked before each step, so the run stops with the
        watched condition still true.  ``max_steps`` bounds the run as a
        guard against runaway programs; the run simply stops (without
        erroring) once that many commands have executed.

        The drive itself is :func:`~esolangs.vm.run_until_halt`, and what
        is stepped is ``self`` rather than ``self.vm`` -- :meth:`step`
        already records the watches, so recording stays part of a step
        instead of becoming a hook the shared loop would have to grow.  A
        breakpoint is the ``stop`` predicate, which is checked before each
        step and so keeps the watched condition true at the return.  Its
        ``False`` verdict is discarded because this method's contract is to
        stop, not to report why.
        """
        run_until_halt(self, max_steps, stop=self._at_breakpoint)

    def _at_breakpoint(self) -> bool:
        """Whether any breakpoint condition holds right now."""
        return any(cond(self.vm) for cond in self._breakpoints)


def make_debugger(language: str, program: str, stdin: str = "") -> Debugger:
    """Return a :class:`Debugger` over a fresh :class:`VM` for ``language``.

    ``stdin`` is fed to the program line by line, like :func:`esolangs.run`.
    A language without a step-capable interpreter raises
    :class:`UnknownLanguageError`, as with :func:`esolangs.make_vm`.
    """
    return Debugger(make_vm(language, program, stdin))
