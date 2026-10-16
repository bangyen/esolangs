"""The halt and cycle detectors :mod:`esolangs.vm` re-exports."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

from esolangs.runtime._validate import check_whole
from esolangs.runtime.source_hints import with_hint

if TYPE_CHECKING:
    from esolangs.vm import VM


@runtime_checkable
class _SteppableMachine(Protocol):
    """The bare step-and-ask-if-halted surface a bounded drive needs.

    No ``snapshot()``, so :class:`~esolangs.debugger.Debugger` qualifies.
    """

    def step(self) -> None:
        """Execute one command, advancing the machine."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""


@runtime_checkable
class _StepMachine(_SteppableMachine, Protocol):
    """The minimal step-capable surface the hang detector steps on.

    ``snapshot()`` must be the *complete* state, input cursor included, or a
    "repeat" is not a real cycle.
    """

    def snapshot(self) -> Hashable:
        """Return the complete internal state, hashable for cycle detection.

        Opaque; ``ip``, ``memory``, ``stack`` and ``output`` are the views.
        """


@runtime_checkable
class _BranchingStepMachine(Protocol):
    """A machine whose next random choice can be enumerated exactly.

    The state is an immutable value: exploring one outcome must not
    consume a draw, input or output belonging to a sibling.
    """

    def branching_snapshot(self) -> Hashable:
        """Return the initial complete state for a branching search."""

    def branching_halted(self, state: Hashable) -> bool:
        """Whether ``state`` has halted."""

    def branching_successors(
        self, state: Hashable, limit: int
    ) -> Sequence[Hashable] | None:
        """Return every next state, or ``None`` when it cannot be forked.

        ``limit`` bounds the outcomes one transition may materialize.
        """


def _unwrap(machine: object, protocol: type[Any], role: str, *, hint: str) -> object:
    """Return ``machine``, or the interpreter state a :class:`VM` wraps.

    The protocol is tried before the unwrap, so a raw machine is handed
    back as is.  ``role`` names what the argument failed to be.
    ``protocol`` is ``type[Any]`` with a ``cast`` at each caller: mypy
    refuses a protocol class where ``type[T]`` is expected.
    """
    if isinstance(machine, protocol):
        return machine
    inner = getattr(machine, "_machine", None)
    if isinstance(inner, protocol):
        return inner
    raise with_hint(
        TypeError(
            f"{getattr(machine, 'language', type(machine).__name__)} is not {role}: "
            "neither it nor any machine "
            "it wraps provides the required members"
        ),
        hint,
    )


def _checked_unwrap(
    machine: object, protocol: type[Any], role: str, hint: str, limit: int | None
) -> Any:
    """Check ``limit`` when given, then unwrap to the detector's protocol."""
    if limit is not None:
        check_whole(limit, "limit")
    return _unwrap(machine, protocol, role, hint=hint)


def _refuse_random(machine: object, proof: str) -> None:
    """Raise when ``machine`` draws: ``proof`` assumes the next lap repeats.

    Branching cannot stand in -- a growing state never repeats -- so a
    random machine is refused rather than handed over.
    """
    inner = getattr(machine, "vm", machine)
    inner = getattr(inner, "_machine", inner)
    if isinstance(inner, _BranchingStepMachine) and not getattr(inner, "halted", True):
        raise with_hint(
            TypeError(
                f"random machines: a {proof} proof assumes each lap repeats "
                "the last, and a draw can change the next one"
            ),
            "bound the run instead; run_until_halt_or_all_branches_cycle "
            "decides exact cycles over every draw",
        )


