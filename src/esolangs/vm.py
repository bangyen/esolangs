"""A step-and-inspect interface for the interpreter suite.

:func:`make_vm` wraps one of the step-capable interpreters in a :class:`VM`
that exposes the run state between commands: ``step()`` executes one command,
and the ``halted``/``output``/``ip``/``memory``/``stack`` properties describe
the machine after it.  The fields are language-shaped rather than uniform:
a tape language exposes its cells and code cursor, an OISC its cells and
instruction pointer, and a stack language its stack (empty ``stack`` where a
language has none).

Every registered interpreter exposes a ``step()``/``halted`` state object,
so every language in the registry can be wrapped; only an unregistered name
is refused.

Three of the languages' conventions defeat the obvious driving loop, so the
:class:`VM` reports them rather than leaving a caller to find out:
``self_halts`` is ``False`` where ``halted`` never becomes true,
``dumps_on_the_post_halt_step`` is ``True`` where the output is written on
the step after the halt, and ``steppable_to_answer`` is ``False`` where no
number of steps reaches the answer at all.  ``while not vm.halted:
vm.step()`` hangs on the first group and returns ``""`` on the second, and
neither is discoverable from the protocol alone.  A hang detector below is
the other way to drive the first group, and takes the bound off the caller
entirely.

The third group has one member, A Painter Ant, and it is not a hang that a
bound fixes: the language is an unconditional infinite loop whose answer is
the *painted grid* once the ant's walk provably repeats, so
:func:`esolangs.run` proves the cycle and renders, and stepping -- which
can only ever be mid-walk -- has nothing to read.  Three million steps
produce ``halted=False`` and ``output=''``.  That is a property of the
language rather than a defect to route around, so it is stated as one:
a caller that steps consults the flag and uses :func:`esolangs.run`.

The five hang detectors here -- :func:`run_until_halt_or_cycle`,
:func:`run_until_halt_or_all_branches_cycle`,
:func:`run_until_halt_or_ancestor`, :func:`run_until_halt_or_growth`, and
:func:`run_until_halt_or_value_growth` --
each take either a :class:`VM` or the interpreter state one wraps, so
proving a hang needs nothing more than :func:`make_vm`.  What a detector
needs beyond stepping is a *sub*-protocol that only some languages have: a
call stack to compare frames across, enumerable random outcomes to fork, a
growing tape, or unbounded cells on a fixed one.  A language lacking one
raises :class:`TypeError` rather than being handed a verdict about state it
does not keep.

:func:`run_until_halt` sits beside them and proves nothing: it steps a
machine to its halt within a budget and reports whether it got there.
That is the loop every consumer of :func:`make_vm` was writing itself.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Hashable, Sequence
from functools import cache
from typing import Any, Protocol, cast, runtime_checkable

from esolangs.exceptions import (
    InterpreterLimitError,
    ProgramError,
    UnknownLanguageError,
)
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import RUNNERS, resolve


@runtime_checkable
class _StepMachine(Protocol):
    """The minimal step-capable surface the hang detector steps on.

    ``snapshot()`` must return a hashable tuple of the machine's *complete*
    internal state, including the input cursor, or a "repeat" is not a
    real cycle.
    """

    def step(self) -> None:
        """Execute one instruction, advancing the machine."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""

    def snapshot(self) -> Hashable:
        """Return the complete internal state, hashable for cycle detection.

        **Opaque, and language-shaped.**  What the tuple holds is whatever
        that interpreter's state is -- a tape and two cursors here, a grid
        and a heading there -- so the positions are not a schema and are not
        named: there is no arrangement that would mean the same thing across
        sixty-nine machines.  It exists to be compared and hashed, which is
        what a cycle detector needs and all it needs.

        Read ``ip``, ``memory``, ``stack`` and ``output`` for state a caller
        can interpret; those *are* uniform and documented individually.
        """


@runtime_checkable
class _StepMachineWithShape(_StepMachine, Protocol):
    """A step-capable machine that also describes its own VM shape.

    The three members are the ones :class:`VM` exposes; an interpreter that
    defines them can be wrapped by :class:`_DelegatingVM` without any
    per-language code in this module.

    They are ``Sequence``, not ``list``, and that is what makes the
    interpreter free to expose its store *directly*.  ``list`` is invariant,
    so a machine holding ``self.stack: list[int]`` -- which several do, under
    exactly this name -- could never satisfy a ``list[object]`` member, and
    could not add a converting property either, because the attribute is the
    name.  ``Sequence`` is covariant, so the live attribute satisfies it as
    it stands, and :class:`_DelegatingVM` materializes the ``list`` that
    :class:`VM` promises.

    That also puts the fresh-copy contract in one place.  A caller must not
    be able to reach back into a machine through ``vm.memory``, and the
    copy that guarantees it belongs at the boundary that owes it rather
    than in every interpreter.
    """

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        """The current code/instruction position."""

    @property
    def memory(self) -> Sequence[int]:
        """The addressable cells, or empty where there is no such store."""

    @property
    def stack(self) -> Sequence[object]:
        """The stack, or empty where the language has none."""


@runtime_checkable
class _BranchingStepMachine(Protocol):
    """A machine whose next random choice can be enumerated exactly.

    The state is deliberately an immutable value rather than the live
    machine.  Exploring one outcome must not consume a random draw, input,
    or output that belongs only to a sibling outcome.
    """

    def branching_snapshot(self) -> Hashable:
        """Return the initial complete state for a branching search."""

    def branching_halted(self, state: Hashable) -> bool:
        """Whether ``state`` has halted."""

    def branching_successors(
        self, state: Hashable, limit: int
    ) -> Sequence[Hashable] | None:
        """Return every next state, or ``None`` when it cannot be forked.

        ``limit`` bounds the outcomes this one transition may materialize.
        A public machine step can itself repeat a random instruction.
        """


def _unwrap(machine: object, protocol: type[Any], role: str) -> object:
    """Return ``machine``, or the interpreter state a :class:`VM` wraps.

    The detectors were written against the interpreters' ``_Machine``
    classes, so every caller reached past :func:`make_vm` and hand-built
    one -- the private class, its ``ScriptedIO``, and for a random language
    the seeded generator, all restated at the call site.  A :class:`VM`
    already holds exactly that machine, constructed exactly that way, so
    accepting one and opening it here removes the reason to import a
    private name.

    The protocol is tried *before* the unwrap, so a raw machine is handed
    straight back and a wrapper is opened only when it is not itself what
    the detector needs.  That order is also what keeps
    :func:`run_until_halt_or_cycle` stepping the object it was given: a
    :class:`VM` forwards ``step``/``halted``/``snapshot`` and so already
    satisfies :class:`_StepMachine`, which is why passing one there worked
    before this function existed and must keep meaning the same thing.

    ``role`` names what the argument failed to be, because the interesting
    failure is not "wrong type" but "this language has no such thing": a
    machine without ``frames`` does not recurse, and one without
    ``branching_successors`` has no random instruction to fork.

    ``protocol`` is ``type[Any]`` and the result is narrowed by a ``cast``
    at each caller, rather than the ``TypeVar`` this shape invites: mypy
    refuses a protocol class where a ``type[T]`` is expected
    (``type-abstract``), since a protocol cannot be instantiated.  The
    ``isinstance`` below is the real check either way.
    """
    if isinstance(machine, protocol):
        return machine
    inner = getattr(machine, "_machine", None)
    if isinstance(inner, protocol):
        return inner
    raise TypeError(
        f"{type(machine).__name__} is not {role}: neither it nor any machine "
        "it wraps provides the required members"
    )


