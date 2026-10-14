"""Greedy lane coloring across white bridges, without merged command blocks."""

from math import isqrt
from typing import NamedTuple

from esolangs.generation.raster_lookup import (
    _INITIAL,
    _POINTER,
    _POP,
    Pixel,
    _next_colour,
    _Operation,
    _push,
)
from esolangs.raster import Raster
from esolangs.runtime.codels import BLACK, WHITE

_DUPLICATE = (4, 0)
_MIN_PACKED_COLUMNS = 22
_MIN_SHARED_COLUMNS = 18


class _Lane(NamedTuple):
    first: int
    last: int
    x: int
    direction: int


def _lanes(
    operations: list[_Operation],
    columns: int,
    *,
    duplicate: bool = False,
    short: bool = False,
) -> tuple[int, list[_Lane]]:
    lanes = []
    at, x, direction, widest = 0, 2, 1, 1
    while at < len(operations):
        first, used = at, 0
        room = columns - x - 4 if direction == 1 else x - (7 if duplicate else 9)
        while at < len(operations):
            charge = 3 if at == len(operations) - 2 else operations[at].size
            if used + charge > room:
                break
            used += operations[at].size
            at += 1
        if at == first:
            raise AssertionError("Raster packed lane has no room for a bounded block")
        lanes.append(_Lane(first, at, x, direction))
        end = x + direction * used
        edge = end + 3 if direction == 1 and at < len(operations) else x
        widest = max(widest, edge, end)
        # Leave one white codel on right bends; left bends need a second
        # codel for the landing block's bottom tip when a spacer is required.
        x = (end + 1 if direction == 1 else end - 2) if short else end - direction
        direction = -direction
    return widest + 1, lanes


def _put(
    cells: dict[tuple[int, int], tuple[Pixel, int]],
    placed: dict[tuple[int, int], tuple[Pixel, int]],
    owner: int,
    x: int,
    y: int,
    colour: Pixel,
) -> None:
    if (x, y) in cells or (x, y) in placed:
        raise AssertionError("Raster packed lanes overlap")
    cells[x, y] = colour, owner