def run_until_halt_or_cycle(
    machine: _StepMachine | VM, limit: int | None = None
) -> bool:
    """Step ``machine`` until it halts or revisits an exact state.

    A random language's machine is decided by branching instead (``limit``
    then counts branching states, its default when ``None``): ``False`` when
    every draw cycles, ``True`` when the program never drew and halts, and
    :class:`TypeError` when this run's own draws decide it.  A repeated
    deterministic snapshot *proves* a hang.  ``True`` on a halt, ``False``
    once a cycle is proven; unbounded growth never repeats and is
    :func:`run_until_halt_or_growth`'s.  Brent's algorithm: O(1)
    snapshots, up to ~2x past the cycle's start, so rely on the verdict,
    not the machine's state at detection.

    ``limit`` bounds the steps as the sibling detectors do, raising
    :class:`TimeoutError` rather than answer.  ``None`` (default) is the
    unbounded search; bound it when the machine may *grow* instead, which
    never repeats a state and so would not return.
    """
    machine = cast(
        _StepMachine,
        _checked_unwrap(
            machine,
            _StepMachine,
            "steppable with a snapshot",
            "pass make_vm(...) or a machine with step, halted and snapshot",
            limit,
        ),
    )
    # A Debugger wraps a VM (``vm``); a VM wraps interpreter state (``_machine``).
    underlying = getattr(machine, "vm", machine)
    underlying = getattr(underlying, "_machine", underlying)
    # A seeded random program can repeat its visible state, then halt: the
    # next draw is not in the snapshot, so a repeat proves nothing.  Branching
    # keeps the verdicts that hold whatever this run draws.  It ignores the
    # machine's own draw source, so "some path halts" after a fork is not
    # this run's answer (a FirstDraw(0) coin loops where the other halts).
    if not machine.halted and isinstance(underlying, _BranchingStepMachine):
        halts, forked = _branch_search(underlying, 10_000 if limit is None else limit)
        if not halts or not forked:
            return halts
        raise with_hint(
            TypeError(
                "random machines: some draws halt this program, so whether "
                "this run halts depends on its own draws"
            ),
            "use run_until_halt_or_all_branches_cycle for the any-draw question",
        )
    tortoise = machine.snapshot()
    power = 1
    length = 0
    steps = 0
    while not machine.halted:
        if limit is not None and steps >= limit:
            raise with_hint(
                TimeoutError(
                    f"undecided after {limit} steps: "
                    "neither halted nor repeated a state"
                ),
                "increase limit; for growing states try a supported growth detector",
            )
        machine.step()
        steps += 1
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

    ``True`` when *some* sequence of draws halts, ``False`` only once the
    reachable graph is finite with no halted state.  ``limit`` bounds
    distinct states and outcomes per step; growth without repeating, or
    an unforkable transition (one reading interactive input), raises
    :class:`TimeoutError`.  Every state is kept, since branches merge.
    A language with no random instruction raises :class:`TypeError`.
    """
    machine = cast(
        _BranchingStepMachine,
        _checked_unwrap(
            machine,
            _BranchingStepMachine,
            "branch-enumerable",
            "use a machine with branching_snapshot, "
            "branching_halted and branching_successors",
            limit,
        ),
    )
    return _branch_search(machine, limit)[0]


def _branch_search(machine: _BranchingStepMachine, limit: int) -> tuple[bool, bool]:
    """Return whether some path halts, and whether any state forked."""
    pending = [machine.branching_snapshot()]
    seen: set[Hashable] = set()
    forked = False
    while pending:
        state = pending.pop()
        if state in seen:
            continue
        # `>=`: a negative limit never equals a count rising from zero, so
        # the cap switched itself off and the caller hung.
        if len(seen) >= limit:
            raise with_hint(
                TimeoutError(
                    f"undecided after {limit} branching states: the reachable "
                    "graph may be unbounded"
                ),
                (
                    "increase the branching state limit if feasible; the "
                    "result remains undecided"
                ),
            )
        seen.add(state)
        if machine.branching_halted(state):
            return True, forked
        successors = machine.branching_successors(state, limit - len(seen))
        if successors is None:
            raise with_hint(
                TimeoutError(
                    "undecided: a branching transition needs input that cannot "
                    "be safely forked"
                ),
                (
                    "use fixed input and a seeded single-path run; that "
                    "does not decide all random paths"
                ),
            )
        forked = forked or len(successors) > 1
        pending.extend(successors)
    return False, forked


@runtime_checkable
class _FramedMachine(_SteppableMachine, Protocol):
    """A :class:`_SteppableMachine` that also exposes its call stack.

    ``frames`` is outermost first; ``frame_entry_key`` is what a frame is
    about to run (function, bindings, input cursor).
    """

    @property
    def frames(self) -> Sequence[object]:
        """The live call stack, outermost frame first."""

    def frame_entry_key(self, frame: object) -> Hashable:
        """Return ``frame``'s entry state, hashable and comparable."""


