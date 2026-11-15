"""Lossless run-length encoding for raster worker requests."""

from collections import OrderedDict
from collections.abc import Callable, Iterator
from itertools import chain, groupby, repeat
from threading import Lock

from esolangs.raster import Pixel, Raster, Rows
from esolangs.runtime._files import StreamReadTimeoutError

type _PixelRuns = tuple[tuple[int, Pixel], ...]
type _RasterRuns = tuple[tuple[int, _PixelRuns], ...]

_BLOCK = 8192
_CACHED_RASTERS = 4
_cache: OrderedDict[int, tuple[Raster, _RasterRuns]] = OrderedDict()
_cache_lock = Lock()


def _pixel_groups(row: tuple[Pixel, ...]) -> Iterator[tuple[int, Pixel]]:
    for pixel, group in groupby(row):
        yield len(list(group)), pixel


def _pixel_runs(row: tuple[Pixel, ...], checkpoint: Callable[[], None]) -> _PixelRuns:
    if len(row) <= _BLOCK:
        return tuple(_pixel_groups(row))
    runs: list[tuple[int, Pixel]] = []
    for start in range(0, len(row), _BLOCK):
        checkpoint()
        groups = _pixel_groups(row[start : start + _BLOCK])
        count, pixel = next(groups)
        if runs and runs[-1][1] == pixel:
            runs[-1] = runs[-1][0] + count, pixel
        else:
            runs.append((count, pixel))
        runs.extend(groups)
    return tuple(runs)


def _same_row(
    left: tuple[Pixel, ...], right: tuple[Pixel, ...], checkpoint: Callable[[], None]
) -> bool:
    if left is right:
        return True
    if len(left) <= _BLOCK:
        return left == right
    for start in range(0, len(left), _BLOCK):
        checkpoint()
        if left[start : start + _BLOCK] != right[start : start + _BLOCK]:
            return False
    return True


def _raster_runs(
    rows: Rows, checkpoint: Callable[[], None] | None = None
) -> _RasterRuns:
    """Coalesce consecutive equal rows and pixels in the exact wire order."""
    if checkpoint is None:
        return tuple(
            (len(list(repeated_rows)), tuple(_pixel_groups(row)))
            for row, repeated_rows in groupby(rows)
        )
    groups: list[tuple[int, _PixelRuns]] = []
    previous = rows[0]
    count = 0
    for index, row in enumerate(rows):
        if index % _BLOCK == 0:
            checkpoint()
        if _same_row(previous, row, checkpoint):
            count += 1
        else:
            checkpoint()
            groups.append((count, _pixel_runs(previous, checkpoint)))
            previous, count = row, 1
    checkpoint()
    groups.append((count, _pixel_runs(previous, checkpoint)))
    return tuple(groups)


def _raster_transport(
    image: Raster, stopped: Callable[[], bool] | None = None
) -> _RasterRuns:
    """Reuse an artifact's complete encoding without hashing all its pixels."""
    identity = id(image)
    with _cache_lock:
        if identity in _cache:
            _cache.move_to_end(identity)
            return _cache[identity][1]

    def checkpoint() -> None:
        if stopped is not None and stopped():
            raise StreamReadTimeoutError("raster exceeded the acquisition deadline")

    checkpoint()
    runs = _raster_runs(image.rows, checkpoint if stopped is not None else None)
    checkpoint()
    with _cache_lock:
        # Keep the image alive with its encoding to prevent identity reuse.
        cached = _cache.setdefault(identity, (image, runs))
        _cache.move_to_end(identity)
        if len(_cache) > _CACHED_RASTERS:
            _cache.popitem(last=False)
    return cached[1]


def _raster_rows(runs: _RasterRuns) -> Rows:
    """Decode pixel-exact rows, sharing immutable repeats."""
    return tuple(
        chain.from_iterable(
            repeat(
                tuple(
                    chain.from_iterable(
                        repeat((pixel[0], pixel[1], pixel[2]), count)
                        for count, pixel in row
                    )
                ),
                count,
            )
            for count, row in runs
        )
    )