def run_until_halt_or_cycle(machine: _StepMachine | VM) -> bool:
    """Step ``machine`` until it halts or revisits an exact state.

    A deterministic machine that revisits its complete internal state has
    looped forever, so a repeated snapshot is a *proof* of a hang that is
    reported immediately instead of waiting out a wall-clock timeout.
    Returns ``True`` when the machine halts and ``False`` once a cycle is
    proven.  It catches *cycles*, not every hang.  An unbounded-growth loop
    never revisits a state.  On a tape language,
    :func:`run_until_halt_or_growth` proves that class instead; elsewhere
    callers keep a timeout as the backstop for it.

    Uses Brent's cycle-detection algorithm: O(1) snapshots held at once
    (one "tortoise" checkpoint compared against the live machine's state on
    every step) instead of a hash set of every state visited, at the cost of
    stepping up to ~2x further past the cycle's start before ``False`` is
    returned.  Callers must not rely on the machine's state at the moment
    of detection, only on the True/False verdict.

    Takes either a raw interpreter state or a :class:`VM` from
    :func:`make_vm`; see :func:`_unwrap`.
    """
    machine = cast(
        _StepMachine, _unwrap(machine, _StepMachine, "steppable with a snapshot")
    )
    tortoise = machine.snapshot()
    power = 1
    length = 0
    while not machine.halted:
        machine.step()
        length += 1
        # mypy narrows `machine.halted` to Literal[False] from the loop guard
        # and won't re-widen it across `step()`; the explicit local defeats that.
        halted: bool = machine.halted
        if halted:
            return True
        if machine.snapshot() == tortoise:
            return False
        if length == power:
            tortoise = machine.snapshot()
            power *= 2
            length = 0
    return True


def run_until_halt_or_all_branches_cycle(
    machine: _BranchingStepMachine | VM, limit: int = 10_000
) -> bool:
    """Explore random outcomes until one halts or every path is cyclic.

    Returns ``True`` when *some* sequence of random draws halts.  Returns
    ``False`` only after the complete reachable state graph is finite and
    contains no halted state, proving that every sequence of draws runs
    forever.  The latter is the useful extension of
    :func:`run_until_halt_or_cycle` for a random branch: revisiting a state
    on one outcome alone says nothing when another outcome could escape.

    ``limit`` bounds distinct states and the outcomes one public step may
    materialize.  A machine that grows a tape, stack, or other state without
    repeating remains undecided, as does a transition that cannot be forked
    (for example, one that would read future interactive input).  Both raise
    :class:`TimeoutError` rather than being mistaken for a universal hang.
    The search keeps every exact state it has seen, unlike Brent's O(1)
    deterministic detector, because branches can merge after taking
    different random choices.

    Takes either a raw interpreter state or a :class:`VM` from
    :func:`make_vm`; see :func:`_unwrap`.  A language with no random
    instruction has no branching surface to search and raises
    :class:`TypeError` rather than being reported as a hang.
    """
    machine = cast(
        _BranchingStepMachine,
        _unwrap(machine, _BranchingStepMachine, "branch-enumerable"),
    )
    pending = [machine.branching_snapshot()]
    seen: set[Hashable] = set()
    while pending:
        state = pending.pop()
        if state in seen:
            continue
        if len(seen) == limit:
            raise TimeoutError(
                f"undecided after {limit} branching states: the reachable "
                "graph may be unbounded"
            )
        seen.add(state)
        if machine.branching_halted(state):
            return True
        successors = machine.branching_successors(state, limit - len(seen))
        if successors is None:
            raise TimeoutError(
                "undecided: a branching transition needs input that cannot "
                "be safely forked"
            )
        pending.extend(successors)
    return False


@runtime_checkable
class _FramedMachine(Protocol):
    """A :class:`_StepMachine` that also exposes its call stack.

    ``frames`` is the live stack, outermost first, and ``frame_entry_key``
    returns what a frame is *about to run* -- its function, its bindings,
    and the input cursor -- so two frames with equal keys will replay each
    other.  Separate from :class:`_StepMachine` because the cycle detector
    needs neither.
    """

    def step(self) -> None:
        """Execute one instruction, advancing the machine."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""

    @property
    def frames(self) -> Sequence[object]:
        """The live call stack, outermost frame first."""

    def frame_entry_key(self, frame: object) -> Hashable:
        """Return ``frame``'s entry state, hashable and comparable."""


def run_until_halt_or_ancestor(machine: _FramedMachine | VM, limit: int = 64) -> bool:
    """Step ``machine`` until it halts or a call provably replays an ancestor.

    :func:`run_until_halt_or_cycle` cannot catch infinite recursion: a call
    that never returns pushes one frame per step and pops none, so the
    machine's whole-state snapshot grows forever and never repeats.  That is
    the unbounded-growth class -- the same one
    :func:`run_until_halt_or_growth` handles on a tape, where the growing
    state is cells rather than frames -- and it is why recursive languages
    keep a wall-clock backstop, one that deadlocks under ``pytest --cov``
    (see ``docs/walls.md``).

    This is the narrower check that class allows.  Rather than comparing
    whole-machine states across time, it compares each newly-pushed frame
    against the frames already beneath it: if a frame enters the same
    function, with the same bindings, at the same input position as an
    ancestor, it is about to replay exactly what that ancestor is still in
    the middle of, and the recursion cannot terminate.  Returns ``True``
    when the machine halts and ``False`` once such a frame is pushed.

    The input position is part of the key and carries the soundness.  A
    recursion whose base case depends on a byte it has yet to read enters
    with identical bindings every lap and would otherwise be called a hang
    while it is one read away from returning.

    Two things this does not do.  It does not catch every infinite
    recursion -- one whose bindings genuinely differ every lap (``f(x - 1)``
    over unbounded integers) never repeats a key, so callers keep the
    wall-clock backstop for that class.  And it costs O(depth) per push
    rather than the cycle detector's O(1), which is affordable only because
    it runs once per *call*, not once per step.

    ``limit`` bounds the walk in *pushes examined*, not steps, and 64 is
    generous: a repeat that exists at all shows up within a few frames --
    three, for every case the Forbin suite covers -- because the key does
    not vary with how long the program has been running.  Exhausting it
    raises :class:`TimeoutError` rather than returning a verdict, so a
    program the check cannot decide is never silently reported as halting.
    That distinction is what keeps the bound cheap: a caller need not leave
    headroom "just in case", and a mutant that defeats the early return
    fails a test in milliseconds instead of walking ten thousand steps of
    live recursion.

    Takes either a raw interpreter state or a :class:`VM` from
    :func:`make_vm`; see :func:`_unwrap`.  A language with no call stack
    cannot recurse and raises :class:`TypeError` rather than reporting a
    verdict about frames it does not have.
    """
    machine = cast(_FramedMachine, _unwrap(machine, _FramedMachine, "framed"))
    keys: dict[int, Hashable] = {}
    pushes = 0
    while pushes < limit:
        if machine.halted:
            return True
        depth_before = len(machine.frames)
        machine.step()
        if len(machine.frames) <= depth_before:
            continue
        pushes += 1
        depth = len(machine.frames) - 1
        # A shallower frame at this index belongs to a call that has since
        # returned, so drop it rather than compare against a dead ancestor.
        keys = {d: k for d, k in keys.items() if d < depth}
        keys[depth] = machine.frame_entry_key(machine.frames[-1])
        if keys[depth] in [k for d, k in keys.items() if d < depth]:
            return False
    raise TimeoutError(
        f"undecided after {limit} pushed frames: neither halted nor repeated "
        "an ancestor's entry state"
    )


