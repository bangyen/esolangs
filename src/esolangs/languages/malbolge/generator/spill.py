"""Place the packed decoder's spill markers by slicing the slot geometry."""

from __future__ import annotations

from collections import defaultdict
from typing import NamedTuple

from esolangs.languages.malbolge.interpreter import _XLAT2, _Machine, _op
from esolangs.runtime.io import ScriptedIO

from .isa import _ACTIVE, _WORDS, _char_for

_MARKERS = 57592
_BANK = 729
_SHADOW_WALK_OFFSETS = (160, 296, 314, 377, 404, 647, 648, 727)
_PLACES = (1, 9, 81)
_HOLES = (7, 8, 3)
_SCALES = (3, 1, 1)
_AXES = {24908: 0, 11786: 1, 31388: 2}
_DISPATCH = 5024
_BRANCH = 5046
_SHADOW_WORD = 29527

type _Slot = tuple[int, int]
type _Domains = dict[int, tuple[int, ...]]


class _Choice(NamedTuple):
    slot: _Slot
    glyph: int


type _Options = dict[int, dict[int, _Choice]]


class _State(NamedTuple):
    machine: _Machine
    returned: bool


def _stage(source: bytearray, row: int) -> _State:
    """Run the fixed prefix to the spill dispatch."""
    machine = _Machine(source.decode("ascii"), ScriptedIO(f"{row:017b}"))
    returned = False
    for _ in range(12000):
        _, pc, _, halted = machine.state
        if pc == _DISPATCH:
            return _State(machine, returned)
        if halted:
            break
        returned |= pc == 29525
        machine.step()
    raise AssertionError(f"spill dispatch missed on row {row}")


def _values(frame: _State, domains: _Domains, address: int) -> tuple[int, ...]:
    """Read all allowed operands, accounting for the prefix encryption."""
    actual = frame.machine.memory[address]
    if address not in domains:
        return (actual,)
    values = domains[address]
    if 29524 <= address <= 29527 and (address != 29524 or frame.returned):
        values = tuple(ord(_XLAT2[v - 33]) for v in values)
    return (*values, actual)


def _walk(frame: _State, domains: _Domains, markers: set[int], glyph: int) -> set[int]:
    """Propagate the glyph through the dispatch's jumps and walks."""
    memory = frame.machine.memory
    states = {glyph + 1}
    for pc in range(_DISPATCH + 1, _BRANCH):
        op = _op(memory[pc], pc)
        if op == "o":
            states = {(d + 1) % _WORDS for d in states}
            continue
        assert op == "j"
        if states & markers:
            return set()
        following = set()
        for d in states:
            for operand in _values(frame, domains, d):
                value = operand
                if _DISPATCH <= d < pc and 33 <= operand <= 126:
                    value = ord(_XLAT2[operand - 33])
                following.add((value + 1) % _WORDS)
        states = following
    return states


def _axis(
    frame: _State, domains: _Domains, markers: set[int], glyph: int
) -> int | None:
    """Read the axis only when all native paths join before the branch."""
    targets = _walk(frame, domains, markers, glyph)
    if len(targets) != 1:
        return None
    (target,) = targets
    if target in domains or target in markers:
        return None
    return _AXES.get(frame.machine.memory[target] + 1)