def run_until_halt_or_ancestor(machine: _FramedMachine | VM, limit: int = 64) -> bool:
    """Step ``machine`` until it halts or a call provably replays an ancestor.

    Infinite recursion pushes a frame per step, so snapshots never repeat;
    each pushed frame is compared with those beneath it, and an equal
    ``frame_entry_key`` means it replays what the ancestor is still inside.
    ``True`` on a halt, ``False`` once such a frame lands.  The input
    position carries the soundness (a base case one read away would
    otherwise be called a hang).  Misses bindings that differ every lap
    (``f(x - 1)`` over unbounded ints); O(depth) per push.  ``limit`` bounds
    pushes examined -- a repeat shows within a few frames (three across the
    suite) -- and exhausting it raises :class:`TimeoutError`.  No call
    stack, or a random machine, raises :class:`TypeError`.
    """
    _refuse_random(machine, "replayed-ancestor")
    machine = cast(
        _FramedMachine,
        _checked_unwrap(
            machine,
            _FramedMachine,
            "framed",
            "use a machine with frames and frame_entry_key; "
            "otherwise try exact-state cycle detection",
            limit,
        ),
    )
    ancestors: list[tuple[int, Hashable]] = []
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
        # A frame at or above this depth belongs to a call that has since
        # returned, so drop it rather than compare against a dead ancestor.
        while ancestors and ancestors[-1][0] >= depth:
            ancestors.pop()
        key = machine.frame_entry_key(machine.frames[-1])
        if any(key == ancestor for _, ancestor in ancestors):
            return False
        ancestors.append((depth, key))
    raise with_hint(
        TimeoutError(
            f"undecided after {limit} pushed frames: neither halted nor repeated "
            "an ancestor's entry state"
        ),
        (
            "increase the pushed-frame limit; changing arguments "
            "may prevent an ancestor match"
        ),
    )


@runtime_checkable
class _TapeMachine(_SteppableMachine, Protocol):
    """A :class:`_SteppableMachine` on a rightward-growing tape of cells.

    The four members are what the growth certificate compares across two
    visits to one ``ip``, and together must be the complete state.
    ``tape`` must be the *committed* tape (brainfuck buffers a cell).
    ``ip`` is ``Hashable``: a 2D position includes its heading.
    Opting in claims the language reads and writes only the cell under
    the pointer, is translation-invariant for ``ptr >= 1``, and grows
    rightward by fresh zeros (leftward only from ``ptr == 0``, which the
    certificate's ``m >= 1`` excludes).  Absolute addresses, wrapping or
    fixed tapes, and leftward growth away from ``ptr == 0`` must not
    declare it.
    """

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


#: One visit's ``(pointer, tape, input cursor)`` in the growth proof.
_Snapshot = tuple[int, tuple[int, ...], int]


@dataclass
class _GrowthVisit:
    """Per-``ip`` state for the growth proof.

    Three certificates share one record: ``snapshot``/``lowest`` compare
    two consecutive visits, ``origin``/``origin_low`` the first visit to
    the current one, and the ``wave_*`` fields Brent's checkpoint for a
    phase that begins after a transient.  Each ``*_low`` is the smallest
    pointer seen over its certificate's interval; the proof is invalid
    if the period ever reached the left edge.
    """

    snapshot: _Snapshot
    lowest: int
    origin: _Snapshot
    origin_low: int
    wave_before: _Snapshot
    wave_low: int
    wave_power: int
    wave_length: int