@runtime_checkable
class _TapeMachine(Protocol):
    """A :class:`_StepMachine` on a rightward-growing tape of cells.

    The four members are what the growth certificate compares across two
    visits to one code position.  ``tape`` must be the *committed* tape --
    brainfuck buffers the cell under the pointer, and a logical state with
    two spellings would break the comparison exactly as it would break the
    cycle detector's hash.  ``input_position`` is the input cursor, and it
    carries the soundness the same way ``frame_entry_key``'s does.

    ``ip`` is the language-shaped code position every machine here already
    exposes, and it is only ever used as a dictionary key, never
    arithmetically -- so it is ``Hashable`` rather than ``int``.  That is
    deliberate.  A 2D language's position is a tuple that includes the
    heading, and *must* be: two visits to one grid cell travelling in
    different directions are not the same point in the program, and keying
    on the coordinates alone would compare them as if they were.  Taking
    the machine's own ``ip`` gets that right by construction instead of by
    remembering it per language.

    Together, ``ip``, ``ptr``, ``tape`` and ``input_position`` must be the
    machine's *complete* state -- the same completeness ``snapshot``
    promises the cycle detector.  A register or flag living outside them
    would let two compared visits differ in something the certificate never
    looked at, and the replay argument would not hold.

    Opting in is also a claim about the language, not just about the
    members:

    - a transition reads and writes only the cell under the pointer,
    - the semantics are translation-invariant for ``ptr >= 1`` -- moving
      the whole configuration one cell right changes nothing, which fails
      only at the clamped left edge,
    - the tape grows rightward, by fresh zero cells.

    Brainfuck, BrainIf, Back, 6-5 and Factor satisfy all three.  A language
    with absolute cell addresses (Suffolk's ``<`` resets the pointer to 0,
    Minifuck reads cells 0-7 by index), a wrapping or fixed-size tape
    (Circlefuck, NoComment, Home Row), or leftward growth (Jaune prepends,
    which shifts every existing index) does not, and must not declare this
    protocol -- matching member names is not eligibility.
    """

    def step(self) -> None:
        """Execute one instruction, advancing the machine."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""

    @property
    def ip(self) -> Hashable:
        """The current code position, hashable and compared by equality."""

    @property
    def ptr(self) -> int:
        """The current cell pointer."""

    @property
    def tape(self) -> tuple[int, ...]:
        """The committed cells, index 0 leftmost."""

    def input_position(self) -> int:
        """Return the input cursor, so a reading loop is not a repeat."""


def run_until_halt_or_growth(machine: _TapeMachine | VM, limit: int = 100_000) -> bool:
    """Step ``machine`` until it halts or provably grows without bound.

    :func:`run_until_halt_or_cycle` cannot catch ``+[>+]``.  The tape gets
    one cell longer and the pointer one cell further right every lap, so
    the whole-machine snapshot is new every time and Brent's detector never
    sees a repeat -- that is the unbounded-growth class its docstring hands
    back to a wall-clock timeout.

    This is the check that class allows on a tape.  Instead of comparing
    whole states, it compares two consecutive visits to the *same code
    position* -- the machine's own ``ip``, so a 2D language's heading is
    part of it -- and asks whether the second is the first shifted right.
    Let
    ``d`` be the pointer's displacement between the visits, ``m`` the
    lowest cell the pointer reached in between, and write a hang when all
    of:

    - the input cursor did not move (a ``,`` in the period makes the next
      lap input-dependent, so it is undecided, not a hang),
    - ``d > 0`` and the tape grew by exactly ``d`` fresh cells,
    - ``m >= 1``, so the period never touched the clamped left edge,
    - ``tape2[i + d] == tape1[i]`` for every ``m <= i < len(tape1)``.

    Together those make the second visit's configuration, restricted to the
    cells at or right of ``m``, the first's translated by ``d``.  Since the
    machine reads only the cell under the pointer and its semantics are
    translation-invariant away from the left edge, the period must replay
    at ``+d``, and then again at ``+2d``, forever: an induction, not a
    guess.  Returns ``True`` when the machine halts and ``False`` once such
    a certificate is found.

    Three details that are the whole soundness argument.  ``m >= 1`` is
    what licenses translation: a period that touched cell 0 may have been
    clamped by ``<`` where its shifted copy would not be, and the two would
    diverge.  The lower bound ``i >= m`` rather than ``i >= 0`` is what
    makes ``+[>++]`` provable -- its cell 0 keeps the value 1 while the
    interior fills with 2s, so a full-width shift never matches, while the
    suffix from the period's own minimum does; cells left of ``m`` are
    unreachable for the rest of the run, so their disagreeing is not a
    counterexample.  And the length check is what rules out a shift that
    merely *looks* aligned: the fresh cells must be exactly the ``d`` zeros
    the growth created.

    Consecutive visits retain the full certificate above.  Alongside that,
    a Brent checkpoint discovers an arbitrary repeating phase without a
    caller choosing its length.  It keeps two checkpoints per position,
    rather than one snapshot for every possible period, and applies the
    same certificate measured from the checkpoint instead of the last
    visit, with the minimum tracked since the checkpoint.  And ``d ==
    0`` is not its business: a loop that grows a cell's value rather than
    the tape, such as ``+[<+]``, revisits an exact state once the value
    wraps at 256 and is
    :func:`run_until_halt_or_cycle`'s to prove.

    One growth shape stays out of reach.  ``>+[[<]>[>]+]`` hangs -- each
    lap extends a run of ones -- but every lap walks to cell 0, so its
    visits share a frozen prefix rather than translating, and no
    certificate built from a pair of configurations can close that class:
    a machine that counted its walk's length into ``ip`` (protocol-legal;
    a 2D heading is exactly such state) could halt on a count the pair
    never witnessed, so a frozen-prefix rule would call a halting program
    a hang.  Such periods keep the wall-clock backstop.

    ``limit`` bounds the walk in steps.  Exhausting it raises
    :class:`TimeoutError` rather than returning a verdict, so a program
    this cannot decide is never reported as halting.

    Takes either a raw interpreter state or a :class:`VM` from
    :func:`make_vm`; see :func:`_unwrap`.  A language with no tape has
    nothing to grow and raises :class:`TypeError` rather than a verdict.
    """
    machine = cast(_TapeMachine, _unwrap(machine, _TapeMachine, "a tape machine"))
    # The last visit keeps the broad, one-period certificate.  ``origins``
    # proves a steady wave after its first full phase, while ``waves`` is
    # Brent's O(1)-per-position checkpoint for a phase that begins after a
    # transient.  Both minima are updated on every step because the proof
    # is invalid if the period ever reached the clamped left edge.
    last: dict[Hashable, tuple[int, tuple[int, ...], int]] = {}
    lowest: dict[Hashable, int] = {}
    origins: dict[Hashable, tuple[tuple[int, tuple[int, ...], int], int]] = {}
    waves: dict[Hashable, tuple[tuple[int, tuple[int, ...], int], int, int, int]] = {}
    for _ in range(limit):
        if machine.halted:
            return True
        ip, ptr, tape = machine.ip, machine.ptr, machine.tape
        for position in lowest:
            lowest[position] = min(lowest[position], ptr)
        for position, (before, low) in origins.items():
            origins[position] = (before, min(low, ptr))
        for position, (before, low, power, length) in waves.items():
            waves[position] = (before, min(low, ptr), power, length)
        cursor = machine.input_position()
        current = (ptr, tape, cursor)
        previous = last.get(ip)
        if previous is not None and _grows_forever(previous, current, lowest[ip]):
            return False
        last[ip] = current
        lowest[ip] = ptr

        origin = origins.get(ip)
        if origin is None:
            origins[ip] = (current, ptr)
        else:
            before, low = origin
            if _grows_forever(before, current, low):
                return False

        checkpoint = waves.get(ip)
        if checkpoint is None:
            waves[ip] = (current, ptr, 1, 0)
        else:
            before, low, power, length = checkpoint
            # The backstop for a drifting baseline.  Nothing reaches this
            # return, and the reason is stronger than the old comment here
            # claimed: measured by ablation, each of the three arms proves
            # every growth program in the suite *on its own*, and with all
            # three disabled every one goes undecided.  They are not a
            # pipeline but three independent certificates.
            #
            # That is also why a mutation sweep leaves this whole block
            # alive: mutating one arm's bookkeeping cannot change a verdict
            # the other two reach anyway.  Those survivors are the
            # redundancy, not a missing test, and the redundancy is kept --
            # the corpus is a handful of brainfuck programs, and an arm
            # idle on all of them may still be the only one that decides a
            # shape nobody has written down yet.
            if _grows_forever(before, current, low):  # pragma: no cover - see above
                return False
            length += 1
            if length == power:
                waves[ip] = (current, ptr, power * 2, 0)
            else:
                waves[ip] = (before, low, power, length)
        machine.step()
    raise TimeoutError(
        f"undecided after {limit} steps: neither halted nor grew by a "
        "provable translation"
    )


def _grows_forever(
    before: tuple[int, tuple[int, ...], int],
    after: tuple[int, tuple[int, ...], int],
    lowest: int,
) -> bool:
    """Whether ``after`` is ``before`` translated right by the growth.

    The certificate itself, split out so the four conditions read as the
    list in :func:`run_until_halt_or_growth`'s docstring rather than as one
    expression buried in a loop.
    """
    ptr_before, tape_before, input_before = before
    ptr_after, tape_after, input_after = after
    displacement = ptr_after - ptr_before
    return (
        input_after == input_before
        and displacement > 0
        and len(tape_after) == len(tape_before) + displacement
        and lowest >= 1
        and all(
            tape_after[i + displacement] == tape_before[i]
            for i in range(lowest, len(tape_before))
        )
    )


@runtime_checkable
class _AffineMachine(Protocol):
    """A machine whose cells grow in *value* on a tape that does not grow.

    :func:`run_until_halt_or_growth` proves the other half of the
    unbounded-growth class: a tape that gets longer.  Suffolk's ``>>!``
    loops do neither that nor repeat a state.  Their tape stays one to five
    cells wide and the pointer stays put, while a cell climbs by a constant
    every lap -- 4501, then 9001, then 13501.  Nothing repeats, so the cycle
    detector never fires, and nothing grows, so the tape certificate never
    does either.  Cells here are Python ints, not wrapping bytes, so the
    climb has no ceiling to bring the state back around.

    What makes that provable is the *shape* of the language rather than the
    size of the numbers.  ``values`` is the vector that may grow -- the
    accumulator and the cells -- compared by subtraction.  ``key`` is
    everything else, compared by equality: the code position, the pointer,
    the tape's width.  ``clamp_slack`` exposes the one place a value can
    change the machine's behaviour rather than just its arithmetic.

    Opting in is a claim about the language, checked against its
    transition, not just matching member names:

    - control flow is independent of ``values``.  Suffolk has no branch at
      all: ``ind`` advances and wraps unconditionally, and ``>``, ``<`` and
      ``!`` move the pointer by fixed rules.  So two visits to one ``key``
      ran the same instructions, whatever the cells held.
    - every operation is affine over the values.  ``<``'s ``acc +=
      tape[ptr]`` is a sum, ``!``'s write is ``tape[ptr] + 1 - acc``, and
      both are linear; ``ptr = acc = 0`` is a reset to a constant.
    - every departure from that is a ``max(0, ...)`` clamp, and
      ``clamp_slack`` reports the value being clamped *before* the step
      that clamps it, or ``None`` when the pending step does not clamp.

    The third bullet is the load-bearing one.  A lap is affine only while
    each clamp stays on the side it was on, so a certificate that ignored
    them would be reading two laps and hoping.  A clamp whose slack shrinks
    by a little each lap agrees with itself for a hundred laps and then
    flips, and the run it was "proving" infinite may settle into a repeat
    instead -- a wrong answer, where this file's whole design is to raise
    :class:`TimeoutError` rather than risk one.
    """

    def step(self) -> None:
        """Execute one instruction, advancing the machine."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""

    @property
    def key(self) -> Hashable:
        """The state compared by equality: code position, pointer, width."""

    @property
    def values(self) -> tuple[int, ...]:
        """The unbounded values, compared by subtraction, in a fixed order."""

    @property
    def clamp_slack(self) -> int | None:
        """The pending step's clamped quantity, or ``None`` if it clamps none."""

    def input_position(self) -> int:
        """Return the input cursor, so a reading loop is not a repeat."""


