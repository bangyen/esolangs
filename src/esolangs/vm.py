"""A step-and-inspect interface for the interpreter suite.

:func:`make_vm` wraps a registered interpreter in a :class:`VM` exposing the
run state between commands.  ``ip``/``memory``/``stack`` are language-shaped
rather than uniform, and empty where a language has no such store.

Three conventions defeat ``while not vm.halted: vm.step()``, so the VM
reports them: ``self_halts`` is ``False`` where ``halted`` never becomes
true, ``dumps_on_the_post_halt_step`` is ``True`` where the output lands on
the step after the halt, and ``steppable_to_answer`` is ``False`` where no
number of steps reaches the answer (A Painter Ant alone, whose answer is the
grid rendered once the walk is proven periodic -- use :func:`esolangs.run`).

The five hang detectors -- :func:`run_until_halt_or_cycle`,
:func:`run_until_halt_or_all_branches_cycle`,
:func:`run_until_halt_or_ancestor`, :func:`run_until_halt_or_growth` and
:func:`run_until_halt_or_value_growth` -- take either a :class:`VM` or the
interpreter state one wraps.  Each needs a sub-protocol only some languages
have; one lacking it raises :class:`TypeError` rather than being handed a
verdict about state it does not keep.  :func:`run_until_halt` proves
nothing and just drives a machine to its halt within a budget.
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

        Opaque and language-shaped: the tuple exists to be compared and
        hashed, not read.  ``ip``, ``memory``, ``stack`` and ``output`` are
        the interpretable views.
        """


