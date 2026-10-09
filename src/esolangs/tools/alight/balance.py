"""Alight fold partitions and the native minimax record layouts."""

from functools import cache
from itertools import pairwise
from math import isqrt
from typing import NamedTuple

from esolangs.tools.alight import (
    _ALIGHT_EAST_TURN,
    _ALIGHT_OVERHEAD,
    _ALIGHT_WEST_TURN,
    _alight_chunk,
    _alight_flat_compact,
    _alight_folded,
    _alight_units,
    _dimensions,
    _half_before,
    _postfix_units,
)
from esolangs.tools.helpers import _validate_truth_table, input_weights

_Affine = tuple[int, int]
_EAST = len(_ALIGHT_EAST_TURN)
_WEST = len(_ALIGHT_WEST_TURN)
#: ``_Plan.kind``, also a score tiebreak, so the order is load-bearing.
_COLUMN, _ROW, _FOLD = 0, 1, 2


class _Plan(NamedTuple):
    kind: int
    columns: int
    chunk: int
    width: int
    height: int
    length: int

    def score(self) -> tuple[int, int, int, int, int]:
        return (
            max(self.width, self.height),
            self.width * self.height,
            self.length,
            self.kind,
            self.columns,
        )

    def ready(self) -> int:
        return max(self.width, self.columns)