def run_until_halt_or_value_growth(
    machine: _AffineMachine | VM, limit: int = 20_000
) -> bool:
    """Step ``machine`` until it halts or provably grows in value forever.

    The companion to :func:`run_until_halt_or_growth`, for the class that
    one hands back: a fixed-width tape whose *cells* grow without bound.
    Instead of asking whether a later visit is an earlier one shifted
    right, it asks whether three consecutive visits to one ``key`` advance
    by the same vector twice.  Writing ``v1``, ``v2``, ``v3`` for their
    ``values``, a hang is reported when all of:

    - the input cursor did not move across them (a read makes the next lap
      input-dependent, so it is undecided, not a hang),
    - ``key`` is equal at all three, so the laps ran the same code with the
      same pointer on the same width of tape,
    - ``v2 - v1 == v3 - v2``, and that vector is non-zero and has no
      negative component, so the values are strictly climbing,
    - the two laps agree at every clamp: same side of zero, and a slack
      that did not move toward flipping.

    Together those make the lap an affine map that sends ``v2`` to ``v2 +
    d``.  Because control flow does not read the values
    (:class:`_AffineMachine`'s first claim), the only way a later lap could
    differ is a clamp changing side, and the fourth condition rules that
    out: a clamp that is unclamped and whose slack is not falling stays
    unclamped, and one that is clamped and whose slack is not rising stays
    clamped.  So every later lap repeats the same affine effect, ``d`` is
    added forever, and no state ever recurs.  Returns ``True`` when the
    machine halts and ``False`` once such a certificate is found.

    The delta must be seen *twice* rather than once.  A single delta is one
    observation of an affine map, which is consistent with the next lap
    doing something else entirely; seeing it repeat is what pins the map
    down, and the clamp conditions are what carry it forward.

    ``limit`` bounds the walk in steps.  Exhausting it raises
    :class:`TimeoutError` rather than returning a verdict, so a program
    this cannot decide is never reported as halting.

    A step is not a unit of time here.  ``values`` is the whole tape, so a
    program that widens it every step -- ``>`` alone -- costs a step that
    grows with the walk, and the budget buys quadratically less the further
    it runs.  The default is the measured turn of that curve: 20_000 steps
    is about 1.6s on that worst case, while both programs this was written
    for are decided in under a millisecond.  A caller who wants the deeper
    walk can pay for it explicitly.

    Takes either a raw interpreter state or a :class:`VM` from
    :func:`make_vm`; see :func:`_unwrap`.  A language whose values are
    bounded has nothing to prove this way -- a climbing byte wraps, and its
    repeat is :func:`run_until_halt_or_cycle`'s -- and raises
    :class:`TypeError` rather than a verdict.
    """
    machine = cast(
        _AffineMachine, _unwrap(machine, _AffineMachine, "an affine machine")
    )
    # One slack per step, in a single log, and per key the last three steps
    # that visited it.  A lap is then a slice of the log rather than a list
    # of its own: collecting the slacks per waiting key instead would append
    # once for every key still unrevisited, which is quadratic on a program
    # whose key never repeats -- ``>`` alone mints a fresh one every step by
    # widening the tape, and would spend the whole budget before reaching
    # it.  The log costs one append a step, and only a key on its third
    # visit is ever sliced out of it.
    slacks: list[int | None] = []
    visits: dict[Hashable, list[tuple[int, tuple[int, ...], int]]] = {}
    for index in range(limit):
        # Suffolk is the only affine machine, and the wiki's rerun never
        # halts -- its `halted` is a constant False -- so nothing reaches
        # this return.  It stays for the next affine language.
        if machine.halted:  # pragma: no cover - see above
            return True
        slacks.append(machine.clamp_slack)
        key = machine.key
        seen = visits.setdefault(key, [])
        seen.append((index, machine.values, machine.input_position()))
        del seen[:-3]
        if len(seen) == 3 and _climbs_forever(seen, slacks):
            return False
        machine.step()
    raise TimeoutError(
        f"undecided after {limit} steps: neither halted nor climbed by a "
        "provable affine step"
    )


