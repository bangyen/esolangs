"""Immutable greyscale scanlines with an RGB view on demand."""

from collections.abc import Callable
from functools import cached_property
from operator import itemgetter

from esolangs.runtime._files import _STREAM_DEADLINE, _time_remaining

type GreyRows = tuple[bytes, ...]
type RGBRow = tuple[tuple[int, int, int], ...]


class GreyImage:
    def __init__(self, size: tuple[int, int], draw: Callable[[], GreyRows]) -> None:
        self.size = size
        self._draw = draw

    @cached_property
    def rows(self) -> GreyRows:
        """Draw once and check the layout against the actual scanlines."""
        deadline = _STREAM_DEADLINE.get()
        _time_remaining(deadline)
        rows = self._draw()
        width, height = self.size
        if len(rows) != height or any(len(row) != width for row in rows):
            raise ValueError("greyscale drawing differs from its planned dimensions")
        _time_remaining(deadline)
        return rows

    def __call__(self) -> tuple[RGBRow, ...]:
        palette = tuple((v, v, v) for v in range(256))
        patterns: dict[bytes, RGBRow] = {}
        result = []
        for row in self.rows:
            pixels = patterns.get(row)
            if pixels is None:
                pixels = tuple(map(palette.__getitem__, row))
                if len(patterns) < 1024:
                    patterns[row] = pixels
            result.append(pixels)
        return tuple(result)


def channels(row: RGBRow) -> tuple[bytes, bytes, bytes]:
    """The three immutable channel planes of an RGB scanline."""
    red, green, blue = (bytes(map(itemgetter(i), row)) for i in range(3))
    return red, green, blue


def pixel_hash(rows: tuple[RGBRow, ...] | GreyRows) -> int:
    """Hash the same channel bytes for either backing representation."""
    cached: dict[int, int] = {}
    hashes = []
    for row in rows:
        value = cached.get(id(row))
        if value is None:
            value = hash((row, row, row) if isinstance(row, bytes) else channels(row))
            cached[id(row)] = value
        hashes.append(value)
    return hash(tuple(hashes))