def _layout(  # noqa: C901
    operations: list[_Operation],
    columns: int,
    *,
    duplicate: bool = False,
    short: bool = False,
) -> Raster:
    width, lanes = _lanes(operations, columns, duplicate=duplicate, short=short)
    placed: dict[tuple[int, int], tuple[Pixel, int]] = dict.fromkeys(
        ((0, 0), (0, 1), (1, 1)), (_INITIAL, 0)
    )
    identity, old_y, corner = 0, 1, 0
    previous: _Lane | None = None
    end_colour = _next_colour(_INITIAL, _POP)
    for number, lane in enumerate(lanes):
        if previous is None:
            gap = 0
        elif number == len(lanes) - 1:
            gap = 3  # Isolate the vertical halt from the preceding lane.
        else:
            even = all(
                operation.change[0] % 2 == 0
                for operation in operations[previous.first : lane.last]
            )
            gap = 1 if duplicate or even else 2
        y = old_y + gap
        while True:
            for phase in range((18 if duplicate else 9) if previous is not None else 1):
                cells: dict[tuple[int, int], tuple[Pixel, int]] = {}
                owner = identity

                if previous is not None:
                    owner += 1
                    landing = corner
                    for yy in range(old_y + 1, y + 1):
                        _put(cells, placed, owner, landing, yy, end_colour)
                    if y > old_y + 1 and previous.direction == -1:
                        landing += 1
                        _put(cells, placed, owner, landing, y, end_colour)
                    for xx in range(
                        landing - previous.direction, lane.x, -previous.direction
                    ):
                        _put(cells, placed, owner, xx, y, WHITE)
                    # White executes no transition. Try opposite hue parity
                    # first, then the remaining colors for mixed lanes. Reject
                    # every block merge, including turns (seed 20261011, n8/14).
                    hue = (1 if phase < 9 else 0) + 2 * ((phase % 9) // 3)
                    colour = _next_colour(end_colour, (hue, phase % 3))
                else:
                    colour = end_colour
                x = lane.x

                def block(
                    operation: _Operation,
                    row_y: int = y,
                    direction: int = lane.direction,
                    blocks: dict[tuple[int, int], tuple[Pixel, int]] = cells,
                ) -> None:
                    nonlocal x, colour, owner
                    owner += 1
                    for _ in range(operation.size):
                        _put(blocks, placed, owner, x, row_y, colour)
                        x += direction
                    colour = _next_colour(colour, operation.change)

                for operation in operations[lane.first : lane.last]:
                    block(operation)
                if number == len(lanes) - 1:
                    owner += 1
                    for offset in (-1, 0, 1):
                        _put(cells, placed, owner, x, y + offset, colour)
                else:
                    value = 1 if lane.direction == 1 else 3
                    for operation in (
                        _push(value),
                        _Operation(_DUPLICATE) if duplicate else _push(value),
                        _Operation(_POINTER),
                        _Operation(_POINTER),
                    ):
                        block(operation)
                collision = False
                for (xx, yy), (pixel, block_id) in cells.items():
                    if pixel == WHITE:
                        continue
                    for point in (
                        (xx - 1, yy),
                        (xx + 1, yy),
                        (xx, yy - 1),
                        (xx, yy + 1),
                    ):
                        neighbor = cells.get(point, placed.get(point))
                        if (
                            neighbor is not None
                            and neighbor[0] == pixel
                            and neighbor[1] != block_id
                        ):
                            collision = True
                if not collision:
                    break
            if not collision:
                break
            y += 1
            if y - old_y > 4:
                raise AssertionError("Raster packed lane cannot isolate its blocks")
        placed.update(cells)
        identity, previous, old_y = owner, lane, y
        end_colour, corner = colour, x - lane.direction
    height = max(y for _, y in placed) + 1
    return Raster(
        tuple(
            tuple(placed.get((x, y), (BLACK, 0))[0] for x in range(width))
            for y in range(height)
        )
    )


def _shape_score(width: int, height: int) -> tuple[int, int, int]:
    """Rank a layout: squarest first, then smallest area, then narrowest."""
    return abs(width - height), width * height, width


def _raster_score(image: Raster) -> tuple[int, int, int]:
    return _shape_score(len(image.rows[0]), len(image.rows))


def pack(operations: list[_Operation], default: Raster) -> Raster:
    """Reduce padding with fixed lane widths and area and black ceilings."""
    root = isqrt(sum(operation.size for operation in operations))

    def layouts(minimum: int, **options: bool) -> list[Raster]:
        return [
            _layout(operations, max(minimum, root + offset), **options)
            for offset in (5, 9, 13)
        ]

    candidate = min(layouts(_MIN_PACKED_COLUMNS), key=_raster_score)

    def area(image: Raster) -> int:
        return len(image.rows) * len(image.rows[0])

    def black(image: Raster) -> int:
        return sum(pixel == BLACK for row in image.rows for pixel in row)

    # Seed 20261011, 200 tables/arity: n=8 area 279358 -> 214739 (-23.13%);
    # black 165729 -> 64988 (-60.79%), white 0 -> 21852. n=3: 56465 -> 55270.
    if area(candidate) < area(default) and black(candidate) <= black(default):
        default = candidate
    # Shared operands and mixed-lane coloring, same 200-table corpus: n=8
    # area 214739 -> 181350 (-15.55%); black 64988 -> 36033 (-44.55%);
    # white 21852 -> 19936. Exhaustive n=3 area 55270 -> 50130.
    duplicated = min(layouts(_MIN_SHARED_COLUMNS, duplicate=True), key=_raster_score)
    if area(duplicated) < area(default) and black(duplicated) <= black(default):
        default = duplicated
    # Short bridges, same corpus: n=8 area 181350 -> 161247 (-11.09%);
    # black 36033 -> 34748, white 19936 -> 6362. n=3 area 50130 -> 40868.
    eligible = [
        image
        for image in layouts(_MIN_SHARED_COLUMNS, duplicate=True, short=True)
        if area(image) <= area(default) and black(image) <= black(default)
    ]
    return min(
        [default, *eligible],
        key=lambda image: (
            area(image),
            black(image),
            abs(len(image.rows) - len(image.rows[0])),
        ),
    )