def _climbs_forever(
    visits: list[tuple[int, tuple[int, ...], int]],
    slacks: list[int | None],
) -> bool:
    """Whether three visits advance affinely with every clamp holding.

    The certificate itself, split out so the four conditions read as the
    list in :func:`run_until_halt_or_value_growth`'s docstring rather than
    as one expression buried in a loop.  The two laps are the stretches of
    ``slacks`` between the three visits' steps.
    """
    (start, first, cursor), (split, second, middle), (end, third, last) = visits
    if cursor != middle or middle != last:
        return False
    if not len(first) == len(second) == len(third):
        return False
    step = tuple(b - a for a, b in zip(first, second, strict=True))
    if step != tuple(c - b for b, c in zip(second, third, strict=True)):
        return False
    if not any(step) or any(delta < 0 for delta in step):
        return False
    return _clamps_hold(slacks[start:split], slacks[split:end])


def _clamps_hold(before: list[int | None], after: list[int | None]) -> bool:
    """Whether two laps clamped alike, with no slack drifting toward a flip.

    A clamp already at ``max(0, ...)``'s floor may only sink further; one
    above it may only rise.  Either way the next lap lands on the side this
    one did, which is what lets the affine step repeat.
    """
    if len(before) != len(after):
        return False
    for previous, current in zip(before, after, strict=True):
        if (previous is None) != (current is None):
            return False
        if previous is None or current is None:
            continue
        if (previous >= 0) != (current >= 0):
            return False
        if previous >= 0 and current < previous:
            return False
        if previous < 0 and current > previous:
            return False
    return True