def run_until_halt_or_growth(machine: _TapeMachine | VM, limit: int = 100_000) -> bool:
    """Step ``machine`` until it halts or provably grows without bound.

    ``+[>+]`` grows a cell a lap, so the snapshot is always new.  This
    compares two consecutive visits to one ``ip``; with ``d`` the pointer
    displacement and ``m`` the lowest cell reached between them, a hang
    is written when all of:

    - the input cursor did not move,
    - ``d > 0`` and the tape grew by exactly ``d`` fresh cells,
    - ``m >= 1``, so the period never touched the left edge,
    - ``tape2[i + d] == tape1[i]`` for every ``m <= i < len(tape1)``.

    Then the second visit is the first translated by ``d`` on the cells
    it can still reach, and by translation invariance the period replays
    forever.  ``m >= 1`` licenses the translation; ``i >= m`` rather than
    ``i >= 0`` is what proves ``+[>++]`` (cell 0 keeps a 1).  A Brent
    checkpoint per position finds a repeating phase of any length.
    ``d == 0`` (``+[<+]``) is :func:`run_until_halt_or_cycle`'s;
    ``>+[[<]>[>]+]`` is out of reach (visits share a frozen prefix, and a
    machine counting its walk into ``ip`` could halt on a count the pair
    never saw).  ``limit`` is in steps and raises :class:`TimeoutError`;
    no tape, or a random machine, raises :class:`TypeError`.
    """
    _refuse_random(machine, "tape-growth")
    machine = cast(
        _TapeMachine,
        _checked_unwrap(
            machine,
            _TapeMachine,
            "a tape machine",
            "use a compatible rightward-growing tape machine; "
            "otherwise try exact-state cycle detection",
            limit,
        ),
    )
    # One record per position holds all three certificates.  ``snapshot``
    # keeps the broad, one-period comparison; ``origin`` proves a steady
    # wave after its first full phase; the ``wave_*`` fields are Brent's
    # O(1)-per-position checkpoint for a phase that begins after a
    # transient.  Every minimum is updated on each step because the proof
    # is invalid if the period ever reached the left edge.
    visits: dict[Hashable, _GrowthVisit] = {}
    for _ in range(limit):
        if machine.halted:
            return True
        ip, ptr, tape = machine.ip, machine.ptr, machine.tape
        for seen in visits.values():
            seen.lowest = min(seen.lowest, ptr)
            seen.origin_low = min(seen.origin_low, ptr)
            seen.wave_low = min(seen.wave_low, ptr)
        cursor = machine.input_position()
        current: _Snapshot = (ptr, tape, cursor)
        visit = visits.get(ip)
        if visit is None:
            visits[ip] = _GrowthVisit(
                snapshot=current,
                lowest=ptr,
                origin=current,
                origin_low=ptr,
                wave_before=current,
                wave_low=ptr,
                wave_power=1,
                wave_length=0,
            )
        else:
            if _grows_forever(visit.snapshot, current, visit.lowest):
                return False
            if _grows_forever(visit.origin, current, visit.origin_low):
                return False
            # Unreached: by ablation each of the three arms proves every
            # growth program in the suite alone.  Kept -- the corpus is a
            # handful of programs, and an idle arm may decide a shape not
            # yet written.
            if _grows_forever(  # pragma: no cover - see above
                visit.wave_before, current, visit.wave_low
            ):
                return False
            visit.snapshot = current
            visit.lowest = ptr
            visit.wave_length += 1
            if visit.wave_length == visit.wave_power:
                visit.wave_before = current
                visit.wave_low = ptr
                visit.wave_power *= 2
                visit.wave_length = 0
        machine.step()
    if machine.halted:
        return True
    raise with_hint(
        TimeoutError(
            f"undecided after {limit} steps: neither halted nor grew by a "
            "provable translation"
        ),
        "increase limit; for repeated exact states try run_until_halt_or_cycle",
    )


