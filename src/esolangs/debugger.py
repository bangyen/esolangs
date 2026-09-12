r"""A debugger on top of the step-and-inspect VM."""

from __future__ import annotations

import os
from collections.abc import Callable
from inspect import signature
from time import monotonic
from typing import Literal

from esolangs._validate import check_timeout, check_whole
from esolangs.exceptions import ArgumentError
from esolangs.vm import VM, make_vm, run_until_halt

# : Why a :meth:`Debugger.run`.
StopReason = Literal["halted", "breakpoint", "max_steps", "timeout"]

# : The four values.
# : be iterated or.
# : by reading a docstring;.
#: assert against.
# :.
# : These are what.
# : one more -- ``stopped:.
# : catches what ``run`` lets.
# : traceback.
# : parsed ``stopped:`` against.
STOP_REASONS: tuple[StopReason, ...] = ("halted", "breakpoint", "max_steps", "timeout")


class Debugger:
    r"""Breakpoints and watches over a :class:`VM`."""

    def __init__(self, vm: VM) -> None:
        r"""Wrap ``vm`` with an empty breakpoint and watch set."""
        self.vm = vm
        self._breakpoints: list[Callable[[VM], bool]] = []
        self._cell_history: dict[int, list[int | None]] = {}
        self._stack_history: dict[int, list[object]] = {}
        self._suppressed: set[int] = set()
        self._hits: set[int] = set()
        self._timed_out = False
        self._warned = False
        self._dumped = False

    # -- passthrough to the wrapped.

    @property
    def halted(self) -> bool:
        r"""Whether the wrapped VM has finished executing."""
        return self.vm.halted

    @property
    def output(self) -> str:
        r"""Everything the wrapped VM has written so far."""
        return self.vm.output

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        r"""The wrapped VM's current position."""
        return self.vm.ip

    @property
    def ip_shape(self) -> str:
        r"""How the wrapped VM's ``ip`` reads as a place in the source."""
        return self.vm.ip_shape

    @property
    def views(self) -> tuple[tuple[str, str], ...]:
        r"""The wrapped VM's machine-specific named state."""
        return self.vm.views

    @property
    def memory(self) -> list[int]:
        r"""The wrapped VM's addressable cells."""
        return self.vm.memory

    @property
    def stack(self) -> list[object]:
        r"""The wrapped VM's stack."""
        return self.vm.stack

    @property
    def self_halts(self) -> bool:
        r"""Whether a program in this language can reach a halt of its own."""
        return self.vm.self_halts

    @property
    def dumps_on_the_post_halt_step(self) -> bool:
        r"""Whether the output lands on the step *after* ``halted`` goes true."""
        return self.vm.dumps_on_the_post_halt_step

    @property
    def steppable_to_answer(self) -> bool:
        r"""Whether stepping this language ever reaches the answer."""
        return self.vm.steppable_to_answer

    def snapshot(self) -> object:
        r"""Return the wrapped machine's complete *internal* state, hashable."""
        return self.vm.snapshot()

    # -- breakpoints.

    def break_at(self, ip: int | tuple[int, ...]) -> None:
        r"""Stop when the program counter reaches ``ip``."""
        if isinstance(ip, int) and not isinstance(ip, bool):
            check_whole(ip, "ip")
        elif not (
            isinstance(ip, tuple)
            and ip
            and all(isinstance(part, int) and not isinstance(part, bool) for part in ip)
        ):
            raise ArgumentError(
                f"ip must be a non-negative integer or a tuple of them, got {ip!r}"
            )
        here = self.vm.ip
        if here is not None and here != ():
            kind = "a coordinate tuple" if isinstance(here, tuple) else "an index"
            if isinstance(here, tuple) != isinstance(ip, tuple):
                raise ArgumentError(
                    f"this language's ip is {kind} (currently {here!r}), so a "
                    f"breakpoint on {ip!r} could never fire"
                )
        self._breakpoints.append(lambda vm: vm.ip == ip)

    def break_on_cell(self, index: int, value: int) -> None:
        r"""Stop when ``memory[index]`` holds ``value``."""
        check_whole(index, "index")
        if isinstance(value, bool) or not isinstance(value, int):
            raise ArgumentError(f"value must be an integer, got {value!r}")
        self._breakpoints.append(
            lambda vm: index < len(vm.memory) and vm.memory[index] == value
        )

    def break_on_stack(self, slot: int, value: object) -> None:
        r"""Stop when the ``slot``-th stack value from the top holds ``value``."""
        check_whole(slot, "slot")
        self._breakpoints.append(
            lambda vm: slot < len(vm.stack) and vm.stack[-1 - slot] == value
        )

    def break_on_output(self, text: str) -> None:
        r"""Stop once ``text`` has been written so far."""
        if not isinstance(text, str):
            raise ArgumentError(f"text must be a string, got {type(text).__name__}")
        self._breakpoints.append(lambda vm: text in vm.output)

    def break_when(self, predicate: Callable[[VM], bool]) -> None:
        r"""Stop when ``predicate(vm)`` holds; a catch-all for the rest."""
        if not callable(predicate):
            raise ArgumentError(
                f"predicate must be callable, got {type(predicate).__name__}"
            )
        try:
            signature(predicate).bind(self.vm)
        except TypeError as exc:
            raise ArgumentError(
                f"predicate must take one argument, the VM: {exc}"
            ) from exc
        self._breakpoints.append(predicate)

    def clear_breakpoints(self) -> None:
        r"""Drop every breakpoint, leaving the watches and the run intact."""
        self._breakpoints.clear()
        self._suppressed.clear()
        self._hits.clear()

    # -- watches.

    def watch_cell(self, index: int) -> list[int | None]:
        r"""Record ``memory[index]`` each step, returning the history."""
        check_whole(index, "index")
        if index not in self._cell_history:
            self._cell_history[index] = []
        return self._cell_history[index]

    def watch_stack(self, slot: int) -> list[object]:
        r"""Record the ``slot``-th stack value from the top each step."""
        check_whole(slot, "slot")
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

    # -- execution.

    def step(self) -> None:
        r"""Execute one command, recording any watches."""
        self.vm.step()
        self._record()
        self._warn_about_stdin_once()

    def run(
        self, max_steps: int | None = None, timeout: float | None = None
    ) -> StopReason:
        r"""Execute until the machine halts, a breakpoint fires, or a bound."""
        if max_steps is not None:
            check_whole(max_steps, "max_steps")
        check_timeout(timeout)
        deadline = None if timeout is None else monotonic() + timeout
        self._timed_out = False
        halted = run_until_halt(self, max_steps, stop=lambda: self._stop(deadline))
        if halted:
            self._warn_about_stdin_once()
            # Checked *before* the dump.
            # .
            # A breakpoint is checked.
            # condition the final step.
            # ``run_until_halt`` returned.
            # watch that had fired.
            # since a program whose last.
            # ordinary case -- the.
            # .
            # Two checks rather than one,.
            # step and it changes.
            # swallowed every predicate.
            # ``vm.halted and vm.output ==.
            # languages was true at the.
            # reported as "halted".
            # answer out of reach of a.
            # here, and once after.
            if self._at_breakpoint():
                self._suppressed = set(self._hits)
                return "breakpoint"
            if self.dumps_on_the_post_halt_step and not self._dumped:
                # :meth:`step` learned to cross.
                # so seven languages finished a.
                # ``output`` and the answer one.
                # it back meant knowing to call.
                # method that had already.
                # not a thing a caller can be.
                # ``debug`` did not, and.
                # program that had run.
                # .
                # Only for the seven, and only.
                # no-op everywhere else, but it.
                # watch history, and a bound.
                # be spent.
                # debugger meant an idle.
                # machine spent another one:.
                # Swap grew a ``watch_cell``.
                # promise that it grows one per.
                self._dumped = True
                self.step()
                if self._at_breakpoint():
                    self._suppressed = set(self._hits)
                    return "breakpoint"
            return "halted"
        if self._timed_out:
            return "timeout"
        if self._at_breakpoint():
            self._suppressed = set(self._hits)
            return "breakpoint"
        return "max_steps"

    def _warn_about_stdin_once(self) -> None:
        r"""Say what :func:`esolangs.run` says about a stdin that did not fit."""
        if self._warned:
            return
        name = getattr(self.vm, "language", None)
        io_obj = getattr(self.vm, "_io", None)
        if name is None or io_obj is None:  # pragma: no cover - every adapter has both
            return
        # Two conditions, and only one.
        # .
        # Reading *past* the end is.
        # is when it has to be said:.
        # exhausted read as a value.
        # before they halt -- DINAC at.
        # 5 -- so warning at the halt.
        # breakpoint stop and every.
        # way to drive a debugger, and.
        # bound the run.
        # stdin Suptiftam returns.
        # merely deferred elsewhere is.
        # .
        # A *surplus* -- lines the.
        # was there but unusable -- is.
        # and cannot be known until the.
        # half still waits for the halt.
        # uncovered: a bounded run that.
        # and the halt, on a program.
        # than an over-read.
        # one; a debugger bounded short.
        # fact it needs does not exist.
        if not (getattr(io_obj, "past_end", False) or self.vm.halted):
            return
        self._warned = True
        from esolangs import _warn_about_surplus

        _warn_about_surplus(str(name), io_obj)

    def _stop(self, deadline: float | None) -> bool:
        r"""Whether to stop before the next step: a breakpoint, or the clock."""
        if deadline is not None and monotonic() > deadline:
            self._timed_out = True
            return True
        return self._at_breakpoint()

    def _at_breakpoint(self) -> bool:
        r"""Whether a breakpoint fires now: one that holds and did not already."""
        hits = {i for i, cond in enumerate(self._breakpoints) if cond(self.vm)}
        self._suppressed &= hits
        self._hits = hits
        return bool(hits - self._suppressed)


def make_debugger(
    language: str, program: str | os.PathLike[str], stdin: str = ""
) -> Debugger:
    r"""Return a :class:`Debugger` over a fresh :class:`VM` for."""
    return Debugger(make_vm(language, program, stdin))
