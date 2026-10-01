"""Integer codel grids, anchored at the image origin."""

from math import gcd

from esolangs._validate import check_scale
from esolangs.exceptions import ProgramError
from esolangs.raster import Rows


def detect_scale(rows: Rows) -> int:
    """Return the largest uniform square grid; its intended meaning is ambiguous."""
    scale = gcd(len(rows), len(rows[0]))
    previous = rows[0]
    for y, row in enumerate(rows):
        if row != previous:
            scale = gcd(scale, y)
        previous = row
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
    for y in range(0, len(rows), factor):
        row = []
        for x in range(0, len(rows[0]), factor):
            pixel = rows[y][x]
            if any(
                rows[yy][xx] != pixel
                for yy in range(y, y + factor)
                for xx in range(x, x + factor)
            ):
                raise ProgramError("scale requires uniform codel squares")
            row.append(pixel)
        result.append(tuple(row))
    return tuple(result)
