"""Streetcode steering, from junction choices to wall-following."""

from collections.abc import Callable
from typing import Literal, NamedTuple

from esolangs.languages.streetcode.interpreter.geometry import (
    _DELTA,
    _NO_LATCHES,
    _Car,
    _crossing_mouth,
    _Grid,
    _Heading,
    _junction_choices,
    _junction_kind,
    _lane_bounded,
    _lane_merge_target,
    _Latches,
    _left,
    _Merge,
    _open_toward,
    _opposite,
    _right,
    _road_mouth,
    _State,
    _turn_of,
)

# Intentional ``;`` stop, distinct from a probe's ``None``.  Construction
# rejects the latter, so a survivor is a validator bug rather than a halt.
_Halt = Literal["halt"]


class _Steer(NamedTuple):
    """What a steering phase decided: a heading, and the latches after it."""

    heading: _Heading
    latches: _Latches


# What one phase answers before ``_choose_heading`` sorts it out.  Not a
# ``_Steer | None`` because a declining phase may still have written a latch
# off (a merge abandoned mid-approach), and that write must survive.
_Phase = tuple["_Heading | None", _Latches]


def _heading_leaving_merge(grid: _Grid, car: _Car, latches: _Latches) -> _Phase:
    """Phase 2 of a merge: hold straight until the new wall picks up.

    Keep going while right and ahead are open; either closing ends the latch.
    """
    if latches.merging_heading is None:
        return None, latches
    heading = car.heading
    if latches.merging_heading == heading and (
        _open_toward(grid, car, _right(heading)) and _open_toward(grid, car, heading)
    ):
        return heading, latches
    return None, latches._replace(merging_heading=None)


def _heading_from_merge_target(
    grid: _Grid, car: _Car, latches: _Latches, arrival_cell: int
) -> _Phase:
    """Phase 1 of a merge: drive to the latched lane, then turn.

    ``None`` once the latch is spent or abandoned.
    """
    merge = latches.merge
    if merge is None:
        return None, latches
    new_heading = merge.new_heading
    heading = car.heading
    # A 'U' during the approach turns the car around, so the latch must not
    # wait forever for a cell it no longer visits -- that would disable
    # junction detection for the rest of the run.
    if heading != merge.latched_heading:
        return None, latches._replace(merge=None)
    if car.at != merge.target:
        # Still approaching the lane where the turn will be made.  Hold
        # the latched heading: the road being joined is open on that side
        # by definition, so an ordinary hug would turn early and never
        # reach the target.
        if _open_toward(grid, car, heading):
            return heading, latches
        return None, latches._replace(merge=None)

    latches = latches._replace(merge=None)
    # Re-read from ``arrival_cell`` (an ``I``/``=`` on the approach changes
    # the CPth cell; a turning square's own setup is not the decision).
    # Side mouths only: a ``^`` on a crossing's run out must not overturn it.
    if not merge.crossing:
        # Left-to-right as the driver sees it: a left turn before carrying
        # straight on, a right turn after.  Read off the latch rather than
        # recomputed from the headings, so the re-read cannot disagree with
        # the original choice about which road is "leftmost".
        choices = (
            [new_heading, merge.latched_heading]
            if merge.turn == "left"
            else [merge.latched_heading, new_heading]
        )
        new_heading = choices[0] if arrival_cell == 0 else choices[1]
    if new_heading == heading:
        return None, latches._replace(merging_heading=None)
    if _open_toward(grid, car, new_heading):
        return new_heading, latches._replace(merging_heading=new_heading)
    return None, latches