def _fold_shape(
    pieces: list[_Affine], span: _Affine, value: int, stop: int
) -> tuple[int, int, int, int]:
    """Return width, height, length and the next greedy row-fit transition."""
    at = 0
    rows = 0
    used = (0, 0)
    while at < len(pieces):
        reserve = _EAST if rows == 0 else (_WEST + 1 if rows % 2 else _EAST + 1)
        used = (0, 0)
        while at < len(pieces):
            piece = pieces[at]
            total = (used[0] + piece[0], used[1] + piece[1])
            if used != (0, 0):
                rate = total[0] - span[0]
                offset = total[1] - span[1] + reserve
                failed = rate * value + offset > 0
                if rate < 0 and failed:
                    stop = min(stop, (offset - rate - 1) // -rate)
                elif rate > 0 and not failed:
                    stop = min(stop, -offset // rate + 1)
                if failed:
                    break
            used = total
            at += 1
        rows += 1
    columns = span[0] * value + span[1]
    last = used[0] * value + used[1]
    east, west = rows // 2, (rows - 1) // 2
    height = _EAST * east + _WEST * west + 1
    if rows == 1:
        return last, 1, last, stop
    final = columns if rows % 2 == 0 else last + 1
    east_ink = _EAST - 1 - _ALIGHT_EAST_TURN[:-1].count(" ")
    west_ink = _WEST - 1 - _ALIGHT_WEST_TURN[:-1].count(" ")
    length = (
        (rows - 1 + east_ink * east) * columns + west_ink * west + final + height - 1
    )
    return columns, height, length, stop


@cache
def _plans(n: int, kept: tuple[bool, ...] | None = None) -> tuple[_Plan, ...]:
    """Return native-dominating fold endpoints; geometry ignores literal bits.

    ``kept`` marks the essential reads; the rest are bare ``inp`` and the
    table has ``2**sum(kept)`` rows.
    """
    essential = list(kept or (True,) * n)
    size = 1 << sum(essential)
    flat = size + len(_alight_flat_compact("", n, essential))
    base = [len(";".join(unit)) + 1 for unit in _alight_units("", n, 0, essential)]
    prefix, tail = base[:-3], base[-2:]
    plans = [
        _Plan(_COLUMN, 0, 0, 1, flat, 2 * flat - 1),
        _Plan(_ROW, 0, 0, flat, 1, flat),
    ]
    index = len(_half_before(size))
    overhead = _ALIGHT_OVERHEAD + 2 * index
    shift = overhead + _EAST
    whole = 1 if _alight_chunk(size, 1) == size else shift + size + base[-3] - overhead
    whole_pieces = [(0, length) for length in [*prefix, size + base[-3], *tail]]
    lower = max(whole, max(length for _, length in whole_pieces) + _EAST + 1)
    upper = max(lower, flat)
    while lower <= upper:
        width, height, length, stop = _fold_shape(
            whole_pieces, (1, 0), lower, upper + 1
        )
        columns = (
            whole
            if lower == max(length for _, length in whole_pieces) + _EAST + 1
            else lower
        )
        plans.append(_Plan(_FOLD, columns, size, width, height, length))
        lower = stop
    cutoff = size + base[-3] - overhead
    if cutoff > 1:
        maximum = cutoff - 1
        quotients = {size}
        for divisor in range(1, isqrt(size - 1) + 1):
            quotients.update((divisor + 1, (size - 1) // divisor + 1))
        powers = []
        power = 10
        while power < size:
            powers.append(power + 1)
            power *= 10
        for count in quotients:
            low = (size + count - 1) // count
            high = min(maximum, (size - 1) // (count - 1))
            if low > high:
                continue
            events = {low, high + 1}
            for number in range(1, count):
                events.update(
                    point
                    for power in powers
                    if low < (point := (power + number - 1) // number) <= high
                )
            for lower, upper in pairwise(sorted(events)):
                first = (1, 30 + len(_half_before(lower)))
                pieces = [(0, length) for length in prefix] + [first]
                for number in range(1, count):
                    digits = len(_half_before(number * lower))
                    pieces.append(
                        (1 - count, size + 27 + 2 * digits)
                        if number == count - 1
                        else (1, 27 + 2 * digits)
                    )
                pieces.extend((0, length) for length in tail)
                while lower < upper:
                    width, height, length, stop = _fold_shape(
                        pieces, (1, shift), lower, upper
                    )
                    columns = 1 if lower == 1 else lower + shift
                    plans.append(_Plan(_FOLD, columns, lower, width, height, length))
                    lower = stop
    return tuple(plans)


def _emit(table: str, n: int, plan: _Plan, essential: list[bool] | None = None) -> str:
    flat = _alight_flat_compact(table, n, essential)
    if plan.kind == _COLUMN:
        program = "\n".join(flat)
    elif plan.kind == _ROW:
        program = flat
    else:
        program = _alight_folded(
            _alight_units(table, n, plan.chunk, essential), plan.columns
        )
    if (*_dimensions(program), len(program)) != (plan.width, plan.height, plan.length):
        raise AssertionError("Alight fold model disagrees with the rendered program")
    return program


def select_alight(table: str, n: int, width: int) -> str:
    """Return the original minimax winner among the permitted fit regimes."""
    plan = min((plan for plan in _plans(n) if plan.ready() <= width), key=_Plan.score)
    return _emit(table, n, plan)


def _balance_postfix(
    table: str, n: int, default: str, essential: list[bool] | None = None
) -> str:
    """Balance whole and square-root chunks at greedy fold transitions."""
    width, height = _dimensions(default)
    best = (abs(width - height), len(default), width)
    selected: tuple[list[list[str]], int, tuple[int, int, int]] | None = None
    size = len(table)
    for chunk in {size, isqrt(size - 1) + 1}:
        units = _postfix_units(table, n, chunk, essential)
        pieces = [(0, len(";".join(unit)) + 1) for unit in units]
        lower = max(length for _, length in pieces) + _EAST + 1
        upper = sum(length for _, length in pieces)
        while lower <= upper:
            _, height, _, stop = _fold_shape(pieces, (1, 0), lower, upper + 1)
            # Height is constant until the next row-fit transition; its nearest
            # permitted width minimizes imbalance without a width sweep.
            columns = min(max(height, lower), stop - 1)
            width, height, length, _ = _fold_shape(pieces, (1, 0), columns, stop)
            score = (abs(width - height), length, width)
            if score < best:
                best = score
                selected = units, columns, (width, height, length)
            lower = stop
    if selected is None:
        return default
    units, columns, shape = selected
    program = _alight_folded(units, columns)
    if (*_dimensions(program), len(program)) != shape:
        raise AssertionError("Alight postfix fold model disagrees with rendering")
    return program


def balance_alight(
    table: str, default: str, *, expression_syntax: str = "infix"
) -> str:
    """Balance the layouts that can win the native minimax width selector."""
    n = _validate_truth_table(table)
    weights, projected = input_weights(table, n)
    # An ignored input is read and dropped; a constant keeps every input.
    essential = [bool(weight) for weight in weights]
    if not any(essential) or all(essential):
        essential = [True] * n
        projected = table
    if expression_syntax == "postfix":
        return _balance_postfix(projected, n, default, essential)
    table = projected
    plans = _plans(n, tuple(essential))
    records = [next(plan for plan in plans if plan.kind == _ROW)]
    best: _Plan | None = None
    for plan in sorted(plans, key=lambda plan: (plan.ready(), plan.score())):
        if best is None or plan.score() < best.score():
            best = plan
            records.append(plan)
    selected = min(
        records,
        key=lambda plan: (abs(plan.width - plan.height), plan.length, plan.width),
    )
    return _emit(table, n, selected, essential)