@runtime_checkable
class _SteppableMachine(Protocol):
    """The bare step-and-ask-if-halted surface a bounded drive needs.

    Deliberately smaller than :class:`_StepMachine`: driving a machine to
    its halt never calls ``snapshot()``, and requiring one would exclude
    the very callers this is for.  :class:`~esolangs.debugger.Debugger` is the
    case that matters -- it forwards ``step``/``halted`` and records a
    watch on the way, but keeps no snapshot of its own.
    """

    def step(self) -> None:
        """Execute one command, advancing the machine."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""


def run_until_halt(
    machine: _SteppableMachine | VM,
    limit: int | None = None,
    *,
    stop: Callable[[], bool] | None = None,
) -> bool:
    """Step ``machine`` until it halts, or the budget or ``stop`` ends it.

    The plain bounded drive, as distinct from the five hang detectors
    above: it proves nothing, it just runs a machine and reports whether it
    got to the end.  Returns ``True`` when the machine halted, ``False``
    when it was still going when the run stopped.

    Every consumer of :func:`make_vm` was writing this loop out again --
    ``tests/test_vm_protocol.py`` and :meth:`~esolangs.debugger.Debugger.run`
    among them -- with a different budget each time and a different thing
    done on overrun: an ``AssertionError``, a silent return, a ``False``.
    Those differences are real and stay with the callers.  What is shared is the
    verdict underneath them, and that is all this returns; a caller maps
    ``False`` to its own policy.

    ``limit`` is a bound in steps, and ``None`` means unbounded -- a run
    with no budget is the common case for a machine known to halt, and
    making the caller pass a large number instead would just be a budget
    nobody chose.  ``stop`` is checked *before* each step, so a run that
    ends on it leaves the condition it stopped for still true; that
    ordering is what a breakpoint means, and getting it wrong would report
    the state after the very command the caller wanted to stop before.

    The machine is stepped in place and is left wherever it stopped, which
    is the point: a caller reads ``output``, ``memory``, or its own records
    off it afterwards.
    """
    steps = 0
    while not machine.halted:
        if stop is not None and stop():
            return False
        if limit is not None and steps == limit:
            return False
        machine.step()
        steps += 1
    return True


@runtime_checkable
class VM(Protocol):
    """A step-capable interpreter wrapper.

    ``ip``/``memory``/``stack`` are language-shaped: each adapter exposes
    what the language's state actually is, so a tape language's ``memory``
    is its cells, a stack language's ``stack`` its values, and so on.
    """

    def step(self) -> None:
        """Execute one command, advancing the machine."""

    def snapshot(self) -> Hashable:
        """Return the complete state used by cycle detection."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""

    @property
    def output(self) -> str:
        """Everything the machine has written so far."""

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        """The current code/instruction position, language-shaped.

        A linear language's ``ip`` is an index into its program; a 2D
        language's is a coordinate tuple; a language whose agent has been
        consumed reports ``None``.

        **The tuple's arity is the language's own and is not stable within
        a run.**  This used to promise ``(x, y, heading)``, which is three
        of them: at the start of a run the registry also has 1-, 2-, 4- and
        6-tuples, and *eight* languages change shape as they go -- so a
        caller must read the shape rather than assume one.

        The eight, measured by stepping each to its halt:

        * to ``None``: Basicfuck (from an ``int``), Flowchart, MyScript,
          Super SNUSP
        * to an empty tuple: ``function x(y)``
        * growing and shrinking again: the Algebraic Programming Language
          between 1, 2 and 3, Forþ between 1, 2 and 3, and **COD through
          4, 8, 12 and 16 before ending at 0**

        So the arities a run can actually present are 0, 1, 2, 3, 4, 6, 8,
        12 and 16.  Sizing anything to the largest *initial* arity is the
        mistake this paragraph exists to prevent, and the paragraph itself
        used to invite it: it said six languages and named COD as going to
        an empty tuple, when COD's shape mostly *grows* and reaches four
        times the width the enumeration stopped at.
        :meth:`~esolangs.debugger.Debugger.break_at` checks the kind for
        exactly this reason, and deliberately does not check the arity.

        **What the leading components mean is stable even though the arity
        is not: they are row then column, never x then y.**  A reader
        asking which way round had to work it out by construction, and the
        paragraph above -- correctly refusing to promise a *shape* -- reads
        as though the order were unknowable too.  It is not: of the ten
        grid languages that report a coordinate, Alight and Super SNUSP lay
        their programs on a single row, so the only move they can make is
        along the column, and the *second* component is what changes; Dig,
        Flowchart, LaserFuck and Streetcode each begin by moving
        vertically, and the *first* is what changes.  The rest agree.
        Anything past the second component is the language's own -- a
        heading, a phase -- and is not described here.

        **The row-then-column rule is about those ten and no others.**
        Twenty languages report a tuple: the other ten are not grid
        languages at all -- 3D Brainfuck and Back are tape machines, Eval,
        Forþ and Grapheme stack ones, Interprogck8 and MyScript register
        ones, and APL, Forbin and ``function x(y)`` are their own thing.
        Half of those report a bare ``(0,)``.  Their components are the
        language's own and mean whatever that language needs, so a 4-tuple
        from Back is not a coordinate in row-major order and nothing here
        says it is.  ``describe(...)["state_model"]`` is what separates the
        two groups.
        """

    @property
    def memory(self) -> list[int]:
        """The addressable cells, or ``[]`` where there is no such store."""

    @property
    def stack(self) -> list[object]:
        """The stack, or ``[]`` where the language has none."""

    @property
    def ip_shape(self) -> str:
        """How to read :attr:`ip` as a place in the source, if at all.

        ``"offset"``, the default, means a plain int counting characters
        into the program text, which is what most of the registry reports
        and why they declare nothing.  ``"grid"`` means the first two parts
        are a row and a column, with any rest a heading.  ``"line"`` means
        the first part is a line number.  ``"opaque"`` means the position
        is real but is not a place in the source.

        Every machine reporting a *tuple* declares one of the last three,
        and ``test_a_positional_ip_says_what_it_counts`` enforces it.  The
        shapes that are neither a cell nor a line -- a frame stack whose
        parts are one position each (Forth, Grapheme, Forbin), a depth
        paired with a cursor (MyScript, Eval), a 3-D point and heading (3D
        Brainfuck) -- all look exactly like a ``(row, col)`` and cannot be
        told from one by their values.  Reading them as a cell names a real
        character that is not the one running, so saying ``"opaque"`` is a
        deliberate answer rather than an omission, and an undeclared tuple
        stays a question nobody has answered.
        """

    @property
    def views(self) -> tuple[tuple[str, str], ...]:
        """The machine's own named state, as ``(name, text)`` pairs.

        Every interpreter here re-exposes its private ``_State`` slots as
        named properties -- ``acc``, ``ptr``, ``ind``, and the rest -- and
        those names are the language's own vocabulary for what it is doing.
        They are found rather than listed: the views *are* the property
        descriptors on the machine's class, so reading them off it cannot
        fall out of step with the interpreters the way a table here would.

        Excluded are the five views every language already offers and the
        machinery around them; what is left is what this language chose to
        name.  Two names reading one slot -- ``ind`` and ``ip`` usually do --
        are both shown, because which pair share a slot on purpose is the
        language's business and hiding one would be a guess.
        """

    @property
    def self_halts(self) -> bool:
        """Whether the program can reach a halt of its own.

        ``False`` where the *language* has no halt of its own, so a caller
        driving one has to bound the run itself: a hang detector above, or
        :func:`esolangs.run`'s ``timeout``.

        **It does not promise that a given program runs forever**, and this
        used to say ``while not vm.halted: vm.step()`` never returns, flatly.
        Suffolk refutes that: it has no halt instruction, and it ends when a
        read runs out of input, so the loop returns after 757 steps on a
        generated truth-table program and never on one that reads nothing.
        A Painter Ant is the other ``False`` and does run forever.  So the
        two disagree about the very sentence the trait was described by, and
        what they share is the thing worth saying -- neither *program text*
        contains a halt, so the bound has to come from outside.

        Read as a warning rather than a guarantee: ``False`` means bound the
        run, ``True`` means you need not.  A caller that wants to know
        whether a particular program stops has to ask the program, and
        :meth:`snapshot` is how -- a repeated state proves the loop.

        No count here, and none below.  This used to say "the two
        languages" and its sibling "the four languages"; the sibling was
        wrong -- seven carry it -- because a trait is added by editing an
        interpreter and the tally lives in a different file.  A number in
        prose is a second copy of something the registry already knows, so
        the way to keep it true is not to write it:
        ``[n for n in list_languages() if describe(n)["self_halts"]]``
        cannot drift.
        """

    @property
    def dumps_on_the_post_halt_step(self) -> bool:
        """Whether the output arrives on the step *after* the halt.

        ``True`` where a language's ``run`` ends its loop with one more
        ``step()`` to dump the final tape or registers.  A caller that stops
        at ``halted`` has driven such a program correctly and still holds
        ``""``; one further ``step()`` writes what ``run`` writes, and the
        no-op step is the one after that.
        """

    @property
    def eof_is_a_value(self) -> bool:
        """Whether a read past the end of the input yields a value here.

        The norm is to raise :class:`~esolangs.exceptions.InputExhaustedError`
        and most languages do.  ``True`` marks the ones that take the
        exhausted read as a value instead, so an underfed program answers a
        different row of its table rather than refusing -- which is a wrong
        answer with nothing in the output to show for it.

        Reported rather than changed: the zero-beyond-input convention was
        audited against the wiki pages and settled on purpose.  What was
        actually broken is that :func:`esolangs.run` promised the exception
        for every language, and a caller had no way to learn which ones
        it does not come from.

        **Two languages are not either of those two outcomes**, and the flag
        cannot say so on its own.  Fed one line short of what it wants:

        * **Alight** is ``True`` and does not carry on.  The sentinel
          reaches its arithmetic and it halts with ``cannot apply '+' to
          2.0 and 'eof'`` -- a refusal, which is the safe half of the two
          outcomes but not the one this flag names.
        * **Suffolk** is ``False`` and does not raise.  The exhausted read
          *ends* the program, so it comes back halted with no output and no
          warning.  That is written down under :attr:`self_halts`, which
          says Suffolk "ends when a read runs out of input" -- the same fact
          under a different trait, and not the one a reader checks here.

        Everything else is exactly what the flag says: of the fifty-two
        languages that read stdin, forty-four of the forty-five ``False``
        ones raise, and six of the seven ``True`` ones answer a different
        row and warn with
        :class:`~esolangs.exceptions.InputMismatchWarning`.  Swept, not
        sampled -- and swept with an input one line short rather than an
        empty one, which is a different question: several languages diverge
        on empty stdin instead of reaching the read at all.

        (45 + 7 = 52.  This said six and five, which does not add up to the
        fifty-two in the same sentence -- the kind of claim that refutes
        itself without needing to be measured, and the third count in this
        file to go wrong.  :attr:`self_halts` argues against writing one
        down at all, and it is not wrong.)
        """

    @property
    def steppable_to_answer(self) -> bool:
        """Whether stepping this language ever reaches the answer.

        ``False`` for A Painter Ant alone, and not for want of a bigger
        budget: the answer is the grid rendered *after* the ant's walk is
        proven periodic, so a stepping caller -- always mid-walk -- has
        nothing to read no matter how long it goes.  Three million steps
        leave ``halted`` false and ``output`` empty.

        Distinct from ``self_halts``, which Suffolk also carries and which
        does not imply this: Suffolk writes its answer while being stepped.
        A caller that steps should consult this and fall back to
        :func:`esolangs.run`, which owns the cycle proof and the render.
        """


