"""Prove unbounded tape translation or affine value growth."""

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from esolangs.runtime._drive import _checked_halted
from esolangs.runtime._proof_runtime import _step_proof_receiver
from esolangs.runtime._vm_protocol import _SteppableMachine
from esolangs.runtime.source_hints import with_hint


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


def _drive_tape_growth(
    state: _TapeMachine,
    runner: _SteppableMachine,
    limit: int,
    check_receiver: Callable[[], None] | None,
) -> bool:
    """Step until halt or a proved rightward translation."""
    # One record per position holds all three certificates.  ``snapshot``
    # keeps the broad, one-period comparison; ``origin`` proves a steady
    # wave after its first full phase; the ``wave_*`` fields are Brent's
    # O(1)-per-position checkpoint for a phase that begins after a
    # transient.  Every minimum is updated on each step because the proof
    # is invalid if the period ever reached the left edge.
    visits: dict[Hashable, _GrowthVisit] = {}
    for completed in range(limit + 1 if limit else 0):
        if _checked_halted(runner.halted):
            if check_receiver is not None:
                check_receiver()
            return True
        ip, ptr, tape = state.ip, state.ptr, state.tape
        for seen in visits.values():
            seen.lowest = min(seen.lowest, ptr)
            seen.origin_low = min(seen.origin_low, ptr)
            seen.wave_low = min(seen.wave_low, ptr)
        cursor = state.input_position()
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
            # Each certificate alone proves the current corpus. The wave
            # comparison still handles a phase beginning after a transient.
            if (
                _grows_forever(visit.snapshot, current, visit.lowest)
                or _grows_forever(visit.origin, current, visit.origin_low)
                or _grows_forever(  # pragma: no cover
                    visit.wave_before, current, visit.wave_low
                )
            ):
                if check_receiver is not None:
                    check_receiver()
                return False
            visit.snapshot = current
            visit.lowest = ptr
            visit.wave_length += 1
            if visit.wave_length == visit.wave_power:
                visit.wave_before = current
                visit.wave_low = ptr
                visit.wave_power *= 2
                visit.wave_length = 0
        if completed == limit:
            break
        if check_receiver is None:
            runner.step()
        else:
            _step_proof_receiver(runner, check_receiver, completed)
    if _checked_halted(runner.halted):
        if check_receiver is not None:
            check_receiver()
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


def _drive_value_growth(
    state: _AffineMachine,
    runner: _SteppableMachine,
    limit: int,
    check_receiver: Callable[[], None] | None,
) -> bool:
    """Step until halt or a proved affine climb."""
    # One slack per step in a single log, and per key the last three steps
    # that visited it, so a lap is a slice rather than a list of its own.
    # Collecting slacks per waiting key would append once for every key
    # still unrevisited -- quadratic on a program whose key never repeats,
    # such as ``>`` alone widening the tape every step.
    slacks: list[int | None] = []
    visits: dict[Hashable, list[_Visit]] = {}
    for index in range(limit + 1 if limit else 0):
        if _checked_halted(runner.halted):
            if check_receiver is not None:
                check_receiver()
            return True
        slacks.append(state.clamp_slack)
        key = state.key
        seen = visits.setdefault(key, [])
        seen.append((index, state.values, state.input_position()))
        del seen[:-3]
        if len(seen) == 3 and _climbs_forever(seen, slacks):
            if check_receiver is not None:
                check_receiver()
            return False
        if index == limit:
            break
        if check_receiver is None:
            runner.step()
        else:
            _step_proof_receiver(runner, check_receiver, index)
    if _checked_halted(runner.halted):
        if check_receiver is not None:
            check_receiver()
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