def _grows_forever(
    before: _Snapshot,
    after: _Snapshot,
    lowest: int,
) -> bool:
    """Whether ``after`` is ``before`` translated right by the growth."""
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
class _AffineMachine(_SteppableMachine, Protocol):
    """A machine whose cells grow in *value* on a tape that does not grow.

    A loop may stay one to five cells wide while a cell climbs by a
    constant each lap, on unbounded Python ints.  ``values`` may grow
    (compared by subtraction); ``key`` is everything else (equality);
    ``clamp_slack`` is the one place a value changes behaviour.  Opting
    in claims control flow is independent of ``values`` (no branch),
    every operation is affine
    (``acc += tape[ptr]``, ``tape[ptr] + 1 - acc``, resets to 0), and
    every departure is a ``max(0, ...)`` reported by ``clamp_slack``
    *before* the clamping step.  The clamp claim is load-bearing: a slack
    shrinking a little each lap flips after a hundred laps.
    """

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


#: One visit's ``(step index, values, input cursor)`` in the affine proof.
_Visit = tuple[int, tuple[int, ...], int]


def run_until_halt_or_value_growth(
    machine: _AffineMachine | VM, limit: int = 20_000
) -> bool:
    """Step ``machine`` until it halts or provably grows in value forever.

    For fixed-width tapes whose *cells* grow.  With ``v1``, ``v2``, ``v3``
    the ``values`` at three consecutive visits to one ``key``, a hang is
    reported when all of:

    - the input cursor did not move,
    - ``key`` is equal at all three,
    - ``v2 - v1 == v3 - v2``, non-zero, no negative component,
    - the two laps agree at every clamp: same side, slack not drifting.

    Then the lap is an affine map ``v -> v + d`` and, control flow not
    reading values, repeats forever.  Seen *twice* because one observation
    is consistent with anything next.  ``limit`` is in steps; a step costs
    the whole tape, and 20_000 is the measured turn of that curve (~1.6s
    worst case, under a millisecond on the two programs this is for).
    Bounded values raise :class:`TypeError`: a climbing byte wraps.  So does a
    random machine.
    """
    _refuse_random(machine, "value-growth")
    machine = cast(
        _AffineMachine,
        _checked_unwrap(
            machine,
            _AffineMachine,
            "an affine machine",
            "use a machine with unbounded affine values; wrapping "
            "cells need exact-state cycle detection",
            limit,
        ),
    )
    # One slack per step in a single log, and per key the last three steps
    # that visited it, so a lap is a slice rather than a list of its own.
    # Collecting slacks per waiting key would append once for every key
    # still unrevisited -- quadratic on a program whose key never repeats,
    # such as ``>`` alone widening the tape every step.
    slacks: list[int | None] = []
    visits: dict[Hashable, list[_Visit]] = {}
    for index in range(limit):
        if machine.halted:
            return True
        slacks.append(machine.clamp_slack)
        key = machine.key
        seen = visits.setdefault(key, [])
        seen.append((index, machine.values, machine.input_position()))
        del seen[:-3]
        if len(seen) == 3 and _climbs_forever(seen, slacks):
            return False
        machine.step()
    if machine.halted:
        return True
    raise with_hint(
        TimeoutError(
            f"undecided after {limit} steps: neither halted nor climbed by a "
            "provable affine step"
        ),
        "increase limit; for repeated exact states try run_until_halt_or_cycle",
    )


def _climbs_forever(
    visits: list[_Visit],
    slacks: list[int | None],
) -> bool:
    """Whether three visits advance affinely with every clamp holding.

    The two laps are the stretches of ``slacks`` between the visits' steps.
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

    A clamp at the floor may only sink; one above it may only rise.
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


def run_until_halt(
    machine: _SteppableMachine | VM,
    limit: int | None = None,
    *,
    stop: Callable[[], bool] | None = None,
) -> bool:
    """Step ``machine`` until it halts, or the budget or ``stop`` ends it.

    Proves nothing: ``True`` halted, ``False`` still going.  ``limit`` in
    steps, ``None`` unbounded.  ``stop`` is checked *before* each step
    (what a breakpoint means).  The machine is left where it stopped.
    """
    if limit is not None:
        check_whole(limit, "limit")
    steps = 0
    while not machine.halted:
        if stop is not None and stop():
            return False
        if limit is not None and steps >= limit:
            return False
        machine.step()
        steps += 1
    return True
