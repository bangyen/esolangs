"""Integer codel grids, anchored at the image origin."""

from math import gcd

from esolangs._validate import check_scale
from esolangs.exceptions import ProgramError
from esolangs.raster import Pixel, Rows


def detect_scale(rows: Rows) -> int:
    """Return the largest uniform square grid; its intended meaning is ambiguous."""
    scale = gcd(len(rows), len(rows[0]))
    previous = rows[0]
    checked: dict[int, tuple[Pixel, ...]] = {}
    for y, row in enumerate(rows):
        if row != previous:
            scale = gcd(scale, y)
        previous = row
        if id(row) in checked:
            continue
        if len(checked) < 1024:
            checked[id(row)] = row
        for x in range(1, len(row)):
            if row[x] != row[x - 1]:
                scale = gcd(scale, x)
                if scale == 1:
                    return 1
    return scale


def normalize(rows: Rows, scale: int | None = None) -> Rows:
    """Validate and reduce uniform codel squares, detecting size when omitted."""
    factor = detect_scale(rows) if scale is None else check_scale(scale)
    if len(rows) % factor or len(rows[0]) % factor:
        raise ProgramError("image dimensions must be divisible by scale")
    if factor == 1:
        return rows
    result = []
    checked: dict[int, tuple[tuple[Pixel, ...], tuple[Pixel, ...]]] = {}
    for y in range(0, len(rows), factor):
        source = rows[y]
        if any(rows[yy] != source for yy in range(y + 1, y + factor)):
            raise ProgramError("scale requires uniform codel squares")
        cached = checked.get(id(source))
        if cached is None:
            row = []
            for x in range(0, len(source), factor):
                pixel = source[x]
                if source[x : x + factor] != (pixel,) * factor:
                    raise ProgramError("scale requires uniform codel squares")
                row.append(pixel)
            reduced = tuple(row)
            if len(checked) < 1024:
                checked[id(source)] = source, reduced
        else:
            reduced = cached[1]
        result.append(reduced)
    return tuple(result)