#: The names a caller already has by other means, so they are not repeated
#: as "the machine's own".  Five are the views every language offers and the
#: rest are machinery -- the snapshot hooks the cycle provers use, and the
#: traits below.  Everything else a machine exposes as a property is state
#: it chose to name, which is exactly what a reader wants to see.
_NOT_A_VIEW = frozenset(
    {
        "ip",
        "memory",
        "stack",
        "output",
        "halted",
        "snapshot",
        "branching_snapshot",
        "branching_halted",
        "branching_successors",
        "frame_entry_key",
        "self_halts",
        "steppable_to_answer",
        "dumps_on_the_post_halt_step",
        "eof_is_a_value",
        "ip_shape",
        "reproducible_seed",
    }
)

#: How many items of a sequence view to show before counting the rest.  A
#: tape can be thousands of cells, and rendering one to text per step would
#: cost more than running the program.
_VIEW_ITEMS = 8


def _read_view(machine: object, name: str) -> str | None:
    """Return ``machine.name`` as short text, or ``None`` if it cannot be read.

    A property that raises is not a view of anything -- several describe
    state that only exists once a run has begun -- and one broken name must
    not take the whole set down with it.  The failure is answered with
    ``None`` rather than a bare ``continue`` at the call site so that
    skipping is a value the caller tests, not control flow hidden in a
    handler.
    """
    try:
        value = getattr(machine, name)
    except Exception:
        return None
    return _abbreviate(value)


def _abbreviate(value: object) -> str:
    """Render ``value`` short enough to sit on one row.

    A long sequence is cut *before* it is turned into text rather than
    after: a four-thousand-cell tape formatted in full and then truncated
    would be the most expensive thing the stepper does.
    """
    if isinstance(value, (list, tuple)) and len(value) > _VIEW_ITEMS:
        return f"{type(value)(value[:_VIEW_ITEMS])!r} +{len(value) - _VIEW_ITEMS} more"
    text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."


class _DelegatingVM:
    """A VM for an interpreter that describes its own shape.

    The language-shaped mapping -- ``ip``/``memory``/``stack``, genuinely
    different for every one of them -- lives on each interpreter's
    ``_Machine`` rather than here, in a file that does not otherwise know
    the languages.  Keeping it next to the state it describes leaves the
    adapter with the per-language detail: how the machine
    is constructed.  Subclasses provide ``__init__`` only; everything else
    forwards, and ``output`` is captured here.

    ``memory`` and ``stack`` are copied on the way out.  The machine may
    hand back its live store -- several expose the list itself, under
    exactly these names -- and a caller holding ``vm.memory`` must not be
    able to write into a running machine through it.  Copying here rather
    than in each interpreter keeps that guarantee in one place, and turns
    the widening from ``Sequence`` into the ``list`` :class:`VM` promises.
    """

    _machine: _StepMachineWithShape

    def __init__(self, stdin: str = "") -> None:
        """Create the input stream every subclass's machine reads from.

        The program is deliberately not taken here.  Each subclass builds
        its own machine and hands the source straight to it, in the shape
        that language wants -- text or lines -- so a copy kept at this level
        was written and never read by anything.  A mutation sweep is what
        found it: replacing the argument with ``None`` changed no test.
        """
        self._io = ScriptedIO(stdin)

    @property
    def output(self) -> str:
        return self._io.getvalue()

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        """Execute one instruction, translating what the interpreter raises.

        :func:`esolangs.run` turns an interpreter's bare ``ValueError``
        into a :class:`~esolangs.exceptions.ProgramError` and its
        ``RecursionError`` into an
        :class:`~esolangs.exceptions.InterpreterLimitError`, and the VM
        path did neither -- so the package's one promise, that every
        deliberate failure derives from ``EsolangError``, held on one of
        the two ways to execute a program and not the other.  Ninety open
        parens in Algebraic Programming Language raised a bare
        ``RecursionError`` here and a clean ``InterpreterLimitError``
        through ``run``.

        A ``try`` costs nothing when nothing is raised, so the hot loop is
        unaffected.
        """
        try:
            self._machine.step()
        except RecursionError as exc:
            raise InterpreterLimitError(
                f"the {type(self).__name__} interpreter recursed deeper than "
                f"CPython's stack limit allows on this program"
            ) from exc
        except ProgramError:
            raise
        except ValueError as exc:
            raise ProgramError(str(exc)) from exc

    def snapshot(self) -> Hashable:
        """Return the underlying machine's complete state."""
        return self._machine.snapshot()

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        return self._machine.ip

    @property
    def memory(self) -> list[int]:
        return list(self._machine.memory)

    @property
    def stack(self) -> list[object]:
        return list(self._machine.stack)

    # The two language conventions a stepping caller cannot discover for
    # itself: that a language never halts, and that its output lands one
    # step past the halt.  Both come off the machine by ``getattr``, the
    # way ``reproducible_seed`` does, and for the same reason -- they are
    # facts about the language, so the interpreter says so and the fifty-odd
    # that follow the common shape declare nothing.
    #
    # The defaults are the common case, which is why the traits are spelled
    # positively on the machines that carry them: a language that says
    # nothing self-halts and writes before it does.

    @property
    def self_halts(self) -> bool:
        return bool(getattr(self._machine, "self_halts", True))

    @property
    def ip_shape(self) -> str:
        return str(getattr(self._machine, "ip_shape", "offset"))

    @property
    def views(self) -> tuple[tuple[str, str], ...]:
        machine = self._machine
        found = []
        for name, attribute in sorted(vars(type(machine)).items()):
            if name.startswith("_") or name in _NOT_A_VIEW:
                continue
            if not isinstance(attribute, property):
                continue
            text = _read_view(machine, name)
            if text is not None:
                found.append((name, text))
        return tuple(found)

    @property
    def dumps_on_the_post_halt_step(self) -> bool:
        return bool(getattr(self._machine, "dumps_on_the_post_halt_step", False))

    @property
    def steppable_to_answer(self) -> bool:
        return bool(getattr(self._machine, "steppable_to_answer", True))

    @property
    def eof_is_a_value(self) -> bool:
        return bool(getattr(self._machine, "eof_is_a_value", False))