def _geometric(
    residues: set[int], banks: set[int], fixed: set[int], palette: dict[int, int]
) -> _Options:
    """Derive legal marker glyphs for the free slot in each direction."""
    choices: _Options = {}
    for residue in sorted(residues):
        options: dict[int, _Choice] = {}
        address = _MARKERS + residue
        for label in _ACTIVE:
            glyph = _char_for(label, address)
            if glyph not in palette:
                continue
            axis = palette[glyph]
            place = _PLACES[axis]
            digit = residue // place % 9
            word = residue + 1 + (_HOLES[axis] - digit) * place
            if any(bank + word in fixed for bank in banks):
                continue
            bit = (digit // _SCALES[axis] + 1) % 3
            choice = _Choice((word, bit), glyph)
            options[axis] = min(choice, options.get(axis, choice))
        choices[residue] = options
    return choices


def _restrict_navigation(options: _Options, banks: set[int]) -> None:
    """Use the middle ranks for the spill slots shared with navigation."""
    reserved = {29528, 41391}
    pins = {}
    # 29528 supplies the two selector slots. At 41391 only the middle
    # bit can vary independently when constructing the lookup.
    for word, bits in ((29528, (1, 2)), (41391, (1,))):
        for bit in bits:
            slot = (word % _BANK, bit)
            _, middle, _ = sorted(
                r
                for r, choices in options.items()
                if any(choice.slot == slot for choice in choices.values())
            )
            pins[middle] = slot
    for residue, choices in options.items():
        if residue in pins:
            options[residue] = {
                axis: choice
                for axis, choice in choices.items()
                if choice.slot == pins[residue]
            }
        else:
            options[residue] = {
                axis: choice
                for axis, choice in choices.items()
                if not any(bank + choice.slot[0] in reserved for bank in banks)
            }


def _orient(remaining: dict[int, set[_Slot]]) -> dict[int, _Slot]:
    """Assign forced edges, leaves and then the remaining cycles."""
    assigned: dict[int, _Slot] = {}
    while remaining:
        incident: defaultdict[_Slot, set[int]] = defaultdict(set)
        for residue, choices in remaining.items():
            assert choices
            for slot in choices:
                incident[slot].add(residue)
        forced = [
            (r, next(iter(edges))) for r, edges in remaining.items() if len(edges) == 1
        ]
        leaves = [
            (min(rows), slot) for slot, rows in incident.items() if len(rows) == 1
        ]
        if forced or leaves:
            residue, slot = min(forced or leaves)
        else:
            assert all(len(rows) == 2 for rows in incident.values())
            residue = min(remaining)
            slot = min(remaining[residue])
        del remaining[residue]
        assigned[residue] = slot
        for neighbor in incident[slot] - {residue}:
            remaining[neighbor].remove(slot)
    return assigned


def _slice(
    points: list[int],
    axis: int,
    phase: int,
    options: _Options,
    ranks: dict[int, tuple[int, ...]],
) -> dict[int, _Slot]:
    """Keep one Latin-ranked point per line, then orient the residual slices."""
    first, second = (i for i in range(3) if i != axis)
    lines: defaultdict[_Slot, list[int]] = defaultdict(list)
    for point in points:
        if axis in options[point]:
            lines[options[point][axis].slot].append(point)
    assigned = {}
    for slot, points_on_line in lines.items():
        coords = ranks[points_on_line[0]]
        target = (
            phase + (coords[first] if axis else -coords[first]) - coords[second]
        ) % 3
        point = min(points_on_line, key=lambda r: ((ranks[r][axis] - target) % 3, r))
        assigned[point] = slot
    for level in range(3):
        pending = {
            r: {choice.slot for side, choice in options[r].items() if side != axis}
            for r in points
            if r not in assigned and ranks[r][axis] == level
        }
        assigned.update(_orient(pending))
    return assigned


def _place(options: _Options, shadow: int) -> dict[int, _Slot]:
    """Split each slot-class box along its geometric main axis."""
    slot_classes: list[dict[int, tuple[int, int]]] = []
    for place, scale in zip(_PLACES, _SCALES, strict=True):
        counts: defaultdict[int, int] = defaultdict(int)
        indices = {}
        for digit in sorted({r // place % 9 for r in options}):
            slot = (digit // scale + 1) % 3
            indices[digit] = (slot, counts[slot])
            counts[slot] += 1
        slot_classes.append(indices)
    boxes: defaultdict[tuple[int, ...], list[int]] = defaultdict(list)
    ranks = {}
    for residue in options:
        coords = [
            index[residue // place % 9]
            for index, place in zip(slot_classes, _PLACES, strict=True)
        ]
        boxes[tuple(slot for slot, _ in coords)].append(residue)
        ranks[residue] = tuple(rank for _, rank in coords)
    assigned = {}
    for points in boxes.values():
        shape = tuple(1 + max(ranks[r][i] for r in points) for i in range(3))
        axis = int(shape == (2, 3, 3))
        if shadow in points:
            # Leave the shadow's forced edge for the residual orientation.
            (mandatory,) = options[shadow]
            axis = (mandatory + 1) % 3
        assigned.update(_slice(points, axis, int(shape == (2, 2, 3)), options, ranks))
    assert len(assigned) == len(set(assigned.values())) == len(options)
    return assigned


def _spill_locations(
    source: bytearray, readouts: tuple[int, ...], source_ops: dict[int, str]
) -> dict[int, _Slot]:
    """Derive marker glyphs and return their local spill word and bit."""
    residues = {word % _BANK for word in readouts}
    banks = {word - word % _BANK for word in readouts}
    assert len(readouts) == len(residues) * len(banks)
    markers = {_MARKERS + residue for residue in residues}
    primary = {word + 1 for word in readouts}
    # Reserve each column marker and its short-hub companion before
    # assigning spills. The used columns are known after allocation.
    fixed = (
        primary
        | markers
        # The two reversible payload walks read these lanes. Their NOPs
        # carry valid jump glyphs and must stay outside the spill domain.
        | {bank + offset for bank in banks for offset in _SHADOW_WALK_OFFSETS}
        | {51031 + 3 * i + offset for i in range(243) for offset in (0, 1)}
    )
    fixed.update(
        k for k, raw in enumerate(source) if k not in source_ops and _op(raw, k) != "o"
    )
    zero = _stage(source, 0)
    simple = {
        raw: axis
        for raw in range(33, 127)
        if (axis := _axis(zero, {}, markers, raw)) is not None
    }
    potential = _geometric(residues, banks, fixed, simple)
    occupied = primary | {
        bank + choice.slot[0]
        for choices in potential.values()
        for choice in choices.values()
        for bank in banks
    }
    domains = {
        k: tuple(_char_for(op, k) for op in source_ops.get(k, _ACTIVE))
        for k in occupied
        if len(source_ops.get(k, _ACTIVE)) > 1
    }
    # The two extreme prefixes expose the variable register aliases
    # before the spill dispatch; the native certificate checks all rows.
    palette = simple
    for frame in (zero, _stage(source, (1 << 17) - 1)):
        palette = {
            raw: axis
            for raw, axis in palette.items()
            if _axis(frame, domains, markers, raw) == axis
        }
    options = _geometric(residues, banks, fixed, palette)
    # Axis two changes the operands of the C6226 shadow jump and
    # admits D=45928 alongside the required D=128 for word 29527.
    shadow = (_SHADOW_WORD - 1) % _BANK
    options[shadow].pop(2)
    _restrict_navigation(options, banks)
    placements = _place(options, shadow)
    for residue, slot in placements.items():
        source[_MARKERS + residue] = min(
            choice.glyph for choice in options[residue].values() if choice.slot == slot
        )
    return placements
