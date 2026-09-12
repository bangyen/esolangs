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

#: The four values :data:`StopReason` allows, as data.  A ``Literal`` cannot
#: be iterated or attribute-accessed, so its members were discoverable only
#: by reading a docstring; this is the same list a caller can loop over or
#: assert against.
STOP_REASONS: tuple[StopReason, ...] = ("halted", "breakpoint", "max_steps", "timeout")


class Debugger:
    """Breakpoints and watches over a :class:`VM`.

    ``step()`` advances one command; ``run()`` advances until the machine
    halts or a breakpoint fires -- **pass ``max_steps`` or ``timeout``
    unless the program is known to halt**, since neither is bounded by
    default and several of these languages loop forever by design.

    The ``halted``/``output``/``ip``/``memory``/``stack`` properties mirror
    the wrapped VM, and ``watch_cell``/``watch_stack`` accumulate a per-step
    history.

    So do the three language traits -- ``self_halts``,
    ``dumps_on_the_post_halt_step`` and ``steppable_to_answer``.  They were
    the mirrors left out, and they are the ones a *driving* caller needs:
    they say whether to bound the run, whether the answer arrives one step
    past the halt, and whether stepping reaches it at all.  Reading them
    meant reaching through ``self.vm``, which is the wrapped machine and is
    public for exactly the cases this class does not cover -- but a trait
    that decides how to drive the debugger should not need the thing being
    driven.
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

    @property
    def self_halts(self) -> bool:
        """Whether a program in this language can reach a halt of its own."""
        return self.vm.self_halts

    @property
    def dumps_on_the_post_halt_step(self) -> bool:
        """Whether the output lands on the step *after* ``halted`` goes true."""
        return self.vm.dumps_on_the_post_halt_step

    @property
    def steppable_to_answer(self) -> bool:
        """Whether stepping this language ever reaches the answer."""
        return self.vm.steppable_to_answer

    def snapshot(self) -> object:
        """Return the wrapped machine's complete state, hashable.

        Mirrored for the reason this class already gives for the traits: a
        caller reaching through ``self.vm`` to get at it is doing the thing
        the mirrors exist to avoid.  And this one is worth reaching for --
        a repeated snapshot proves a loop, which is how the three
        termination languages are settled in microseconds instead of by
        waiting out a clock.
        """
        return self.vm.snapshot()

    # -- breakpoints --------------------------------------------------

    def break_at(self, ip: int | tuple[int, ...]) -> None:
        """Stop when the program counter reaches ``ip``.

        A position is an ``int``, or a tuple of them for the grid languages
        whose ``ip`` is a coordinate.  Anything else is refused rather than
        stored: it compares unequal to every position the machine ever
        reaches, so the breakpoint would simply never fire, and a silently
        dead breakpoint is worse than an error.

        The *kind* is checked against this language too, because the same
        argument applies one level up: ``break_at((1, 2))`` on brainfuck,
        whose ``ip`` is an index, and ``break_at(10)`` on Alight, whose
        ``ip`` is a coordinate, were both stored and both could never fire.

        Only the kind, not the arity.  A tuple ``ip``'s length is the
        language's own -- three for ArrowQueue and Clockwise, four for
        Alight and COD, six for one of them -- and it is not even constant
        within a run: six languages change shape as they go, several to
        ``None`` once the agent they were tracking is consumed, and COD from
        a 4-tuple to an empty one.  So an arity check would refuse
        breakpoints that are perfectly legitimate later in the same run.
        A machine whose ``ip`` is already ``None`` or empty has no shape to
        compare against, and anything is accepted.

        An in-kind position that the program never *reaches* -- ``break_at``
        on index a million, in a program a hundred long -- is accepted and
        will not fire.  That is the same silently-dead breakpoint this
        method refuses elsewhere, and it stays accepted because deciding it
        needs to know how long the program is, which is not part of the VM
        protocol: ``ip`` is language-shaped and there is no ``len``.  Said
        here rather than guessed at.
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

        ``value`` is checked for the same reason ``ip`` is above: a cell
        holds an ``int``, so a breakpoint on anything else never fires.
        """
        check_whole(index, "index")
        if isinstance(value, bool) or not isinstance(value, int):
            raise ArgumentError(f"value must be an integer, got {value!r}")
        self._breakpoints.append(
            lambda vm: index < len(vm.memory) and vm.memory[index] == value
        )

    def break_on_stack(self, slot: int, value: object) -> None:
        """Stop when the ``slot``-th stack value from the top holds ``value``.

        ``value`` is deliberately unchecked -- a stack slot holds whatever
        its language pushes, which is not always an int -- but the slot is
        an index like any other.
        """
        check_whole(slot, "slot")
        self._breakpoints.append(
            lambda vm: slot < len(vm.stack) and vm.stack[-1 - slot] == value
        )

    def break_on_output(self, text: str) -> None:
        """Stop once ``text`` has been written so far.

        Checked here rather than at the stop: a non-string was registered
        without complaint and then raised ``'in <string>' requires string
        as left operand`` from inside the run loop, pointing at the VM
        instead of at the argument.
        """
        if not isinstance(text, str):
            raise ArgumentError(f"text must be a string, got {type(text).__name__}")
        self._breakpoints.append(lambda vm: text in vm.output)

    def break_when(self, predicate: Callable[[VM], bool]) -> None:
        """Stop when ``predicate(vm)`` holds; a catch-all for the rest.

        The predicate takes the VM and returns a bool.  Both halves are
        checked now, because neither failed where it was given: a
        non-callable raised ``'int' object is not callable`` from the run
        loop, and a zero-argument lambda raised ``takes 0 positional
        arguments but 1 was given`` -- each naming the loop rather than the
        setter that accepted it.
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

        **Recording starts here, not at construction**, so steps taken
        before this call leave no entry: watch first, then run.  The list is
        live, so the one returned keeps filling as the machine advances.
        """
        check_whole(index, "index")
        if index not in self._cell_history:
            self._cell_history[index] = []
        return self._cell_history[index]

    def watch_stack(self, slot: int) -> list[object]:
        """Record the ``slot``-th stack value from the top each step.

        A language with no stack records an empty history forever, and
        is not refused: ``stack`` is ``[]`` for those, which is a
        legitimate state rather than an absent one, and the VM protocol
        draws no line between the two.  ``describe(...)["state_model"]``
        is the fact to consult first.
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

    # -- execution ----------------------------------------------------

    def step(self) -> None:
        """Execute one command, recording any watches.

        Past the halt this delegates like any other step, because that is
        where the ``dumps_on_the_post_halt_step`` languages keep their
        answer.  It used to return early on ``halted``, which looks like a
        kindness and cost them their output: for those the dump *is* the
        step after the halt, so refusing to take it left ``output`` empty
        with the machine finished, and the only way through was to reach
        past this class and call ``self.vm.step()``.  A debugger-driven
        verifier scored 62/69 on that alone.

        No count here.  This said "six languages", and six is the size of a
        *different* set -- the one ``answer_mode == "dump"`` picks out,
        which includes A Painter Ant and leaves out ArrowQueue and Point
        Break.  Seven languages dump on the post-halt step.  Two sets that
        overlap in four places are exactly the pair a number in prose gets
        wrong, and :attr:`VM.self_halts` argues against writing one down at
        all.

        The guard was not protecting anything either: an interpreter's
        ``step`` past its halt is a no-op by construction, so the delegation
        is safe for every other language too.
        """
        self.vm.step()
        self._record()

    def run(
        self, max_steps: int | None = None, timeout: float | None = None
    ) -> StopReason:
        """Execute until the machine halts, a breakpoint fires, or a bound ends it.

        Returns *why* it stopped -- ``"halted"``, ``"breakpoint"``,
        ``"max_steps"`` or ``"timeout"``.  It used to return ``None``, on the
        argument that the contract was to stop rather than to report why; but ``halted``
        only separates the first case from the other two, so a caller could
        not tell a breakpoint from an exhausted budget at all, and the CLI
        one layer up was already reporting exactly this.

        A breakpoint is checked before each step, so the run stops with the
        watched condition still true.  **A breakpoint that stopped the last
        run does not fire again until its condition goes false**, which is
        what lets a resumed run advance; see the note on re-firing below.  A
        breakpoint that has not fired yet is checked as it always was, so
        ``break_at(ip)`` on the initial position still stops before the
        first step executes.

        It is checked once more after the machine halts, because otherwise
        a condition the *last* step made true is never looked at and the
        run reports ``"halted"`` over a watch that fired.  The run after
        that one returns ``"halted"``, since the hit is then suppressed.

        ``max_steps`` bounds the run in steps and ``timeout`` in wall-clock
        seconds; the default of ``None`` for both is unbounded, which is
        right for a machine known to halt and a hang for one that is not.
        Either bound *returns* -- ``"max_steps"`` or ``"timeout"`` -- rather
        than raising, so one ``reason ==`` covers every way a run can end and
        a caller bounding both ways needs no ``except`` beside it.  The
        timeout is checked in the same place as a breakpoint rather than
        through a signal, so it needs no main thread and leaves the machine
        inspectable where it stopped.

        The drive itself is :func:`~esolangs.vm.run_until_halt`, and what is
        stepped is ``self`` rather than ``self.vm`` -- :meth:`step` already
        records the watches, so recording stays part of a step instead of
        becoming a hook the shared loop would have to grow.
        """
        if max_steps is not None:
            check_whole(max_steps, "max_steps")
        check_timeout(timeout)
        deadline = None if timeout is None else monotonic() + timeout
        self._timed_out = False
        halted = run_until_halt(self, max_steps, stop=lambda: self._stop(deadline))
        if halted:
            self._warn_about_stdin_once()
            if self.dumps_on_the_post_halt_step:
                # :meth:`step` learned to cross the halt and this did not,
                # so seven languages finished a *run* with an empty
                # ``output`` and the answer one un-taken step away.  Reading
                # it back meant knowing to call ``step()`` again after a
                # method that had already reported ``"halted"``, which is
                # not a thing a caller can be expected to guess -- the CLI's
                # ``debug`` did not, and printed ``output: ''`` for a
                # program that had run correctly.
                #
                # Only for the seven.  The extra step is a no-op everywhere
                # else, but it would still land in every watch history, and
                # a bound that is not needed should not be spent.
                self.step()
            if self._at_breakpoint():
                # A breakpoint is checked *before* a step, so one whose
                # condition the final step makes true was never looked at:
                # ``run_until_halt`` returned, and "halted" was reported
                # over a watch that had fired.  ``break_on_output`` is where
                # that bites, because a program whose last instruction is
                # its output is the ordinary case rather than a corner --
                # the generated brainfuck XOR ends in ``.``, so watching for
                # its answer reported a miss.
                #
                # Checked after the post-halt step, so the seven languages
                # that dump there can be watched for what they dump.  The
                # machine really has halted, which is why the *next* run
                # says so: the hit is suppressed, nothing else fires, and
                # ``halted`` is already true for a caller that asks.
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

        ``run`` warns when a program read fewer lines than it was given, and
        -- the one that matters -- when it read *past* the end on one of the
        languages where the end of input is a value rather than an error.
        That second case is a wrong answer produced in silence: an underfed
        program answers a different row.

        The debugger never said any of it, so the tool you reach for
        *because* you suspect a wrong answer was the one that would not
        mention the commonest cause of one.  Warned at the halt, which is
        where ``run`` warns and the earliest point the counts are final.

        Once per debugger.  ``run`` can be called again on a halted machine
        and returns immediately, and a warning that repeats every time a
        caller re-checks its stop reason is noise.
        """
        if self._warned:
            return
        self._warned = True
        name = getattr(self.vm, "language", None)
        io_obj = getattr(self.vm, "_io", None)
        if name is None or io_obj is None:  # pragma: no cover - every adapter has both
            return
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


def make_debugger(
    language: str, program: str | os.PathLike[str], stdin: str = ""
) -> Debugger:
    """Return a :class:`Debugger` over a fresh :class:`VM` for ``language``.

    ``stdin`` is fed to the program line by line, like :func:`esolangs.run`.
    A language without a step-capable interpreter raises
    :class:`UnknownLanguageError`, as with :func:`esolangs.make_vm`.
    """
    return Debugger(make_vm(language, program, stdin))