def _derived_adapter(language: str) -> Callable[[str, str], _DelegatingVM]:
    """Build the adapter for a language whose wrapper is pure boilerplate.

    Once an interpreter describes its own shape, most adapters differ only
    in which module to import and whether the program is passed as text or
    as lines -- and ``RUNNERS`` already records both, because ``run`` needs
    exactly the same two facts.  Deriving from it means the adapter set
    cannot drift from the runner set, and adding a language that follows
    the common shape needs no code here at all.

    Every registered language now goes through here.  The exceptions that
    once kept a hand-written class -- extra setup, an overridden ``step()``,
    a construction disagreeing with the runner's -- were absorbed by the
    common constructor and ``rng`` handling below, so no per-language code
    is left.
    """
    module_path, split = RUNNERS[language]
    # Bound to another name first: a class body cannot read the enclosing
    # function's ``language`` while binding a class attribute of that name.
    display_name = language

    class _Derived(_DelegatingVM):
        #: The registry's display name for this adapter's language.
        #:
        #: Only the derived class can know it -- ``_DelegatingVM`` is built
        #: from a program and a stdin and never sees a name -- and the
        #: debugger needs it to ask ``describe`` whether a read past the end
        #: of input is a value for this language, which is the difference
        #: between a wrong answer and an exception.
        language = display_name

        def __init__(self, program: str, stdin: str = "") -> None:
            super().__init__(stdin)
            import importlib
            import inspect

            from esolangs.interpreters.randomness import Seeded

            module = importlib.import_module(f"esolangs.interpreters.{module_path}")
            code = program.splitlines() if split else program
            # ``_Machine`` is private to its module but is the state object
            # this whole file is built around; the explicit adapters below
            # import it by name for the same reason.
            state = getattr(module, "_Machine")  # noqa: B009
            # A language with a random instruction takes a source for it,
            # and a stepped VM has to be reproducible, so one is passed
            # wherever it is accepted.  It is optional exactly like ``io``
            # is: the interpreter falls back to ``secrets`` without it.
            #
            # The seed comes from the machine.  Which draw a language
            # wants to start from is a fact about that language -- COD's
            # own junction example goes East, LaserFuck's grids are
            # written for a laser heading up -- so the interpreter says
            # so, rather than every caller having to know.
            if "rng" in inspect.signature(state).parameters:
                seed = getattr(state, "reproducible_seed", 0)
                self._machine = state(code, self._io, rng=Seeded(seed))
            else:
                self._machine = state(code, self._io)

    _Derived.__name__ = _Derived.__qualname__ = f"_{language}VM"
    _Derived.__doc__ = f"Adapter for {language}; the interpreter describes its shape."
    return _Derived


# Language name -> VM adapter.  Every registered language is step-capable,
# so every one gets a derived adapter and an unregistered name is the only
# thing that raises UnknownLanguageError.  The set is read off ``RUNNERS``
# rather than listed again here: a second copy of every name is a
# second thing to keep in step, and the test that used to guard the pair
# existed only to catch the two drifting apart, so deriving the dict
# retired it.  Building an adapter imports nothing -- the
# interpreter is imported inside the adapter's ``__init__`` -- so this
# stays as lazy as the hand-written table was.
# Typed as what it is used as -- a factory taking the program and the input
# -- rather than as the base class.  A derived adapter takes both, while
# ``_DelegatingVM`` itself takes only the input: the program never belonged
# at that level, since each subclass hands the source straight to its own
# machine in the shape that language wants.
_VM_ADAPTERS: dict[str, Callable[[str, str], _DelegatingVM]] = {
    name: _derived_adapter(name) for name in RUNNERS
}


@cache
def machine_traits(language: str) -> dict[str, bool]:
    """Return ``language``'s three driving traits without running anything.

    The same ``self_halts`` / ``dumps_on_the_post_halt_step`` /
    ``steppable_to_answer`` a :class:`VM` exposes, read off the interpreter's
    state *class* rather than an instance, so :func:`esolangs.describe` can
    report them.  It could not before: the traits were reachable only
    through a VM, which needs a program, which for seventeen languages needs
    the bits -- so a caller deciding *how to drive* a language had to first
    build the thing it was deciding about.

    The defaults match the wrapper's, and for the same reason: they are the
    common case, so the fifty-odd languages that follow it declare nothing
    and only the exceptions carry a line.
    """
    import importlib

    # No membership check beyond ``resolve``: it only ever returns a name in
    # the registry, and the registry and ``RUNNERS`` are the same 69 names,
    # so a second guard here would be a line no input can reach.
    name = resolve(language)
    module = importlib.import_module(f"esolangs.interpreters.{RUNNERS[name][0]}")
    state = getattr(module, "_Machine")  # noqa: B009
    return {
        "self_halts": bool(getattr(state, "self_halts", True)),
        "dumps_on_the_post_halt_step": bool(
            getattr(state, "dumps_on_the_post_halt_step", False)
        ),
        "steppable_to_answer": bool(getattr(state, "steppable_to_answer", True)),
        "eof_is_a_value": bool(getattr(state, "eof_is_a_value", False)),
    }


def make_vm(language: str, program: str | os.PathLike[str], stdin: str = "") -> VM:
    """Return a step-and-inspect wrapper around ``language``'s interpreter.

    The wrapper exposes ``step()``, ``halted``, ``output``, ``ip``,
    ``memory``, and ``stack`` between commands.  ``stdin`` is fed to the
    program line by line, like :func:`esolangs.run`.  The name is resolved
    case-insensitively by :func:`~esolangs.registry.resolve`, as everywhere
    else in the API; every registered language is step-capable, so only a
    name outside the registry raises :class:`UnknownLanguageError`.

    The program and ``stdin`` are checked exactly as :func:`esolangs.run`
    checks them, and for the same reason: stepping is the *other* way to
    execute a program.  An unfilled ``{Xi}`` template ran here all the way
    to a confident ``output: '0'`` and was reported as an answer, and a
    ``None`` program raised ``'NoneType' is not a container or iterable``
    from inside an interpreter rather than being named at the boundary.

    ``program`` may be a :class:`~pathlib.Path`, exactly as ``run`` allows.
    The check was already shared; its *return value* was not, so a path was
    validated -- read off disk, and found to be a fine program -- and then
    handed to the interpreter unread, which met it with ``'PosixPath'
    object is not iterable``.  Checking a value and using it have to be the
    same expression or they drift, which is the whole argument for
    :mod:`esolangs._validate`.
    """
    from esolangs import check_program

    name = resolve(language)
    if name not in _VM_ADAPTERS:
        raise UnknownLanguageError(language)
    source = check_program(name, program, stdin)
    try:
        return _VM_ADAPTERS[name](source, stdin)
    except RecursionError as exc:
        raise InterpreterLimitError(
            f"the {name} interpreter recursed deeper than CPython's stack "
            f"limit allows while loading this program "
            f"({len(source)} characters)"
        ) from exc
    except ProgramError:
        raise
    except ValueError as exc:
        # Most interpreters parse in their constructor and signal a
        # malformed program with a plain ``ValueError``.  ``run``
        # re-raises those as ``ProgramError``; this did not, so
        # ``make_vm("brainfuck", "]")`` leaked one -- for 48 of the 69.
        raise ProgramError(str(exc)) from exc
