"""A debugger on top of the step-and-inspect VM.

:class:`Debugger` wraps a :class:`esolangs.vm.VM` with breakpoints (stop
before the step that would change the condition) and watches (a per-step
history of a cell or stack slot).  Breakpoints are checked *before* each
step, so ``break_at`` on the initial position fires without executing it.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from inspect import signature
from time import monotonic
from typing import Literal

from esolangs._validate import check_timeout, check_whole
from esolangs.exceptions import ArgumentError
from esolangs.vm import VM, make_vm, run_until_halt

#: Why a :meth:`Debugger.run` returned.
StopReason = Literal["halted", "breakpoint", "max_steps", "timeout"]

#: :data:`StopReason`'s members as iterable data.  What :meth:`Debugger.run`
#: returns; the CLI's ``debug`` also prints ``stopped: raised`` for a fault
#: it caught, so a parsed ``stopped:`` line can fail against this tuple.
STOP_REASONS: tuple[StopReason, ...] = ("halted", "breakpoint", "max_steps", "timeout")


class Debugger:
    """Breakpoints and watches over a :class:`VM`.

    ``step()`` advances one command; ``run()`` until a halt or breakpoint --
    **pass ``max_steps`` or ``timeout``** unless the program is known to
    halt.  The VM's properties and traits are mirrored so a driving caller
    never needs ``self.vm``; ``watch_cell``/``watch_stack`` accumulate history.
    """

    def __init__(self, vm: VM) -> None:
        """Wrap ``vm`` with an empty breakpoint and watch set."""
        self.vm = vm
        self._breakpoints: list[Callable[[VM], bool]] = []
        self._cell_history: dict[int, list[int | None]] = {}
        self._stack_history: dict[int, list[object]] = {}
        self._suppressed: set[int] = set()
        self._hits: set[int] = set()
        self._timed_out = False
        self._warned = False
        self._dumped = False

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
        """The wrapped VM's current position.

        An ``int``, a tuple, or ``None``, not stable in kind or arity within a
        run; :attr:`~esolangs.vm.VM.ip` has the rules :meth:`break_at` depends on.
        """
        return self.vm.ip

    @property
    def ip_shape(self) -> str:
        """How the wrapped VM's ``ip`` reads as a place in the source."""
        return self.vm.ip_shape

    @property
    def views(self) -> tuple[tuple[str, str], ...]:
        """The wrapped VM's machine-specific named state."""
        return self.vm.views

    @property
    def memory(self) -> list[int]:
        """The wrapped VM's addressable cells."""
        return self.vm.memory

    @property
    def stack(self) -> list[object]:
        """The wrapped VM's stack."""
        return self.vm.stack

    @property
    def self_halts(self) -> bool:
        """Whether a program in this language can reach a halt of its own.

        See :attr:`~esolangs.vm.VM.self_halts`; a pointer, since copies drifted once.
        """
        return self.vm.self_halts

    @property
    def dumps_on_the_post_halt_step(self) -> bool:
        """Whether the output lands on the step *after* ``halted`` goes true.

        A :meth:`run` returning ``"halted"`` has taken it; one returning
        ``"breakpoint"`` may not have, so on these seven the stop reason, not
        ``halted``, says whether the answer is written.
        """
        return self.vm.dumps_on_the_post_halt_step

    @property
    def steppable_to_answer(self) -> bool:
        """Whether stepping this language ever reaches the answer.

        See :attr:`~esolangs.vm.VM.steppable_to_answer`.
        """
        return self.vm.steppable_to_answer

    def snapshot(self) -> object:
        """Return the wrapped machine's complete *internal* state, hashable.

        ``output`` is excluded (equal internal state means the same future), so
        two snapshots compare equal across the post-halt dump.  A repeated
        snapshot proves a loop, which settles the three termination languages in
        microseconds.
        """
        return self.vm.snapshot()

    def break_at(self, ip: int | tuple[int, ...]) -> None:
        """Stop when the program counter reaches ``ip``.

        An ``int``, or a tuple for a coordinate ``ip``; anything else, or the
        wrong kind for this language, is refused rather than stored as a
        breakpoint that never fires.  Kind only, not arity (not constant within
        a run; see :attr:`~esolangs.vm.VM.ip`).  ``None`` is refused although
        five languages reach it: use ``break_when(lambda vm: vm.ip is None)``.
        A position never reached is accepted (the protocol has no ``len``).
        """
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
        """Stop when ``memory[index]`` holds ``value``.

        ``value`` must be an ``int``, or it never fires.
        """
        check_whole(index, "index")
        if isinstance(value, bool) or not isinstance(value, int):
            raise ArgumentError(f"value must be an integer, got {value!r}")
        self._breakpoints.append(
            lambda vm: index < len(vm.memory) and vm.memory[index] == value
        )

    def break_on_stack(self, slot: int, value: object) -> None:
        """Stop when the ``slot``-th stack value from the top holds ``value``.

        ``value`` is unchecked: a slot holds whatever its language pushes.
        """
        check_whole(slot, "slot")
        self._breakpoints.append(
            lambda vm: slot < len(vm.stack) and vm.stack[-1 - slot] == value
        )

    def break_on_output(self, text: str) -> None:
        """Stop once ``text`` has been written so far.

        A non-string is refused here, not from inside the run loop.
        """
        if not isinstance(text, str):
            raise ArgumentError(f"text must be a string, got {type(text).__name__}")
        self._breakpoints.append(lambda vm: text in vm.output)

    def break_when(self, predicate: Callable[[VM], bool]) -> None:
        """Stop when ``predicate(vm)`` holds; a catch-all for the rest.

        Callability and arity are checked here, not from inside the run loop.
        """
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
        """Drop every breakpoint, leaving the watches and the run intact.

        Without it a condition that stays true (:meth:`break_on_output`'s) could
        not be taken back.
        """
        self._breakpoints.clear()
        self._suppressed.clear()
        self._hits.clear()

    def watch_cell(self, index: int) -> list[int | None]:
        """Record ``memory[index]`` each step, returning the history.

        A missing cell records ``None``, and memory *shrinks* on five languages
        (Forbin 16 -> 0, Taglate 22 -> 4, Packlang, Circuit Diagram,
        Bitdeque).  Recording starts here; the list is live.
        """
        check_whole(index, "index")
        if index not in self._cell_history:
            self._cell_history[index] = []
        return self._cell_history[index]

    def watch_stack(self, slot: int) -> list[object]:
        """Record the ``slot``-th stack value from the top each step.

        A language with no stack records one ``None`` per step, not an empty
        history: ``stack`` is ``[]`` there, and the protocol draws no line.
        ``describe(...)["state_model"]`` is the fact to consult first.
        """
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

    def step(self) -> None:
        """Execute one command, recording any watches.

        Delegates past the halt: the post-halt-dump languages keep their answer
        there, and returning early cost a debugger-driven verifier 58/65.
        Warns about an underfed stdin at the halt as :meth:`run` does.
        """
        self.vm.step()
        self._record()
        self._warn_about_stdin_once()

    def run(
        self, max_steps: int | None = None, timeout: float | None = None
    ) -> StopReason:
        """Execute until the machine halts, a breakpoint fires, or a bound ends it.

        Returns why: ``"halted"``, ``"breakpoint"``, ``"max_steps"`` or
        ``"timeout"``.  A breakpoint that stopped the last run is suppressed
        until its condition goes false.  It is checked again after the halt, and
        on the seven post-halt-dump languages before *and* after the dump, so
        ``"breakpoint"`` can come back with ``halted`` true and ``output`` empty
        -- another ``step()`` takes the dump, which is outside ``max_steps``.
        Bounds return rather than raise (``None`` unbounded); a fault still
        raises (the CLI prints ``stopped: raised``, see :data:`STOP_REASONS`).
        The timeout is checked with the breakpoints, so no main thread is
        needed.  Drives :func:`~esolangs.vm.run_until_halt` over ``self`` so
        watches stay part of a step.
        """
        if max_steps is not None:
            check_whole(max_steps, "max_steps")
        check_timeout(timeout)
        deadline = None if timeout is None else monotonic() + timeout
        self._timed_out = False
        halted = run_until_halt(self, max_steps, stop=lambda: self._stop(deadline))
        if halted:
            self._warn_about_stdin_once()
            # Breakpoints are checked before each step, so one the final
            # step makes true was never seen (``break_on_output`` on a
            # program ending in ``.``).  Checked both before and after the
            # dump step below, because the dump changes ``output``:
            # after-only lost ``vm.halted and vm.output == ""`` on the seven
            # dumping languages, before-only puts the dumped text out of reach.
            if self._at_breakpoint():
                self._suppressed = set(self._hits)
                return "breakpoint"
            if self.dumps_on_the_post_halt_step and not self._dumped:
                # Cross the halt for the seven dumping languages, or ``run``
                # ends with the answer one un-taken step away (the CLI
                # printed ``output: ''`` on a correct program).  Once per
                # debugger, not per run: it lands in every watch history,
                # and three idle ``run()`` calls on a halted Minsky Swap
                # grew ``watch_cell`` by three.
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
        """Say what :func:`esolangs.run` says about a stdin that did not fit.

        Fewer lines than given, or -- the one that matters -- a read past the
        end where the end is a value: a wrong answer in silence.  At the halt,
        where the counts are final; once per debugger, since ``run`` on a halted
        machine returns immediately.
        """
        if self._warned:
            return
        name = getattr(self.vm, "language", None)
        io_obj = getattr(self.vm, "_io", None)
        if name is None or io_obj is None:  # pragma: no cover - every adapter has both
            return
        # Over-read is warned the moment it happens: six languages take the
        # exhausted read as a value (Circuit Diagram at step 4 of 5), so a
        # halt-time warning was silent on every bounded run, and never
        # emitted at all on Suptiftam with empty stdin (``"max_steps"``).
        # Surplus or malformed lines cannot be known until the program stops
        # asking, so that half waits for the halt -- a bounded run that
        # stops before it is the one case ``run``/``check_stdin`` catch and
        # this cannot.
        if not (getattr(io_obj, "past_end", False) or self.vm.halted):
            return
        self._warned = True
        from esolangs import _warn_about_surplus

        _warn_about_surplus(str(name), io_obj)

    def _stop(self, deadline: float | None) -> bool:
        """Whether to stop before the next step: a breakpoint, or the clock."""
        if deadline is not None and monotonic() > deadline:
            self._timed_out = True
            return True
        return self._at_breakpoint()

    def _at_breakpoint(self) -> bool:
        """Whether a breakpoint fires now: one that holds and did not already.

        Suppressed until its condition goes false again, per condition.
        Invisible for position and value breakpoints; the whole story for
        :meth:`break_on_output`, whose ``text in vm.output`` is true forever.
        """
        hits = {i for i, cond in enumerate(self._breakpoints) if cond(self.vm)}
        self._suppressed &= hits
        self._hits = hits
        return bool(hits - self._suppressed)


def make_debugger(
    language: str, program: str | os.PathLike[str], stdin: str = ""
) -> Debugger:
    """Return a :class:`Debugger` over a fresh :class:`VM` for ``language``.

    ``stdin`` is fed line by line.  Only an unknown name raises
    :class:`~esolangs.exceptions.UnknownLanguageError` (every language is
    step-capable); a malformed program raises
    :class:`~esolangs.exceptions.ProgramError`, and on Clockwise -- which
    reads its whole input while the machine is built -- an underfed stdin
    raises :class:`~esolangs.exceptions.InputExhaustedError` here rather
    than at :meth:`Debugger.run`.
    """
    return Debugger(make_vm(language, program, stdin))