def _heading_from_junction(
    grid: _Grid, car: _Car, latches: _Latches, current_cell: int
) -> _Phase:
    """Apply the spec's ambiguous-turn rule at a detected intersection.

    ``None`` when no junction fires or the turn is deferred until level with
    the mouth.  ``current_cell`` is the CPth cell *after* this square's
    instruction, unlike phase 1's arrival read.
    """
    heading = car.heading
    order = [_left(heading), heading, _right(heading)]
    options = [h for h in order if _open_toward(grid, car, h)]
    if len(options) < 2 or not _junction_kind(grid, car):
        return None, latches

    roads = _junction_choices(grid, car)
    # A junction that fired always offers at least two roads.
    new_heading = roads[0] if current_cell == 0 else roads[1]
    turning = new_heading != heading
    # Every road passed ``_road_deep`` or ``_open_toward``; merging applies
    # only to turns onto a detected side road.
    if turning and _crossing_mouth(grid, car):
        # Emerging head-on from a branch onto the road it joins: cross to
        # the far lane before turning, since "drive on the right-hand
        # side" applies to the road being joined too.
        target = car.at
        d_row, d_col = _DELTA[heading]
        while grid.open_at(target[0] + d_row, target[1] + d_col):
            target = target[0] + d_row, target[1] + d_col
        # ``_crossing_mouth`` guarantees the cell ahead is open, so the
        # loop always advances at least one cell.
        return None, latches._replace(
            merge=_Merge(
                target_row=target[0],
                target_col=target[1],
                turn=_turn_of(heading, new_heading),
                latched_heading=heading,
                crossing=True,
            )
        )
    # Looked up once and handed to both helpers, rather than each
    # re-finding it and guarding against a miss the other ruled out.
    mouth = _road_mouth(grid, car, new_heading)
    if turning and mouth is not None and _lane_bounded(grid, car, new_heading, mouth):
        target = _lane_merge_target(car, new_heading, mouth)
        if target != car.at:
            return None, latches._replace(
                merge=_Merge(
                    target_row=target[0],
                    target_col=target[1],
                    turn=_turn_of(heading, new_heading),
                    latched_heading=heading,
                    crossing=False,
                )
            )
        return new_heading, latches

    if not turning:
        # Suppress the hug for exactly the mouth's width past a declined
        # side road (no further: the next corner must still happen).  Only
        # ever extended; one mouth is detected from several cells.
        declined = [h for h in roads if h != heading]
        mouth = _road_mouth(grid, car, declined[0])
        if mouth is not None and mouth.near <= 0:
            # Only when the gap opens immediately beside the car
            # (``near <= 0``), where the fallen-away wall would otherwise
            # steer it into the declined road.  A gap further ahead needs
            # no suppression: wall-following holds the car until it
            # arrives, by which point the junction is behind it.
            latches = latches._replace(skip_hug=max(latches.skip_hug, mouth.width))
    return new_heading, latches


def _heading_from_hug(grid: _Grid, car: _Car, latches: _Latches) -> _Phase:
    """Ordinary right-hand wall-following, the default movement rule."""
    heading = car.heading
    if latches.skip_hug > 0:
        # Drive past the declined branch rather than hugging the wall that
        # has fallen away.  A wall straight ahead still turns the car --
        # rounding a corner is not being pulled into the declined road --
        # but the countdown carries on so the rest of the mouth is skipped.
        latches = latches._replace(skip_hug=latches.skip_hug - 1)
        if _open_toward(grid, car, heading):
            return heading, latches
    for candidate in (_right(heading), heading, _left(heading), _opposite(heading)):
        if _open_toward(grid, car, candidate):
            return candidate, latches
    return None, latches


def _choose_heading(
    grid: _Grid, car: _Car, latches: _Latches, arrival_cell: int, current_cell: int
) -> _Steer | None:
    """Pick the car's next heading, and the latches it carries onward.

    Four phases, each a heading or ``None``: leaving a merge, approaching
    a latched target, deciding a junction, hugging the wall.  Latches are
    abandoned when the approach stops matching.  ``arrival_cell`` (the
    merge re-read) and ``current_cell`` (the junction rule) are the only
    tape reads movement makes, so the drive-state graph tries both bits.
    ``None`` overall means the car ran out of road.
    """
    phases: tuple[Callable[[_Latches], _Phase], ...] = (
        lambda ls: _heading_leaving_merge(grid, car, ls),
        lambda ls: _heading_from_merge_target(grid, car, ls, arrival_cell),
        lambda ls: _heading_from_junction(grid, car, ls, current_cell),
        lambda ls: _heading_from_hug(grid, car, ls),
    )
    for phase in phases:
        heading, latches = phase(latches)
        if heading is not None:
            return _Steer(heading, latches)
    return None


def _drive[StateT: _State](
    grid: _Grid, state: StateT, arrival_cell: int, current_cell: int
) -> "StateT | _Halt | None":
    """Return the state one step on from ``state``, or why there is none.

    The whole movement semantics; pure, so ``validation.drive_states``
    can enumerate it and :meth:`_Machine.step` replay it.  ``;`` is
    ``"halt"``; ``U`` reverses into the lane now on the right and clears
    every latch.  ``None`` is running out of road (a wedged street, which
    ``validation.validate_total`` rejects), deliberately not ``"halt"``.
    Value-dependent halts stay in :meth:`_Machine.step`.
    """
    car = state.car
    op = grid.op_at(car.row, car.col)
    if op == "HALT":
        return "halt"
    if op == "TURN":
        reversed_car = car.facing(_opposite(car.heading))
        lane = reversed_car.ahead(_right(reversed_car.heading))
        # A street with no opposite lane is the late-detected width
        # violation ``step`` raises ``HaltError`` for.
        if not grid.open_at(*lane):
            return None
        # A 'U' clears the latches, the same reset ``step`` applies.
        return type(state)(*lane, reversed_car.heading, _NO_LATCHES)

    steer = _choose_heading(grid, car, state.latches, arrival_cell, current_cell)
    if steer is None:
        return None
    return type(state)(*car.ahead(steer.heading), steer.heading, steer.latches)