@runtime_checkable
class _StepMachineWithShape(_StepMachine, Protocol):
    """A step-capable machine that also describes its own VM shape.

    An interpreter defining these three can be wrapped by
    :class:`_DelegatingVM` with no per-language code here.

    ``Sequence`` rather than ``list`` so a machine may expose its store
    directly: ``list`` is invariant, so ``self.stack: list[int]`` could
    never satisfy a ``list[object]`` member.  :class:`_DelegatingVM`
    materializes the ``list`` :class:`VM` promises, which also keeps the
    fresh-copy contract -- no reaching back into a running machine through
    ``vm.memory`` -- at the one boundary that owes it.
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

    The protocol is tried *before* the unwrap, so a raw machine is handed
    back and a wrapper opened only when it is not itself what the detector
    needs -- which keeps :func:`run_until_halt_or_cycle` stepping the object
    it was given, since a :class:`VM` already satisfies
    :class:`_StepMachine`.

    ``role`` names what the argument failed to be: the interesting failure
    is not "wrong type" but "this language has no such thing".

    ``protocol`` is ``type[Any]`` with a ``cast`` at each caller rather than
    a ``TypeVar``: mypy refuses a protocol class where ``type[T]`` is
    expected, since a protocol cannot be instantiated.
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
    looped forever, so a repeated snapshot *proves* a hang rather than
    waiting out a wall-clock timeout.  Returns ``True`` on a halt and
    ``False`` once a cycle is proven.  It catches cycles, not every hang: an
    unbounded-growth loop never revisits a state, and is
    :func:`run_until_halt_or_growth`'s on a tape and a timeout's elsewhere.

    Brent's algorithm: O(1) snapshots held at once, at the cost of stepping
    up to ~2x past the cycle's start.  Callers may rely on the verdict, not
    on the machine's state at detection.

    Takes a raw interpreter state or a :class:`VM`; see :func:`_unwrap`.
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

    Returns ``True`` when *some* sequence of draws halts, and ``False`` only
    once the reachable graph is finite and holds no halted state.  A cycle
    on one outcome says nothing on its own, which is why
    :func:`run_until_halt_or_cycle` does not extend to a random branch.

    ``limit`` bounds distinct states and the outcomes one public step may
    materialize.  State that grows without repeating, or a transition that
    cannot be forked (one reading future interactive input), raises
    :class:`TimeoutError` rather than being mistaken for a universal hang.
    Every state seen is kept, unlike Brent's O(1) detector, because branches
    can merge after different draws.

    Takes a raw interpreter state or a :class:`VM`; see :func:`_unwrap`.  A
    language with no random instruction raises :class:`TypeError`.
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

    ``frames`` is the live stack, outermost first; ``frame_entry_key``
    returns what a frame is *about to run* -- function, bindings and input
    cursor -- so two frames with equal keys will replay each other.
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

    Infinite recursion is the unbounded-growth class the cycle detector
    hands back: a call that never returns pushes a frame per step, so the
    whole-state snapshot never repeats.  This compares each newly-pushed
    frame against those beneath it instead: a frame entering the same
    function, with the same bindings, at the same input position as an
    ancestor is about to replay what that ancestor is still in the middle
    of.  Returns ``True`` on a halt and ``False`` once such a frame lands.

    The input position carries the soundness.  A recursion whose base case
    depends on a byte it has yet to read enters with identical bindings
    every lap, and would otherwise be called a hang one read from returning.

    It misses a recursion whose bindings genuinely differ every lap
    (``f(x - 1)`` over unbounded integers), which keeps a wall-clock
    backstop, and costs O(depth) per push -- affordable only because it runs
    once per *call*.

    ``limit`` bounds *pushes examined*, not steps; 64 is generous, since a
    repeat that exists at all shows up within a few frames (three across the
    Forbin suite) because the key does not vary with elapsed run time.
    Exhausting it raises :class:`TimeoutError` rather than a verdict, so an
    undecided program is never reported as halting.

    Takes a raw interpreter state or a :class:`VM`; see :func:`_unwrap`.  A
    language with no call stack raises :class:`TypeError`.
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
    two spellings breaks the comparison.  ``input_position`` carries the
    soundness the way ``frame_entry_key`` does.

    ``ip`` is ``Hashable`` rather than ``int`` because it is only ever a
    dictionary key: a 2D language's position includes its heading, and must,
    since two visits to one cell travelling different ways are not the same
    point in the program.

    Together the four must be the machine's *complete* state, the
    completeness ``snapshot`` promises: a register outside them would let
    two compared visits differ in something the certificate never read.

    Opting in is also a claim about the language, not just about the
    members:

    - a transition reads and writes only the cell under the pointer,
    - the semantics are translation-invariant for ``ptr >= 1`` -- moving
      the whole configuration one cell right changes nothing, which fails
      only at the clamped left edge,
    - the tape grows rightward, by fresh zero cells.

    Brainfuck, BrainIf, Back, 6-5 and Factor satisfy all three.  Absolute
    cell addresses (Suffolk, Minifuck), a wrapping or fixed-size tape
    (Circlefuck, NoComment, Home Row) or leftward growth (Jaune prepends)
    do not, and must not declare this protocol -- matching member names is
    not eligibility.
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

    ``+[>+]`` grows the tape a cell a lap, so the whole-machine snapshot is
    new every time and the cycle detector never fires.  This compares two
    consecutive visits to the *same code position* -- the machine's own
    ``ip``, so a 2D heading is part of it -- and asks whether the second is
    the first shifted right.  Let ``d`` be the pointer's displacement
    between the visits and ``m`` the lowest cell reached in between; a hang
    is written when all of:

    - the input cursor did not move (a ``,`` in the period makes the next
      lap input-dependent, so it is undecided, not a hang),
    - ``d > 0`` and the tape grew by exactly ``d`` fresh cells,
    - ``m >= 1``, so the period never touched the clamped left edge,
    - ``tape2[i + d] == tape1[i]`` for every ``m <= i < len(tape1)``.

    Together those make the second visit, restricted to cells at or right of
    ``m``, the first translated by ``d``.  Since the machine reads only the
    cell under the pointer and is translation-invariant away from the left
    edge, the period replays at ``+d``, then ``+2d``, forever -- an
    induction, not a guess.  Returns ``True`` on a halt and ``False`` once
    the certificate holds.

    Each condition earns its place.  ``m >= 1`` licenses the translation: a
    period touching cell 0 may have been clamped by ``<`` where its shifted
    copy would not.  The bound ``i >= m`` rather than ``i >= 0`` is what
    makes ``+[>++]`` provable, whose cell 0 keeps the value 1 while the
    interior fills with 2s; cells left of ``m`` are unreachable for the rest
    of the run.  The length check rules out a shift that merely looks
    aligned: the fresh cells must be exactly the ``d`` zeros growth created.

    Alongside consecutive visits, a Brent checkpoint per position finds a
    repeating phase without a caller choosing its length, applying the same
    certificate from the checkpoint with the minimum tracked since it.
    ``d == 0`` is not its business: ``+[<+]`` revisits an exact state once
    the value wraps, and is :func:`run_until_halt_or_cycle`'s.

    ``>+[[<]>[>]+]`` stays out of reach -- every lap walks to cell 0, so its
    visits share a frozen prefix rather than translating, and no pair of
    configurations can close that class: a machine counting its walk into
    ``ip`` (protocol-legal) could halt on a count the pair never saw.

    ``limit`` bounds the walk in steps; exhausting it raises
    :class:`TimeoutError` rather than a verdict.  Takes a raw interpreter
    state or a :class:`VM`; a language with no tape raises
    :class:`TypeError`.
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
            # return: by ablation each of the three arms proves every growth
            # program in the suite on its own, so they are three independent
            # certificates rather than a pipeline, and a mutation sweep
            # leaves this block alive for the same reason.  The redundancy
            # is kept -- the corpus is a handful of brainfuck programs, and
            # an arm idle on all of them may be the only one that decides a
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

    Split out so the four conditions read as the list in
    :func:`run_until_halt_or_growth`'s docstring.
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

    Suffolk's ``>>!`` loops neither repeat a state nor grow the tape: it
    stays one to five cells wide while a cell climbs by a constant every lap
    (4501, 9001, 13501), and the cells are Python ints with no wrap to bring
    the state back around.

    ``values`` is the vector that may grow -- accumulator and cells --
    compared by subtraction.  ``key`` is everything else, compared by
    equality: code position, pointer, tape width.  ``clamp_slack`` exposes
    the one place a value changes behaviour rather than just arithmetic.

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

    The third bullet is load-bearing: a lap is affine only while each clamp
    stays on the side it was on.  A clamp whose slack shrinks a little each
    lap agrees with itself for a hundred laps and then flips, and the run
    it was "proving" infinite may settle into a repeat instead.
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

    The companion to :func:`run_until_halt_or_growth`, for the class it
    hands back: a fixed-width tape whose *cells* grow without bound.  It
    asks whether three consecutive visits to one ``key`` advance by the same
    vector twice.  Writing ``v1``, ``v2``, ``v3`` for their ``values``, a
    hang is reported when all of:

    - the input cursor did not move across them (a read makes the next lap
      input-dependent, so it is undecided, not a hang),
    - ``key`` is equal at all three, so the laps ran the same code with the
      same pointer on the same width of tape,
    - ``v2 - v1 == v3 - v2``, and that vector is non-zero and has no
      negative component, so the values are strictly climbing,
    - the two laps agree at every clamp: same side of zero, and a slack
      that did not move toward flipping.

    Together those make the lap an affine map sending ``v2`` to ``v2 + d``.
    Control flow does not read the values (:class:`_AffineMachine`'s first
    claim), so the only way a later lap could differ is a clamp changing
    side, which the fourth condition rules out.  Every later lap therefore
    repeats the same effect and no state recurs.  Returns ``True`` on a halt
    and ``False`` once the certificate holds.

    The delta must be seen *twice*: one observation of an affine map is
    consistent with the next lap doing something else entirely.

    ``limit`` bounds the walk in steps; exhausting it raises
    :class:`TimeoutError` rather than a verdict.  A step is not a unit of
    time here -- ``values`` is the whole tape, so ``>`` alone costs a step
    that grows with the walk.  20_000 is the measured turn of that curve,
    about 1.6s on that worst case against under a millisecond for both
    programs this was written for.

    Takes a raw interpreter state or a :class:`VM`; see :func:`_unwrap`.  A
    language whose values are bounded raises :class:`TypeError` -- a
    climbing byte wraps, and its repeat is
    :func:`run_until_halt_or_cycle`'s.
    """
    machine = cast(
        _AffineMachine, _unwrap(machine, _AffineMachine, "an affine machine")
    )
    # One slack per step in a single log, and per key the last three steps
    # that visited it, so a lap is a slice rather than a list of its own.
    # Collecting slacks per waiting key would append once for every key
    # still unrevisited -- quadratic on a program whose key never repeats,
    # such as ``>`` alone widening the tape every step.
    slacks: list[int | None] = []
    visits: dict[Hashable, list[tuple[int, tuple[int, ...], int]]] = {}
    for index in range(limit):
        # Suffolk is the only affine machine and never halts, so nothing
        # reaches this return; it stays for the next affine language.
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

    Split out so the four conditions read as the list in
    :func:`run_until_halt_or_value_growth`'s docstring.  The two laps are
    the stretches of ``slacks`` between the three visits' steps.
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

    Smaller than :class:`_StepMachine` on purpose: a bounded drive never
    calls ``snapshot()``, and requiring one would exclude
    :class:`~esolangs.debugger.Debugger`, which forwards ``step``/``halted``
    but keeps no snapshot of its own.
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

    The plain bounded drive, proving nothing: ``True`` when the machine
    halted, ``False`` when it was still going.  What a caller does on
    ``False`` is its own policy.

    ``limit`` is a bound in steps, ``None`` unbounded.  ``stop`` is checked
    *before* each step, so a run ending on it leaves the condition still
    true -- that ordering is what a breakpoint means.

    The machine is stepped in place and left where it stopped, so a caller
    can read ``output``, ``memory`` or its own records off it.
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
        """Return the internal state cycle detection compares, hashable.

        Internal, not everything: ``output`` is excluded, so two snapshots
        compare equal across a step that wrote something (the post-halt dump
        does, on seven languages).  Equal internal state means the same
        future, which is what the loop proof needs; it is not a state diff.
        """

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

        **The tuple's arity is the language's own and is not stable within a
        run.**  Initial arities run 1, 2, 3, 4 and 6, and six languages
        change shape as they go: Flowchart and Super SNUSP to ``None``,
        ``function x(y)`` to an empty tuple, and the Algebraic Programming
        Language, Forþ and COD growing and shrinking again -- COD through 4,
        8, 12 and 16 before ending at 0.  So a run can present 0, 1, 2, 3,
        4, 6, 8, 12 and 16, and sizing anything to the largest *initial*
        arity is the mistake.  :meth:`~esolangs.debugger.Debugger.break_at`
        checks the kind for this reason and deliberately not the arity.

        **The leading components are row then column, never x then y.**  Of
        the ten grid languages reporting a coordinate, Alight and Super
        SNUSP lie on a single row so only the second component moves, while
        Dig, Flowchart, LaserFuck and Streetcode begin vertically so the
        first does.  Anything past the second is the language's own.

        That rule covers those ten and no others.  Nine more languages
        report a tuple without being grids -- 3D Brainfuck and Back are tape
        machines, Eval, Forþ and Grapheme stack ones, Interprogck8 a
        register one, and APL, Forbin and ``function x(y)`` their own thing
        -- and their components mean whatever that language needs.
        ``describe(...)["state_model"]`` separates the two groups.
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

        ``"offset"``, the default, is a plain int counting characters into
        the program text.  ``"grid"`` means the first two parts are a row
        and a column, any rest a heading; ``"line"`` that the first part is
        a line number; ``"opaque"`` that the position is real but is not a
        place in the source.

        Every machine reporting a *tuple* declares one of the last three,
        enforced by ``test_a_positional_ip_says_what_it_counts``.  A frame
        stack (Forth, Grapheme, Forbin), a depth and cursor (Eval) or a 3-D
        point and heading (3D Brainfuck) all look exactly like a
        ``(row, col)``, and reading one as a cell names a real character
        that is not the one running -- so ``"opaque"`` is an answer, and an
        undeclared tuple is a question nobody has answered.
        """

    @property
    def views(self) -> tuple[tuple[str, str], ...]:
        """The machine's own named state, as ``(name, text)`` pairs.

        Found rather than listed: the views *are* the property descriptors
        on the machine's class, so they cannot fall out of step with the
        interpreters the way a table here would.  :data:`_NOT_A_VIEW`
        excludes the views every language already offers and the machinery
        around them; what is left is what this language chose to name.  Two
        names reading one slot (``ind`` and ``ip`` usually do) are both
        shown, since which pair share one is the language's business.
        """

    @property
    def self_halts(self) -> bool:
        """Whether the program can reach a halt of its own.

        ``False`` where the *language* has no halt, so a caller has to bound
        the run itself -- a hang detector above, or :func:`esolangs.run`'s
        ``timeout``.

        It does not promise that a given program runs forever.  Suffolk has
        no halt instruction but ends when a read runs out of input, so the
        driving loop returns after 757 steps on a generated truth-table
        program and never on one that reads nothing; A Painter Ant, the
        other ``False``, does run forever.  What they share is that neither
        *program text* contains a halt, so the bound comes from outside.

        A warning rather than a guarantee: ``False`` means bound the run.
        Whether a particular program stops is :meth:`snapshot`'s question --
        a repeated state proves the loop.

        No count of the languages carrying it, here or below: a trait is
        added by editing an interpreter, so a tally in prose drifts.
        ``[n for n in list_languages() if describe(n)["self_halts"]]``
        cannot.
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

        The norm is to raise
        :class:`~esolangs.exceptions.InputExhaustedError`.  ``True`` marks
        the languages that take the exhausted read as a value instead, so an
        underfed program answers a different row of its table rather than
        refusing.  Reported rather than changed: the zero-beyond-input
        convention is deliberate, and what was broken is that
        :func:`esolangs.run` promised the exception for every language.

        **Two languages are neither outcome**, and the flag cannot say so.
        Fed one line short, Alight is ``True`` but does not carry on -- the
        sentinel reaches its arithmetic and it halts with ``cannot apply '+'
        to 2.0 and 'eof'`` -- while Suffolk is ``False`` but does not raise,
        since the exhausted read *ends* the program (see :attr:`self_halts`).

        Everything else is what the flag says, swept rather than sampled and
        swept one line short rather than empty: of the fifty-two languages
        reading stdin, forty-four of the forty-five ``False`` ones raise,
        and six of the seven ``True`` ones answer a different row and warn
        with :class:`~esolangs.exceptions.InputMismatchWarning`.
        """

    @property
    def steppable_to_answer(self) -> bool:
        """Whether stepping this language ever reaches the answer.

        ``False`` for A Painter Ant alone, and not for want of a bigger
        budget: the answer is the grid rendered *after* the walk is proven
        periodic, so a stepping caller is always mid-walk and three million
        steps leave ``halted`` false and ``output`` empty.  Distinct from
        ``self_halts``, which Suffolk also carries while still writing its
        answer under stepping.  Fall back to :func:`esolangs.run`, which
        owns the cycle proof and the render.
        """


#: The names a caller already has by other means -- the views every language
#: offers, the snapshot hooks the cycle provers use, and the traits -- so
#: they are not repeated as "the machine's own".
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
#: tape can be thousands of cells, and rendering one per step would cost
#: more than running the program.
_VIEW_ITEMS = 8


def _read_view(machine: object, name: str) -> str | None:
    """Return ``machine.name`` as short text, or ``None`` if it cannot be read.

    Several properties describe state that only exists once a run has begun,
    and one raising must not take the whole set down.  ``None`` rather than
    a ``continue`` at the call site, so skipping is a value the caller tests.
    """
    try:
        value = getattr(machine, name)
    except Exception:
        return None
    return _abbreviate(value)


def _abbreviate(value: object) -> str:
    """Render ``value`` short enough to sit on one row.

    A long sequence is cut *before* it is turned into text: a
    four-thousand-cell tape formatted in full and then truncated would be
    the most expensive thing the stepper does.
    """
    if isinstance(value, (list, tuple)) and len(value) > _VIEW_ITEMS:
        return f"{type(value)(value[:_VIEW_ITEMS])!r} +{len(value) - _VIEW_ITEMS} more"
    text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."


class _DelegatingVM:
    """A VM for an interpreter that describes its own shape.

    The language-shaped ``ip``/``memory``/``stack`` mapping lives on each
    interpreter's ``_Machine`` rather than here, leaving the adapter only
    the per-language detail of how the machine is constructed.  Subclasses
    provide ``__init__``; everything else forwards, and ``output`` is
    captured here.

    ``memory`` and ``stack`` are copied on the way out: several machines
    expose the live list under exactly these names, and a caller holding
    ``vm.memory`` must not be able to write into a running machine.  That
    also widens ``Sequence`` to the ``list`` :class:`VM` promises.
    """

    _machine: _StepMachineWithShape

    def __init__(self, stdin: str = "") -> None:
        """Create the input stream every subclass's machine reads from.

        The program is deliberately not taken here: each subclass hands the
        source straight to its own machine in the shape that language wants,
        so a copy at this level would be written and never read.
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

        Stepping is the other way to execute a program, so it owes the same
        promise :func:`esolangs.run` makes: every deliberate failure derives
        from ``EsolangError``.  A bare ``ValueError`` becomes a
        :class:`~esolangs.exceptions.ProgramError` and a ``RecursionError``
        an :class:`~esolangs.exceptions.InterpreterLimitError`.
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

    # The traits come off the machine by ``getattr``, the way
    # ``reproducible_seed`` does: they are facts about the language, so the
    # interpreter declares them and the fifty-odd following the common shape
    # say nothing.  The defaults are that common case.

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

    Once an interpreter describes its own shape, an adapter differs only in
    which module to import and whether the program is passed as text or
    lines -- both of which ``RUNNERS`` already records for ``run``.  Every
    registered language goes through here, so the adapter set cannot drift
    from the runner set and a new language needs no code in this file.
    """
    module_path, split = RUNNERS[language]
    # Bound to another name first: a class body cannot read the enclosing
    # function's ``language`` while binding a class attribute of that name.
    display_name = language

    class _Derived(_DelegatingVM):
        #: The registry's display name for this adapter's language.
        #:
        #: ``_DelegatingVM`` never sees a name, and the debugger needs one
        #: to ask ``describe`` whether a read past the end of input is a
        #: value here -- the difference between a wrong answer and a raise.
        language = display_name

        def __init__(self, program: str, stdin: str = "") -> None:
            super().__init__(stdin)
            import importlib
            import inspect

            from esolangs.interpreters.randomness import Seeded

            module = importlib.import_module(f"esolangs.interpreters.{module_path}")
            code = program.splitlines() if split else program
            # ``_Machine`` is private to its module but is the state object
            # this whole file is built around.
            state = getattr(module, "_Machine")  # noqa: B009
            # A stepped VM has to be reproducible, so a seeded source is
            # passed wherever a random instruction accepts one (optional
            # like ``io``: the interpreter falls back to ``secrets``).  The
            # seed comes off the machine, because which draw to start from
            # is a fact about the language -- COD's junction example goes
            # East, LaserFuck's grids are written for a laser heading up.
            if "rng" in inspect.signature(state).parameters:
                seed = getattr(state, "reproducible_seed", 0)
                self._machine = state(code, self._io, rng=Seeded(seed))
            else:
                self._machine = state(code, self._io)

    _Derived.__name__ = _Derived.__qualname__ = f"_{language}VM"
    _Derived.__doc__ = f"Adapter for {language}; the interpreter describes its shape."
    return _Derived


# Language name -> VM adapter, read off ``RUNNERS`` rather than listed
# again, so an unregistered name is the only thing raising
# UnknownLanguageError.  Building an adapter imports nothing; the
# interpreter is imported inside its ``__init__``.  Typed as the factory it
# is used as rather than as the base class, which takes only the input.
_VM_ADAPTERS: dict[str, Callable[[str, str], _DelegatingVM]] = {
    name: _derived_adapter(name) for name in RUNNERS
}


@cache
def machine_traits(language: str) -> dict[str, bool]:
    """Return ``language``'s driving traits without running anything.

    The same traits a :class:`VM` exposes, read off the interpreter's state
    *class* rather than an instance, so :func:`esolangs.describe` can report
    them without a program -- which for seventeen languages would mean
    building the thing the caller is still deciding how to drive.
    """
    import importlib

    # No membership check beyond ``resolve``: it only returns registry
    # names, and the registry and ``RUNNERS`` hold the same 65.
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
    checks them, since stepping is the *other* way to execute a program: an
    unfilled template otherwise runs to a confident ``output:
    '0'``.  ``program`` may be a :class:`~pathlib.Path`, and the checked
    value is what reaches the interpreter -- checking a value and using it
    have to be the same expression or they drift, which is the argument for
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
        # malformed program with a plain ``ValueError``, which ``run``
        # re-raises as ``ProgramError``.
        raise ProgramError(str(exc)) from exc
