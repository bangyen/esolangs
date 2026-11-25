"""Bound retained Piet layouts across generation requests."""

from collections import OrderedDict
from collections.abc import Callable
from sys import getsizeof
from threading import Lock

from esolangs.raster import Raster

type Builder = Callable[[str], Raster]
_PIXEL_BYTES = getsizeof((0, 0, 0)) + 3 * getsizeof(255)


class LayoutCache:
    """Share a weighted LRU across builders, including the table keys."""

    def __init__(self, limit: int) -> None:
        """Start empty with the given retained-byte estimate limit."""
        self._limit = limit
        self._entries: OrderedDict[tuple[Builder, str], tuple[Raster, int]] = (
            OrderedDict()
        )
        self._used = 0
        self._lock = Lock()

    def clear(self) -> None:
        """Drop layouts retained across calls."""
        with self._lock:
            self._entries.clear()
            self._used = 0

    def get_or_build(
        self, builder: Builder, table: str, build: Callable[[], Raster]
    ) -> Raster:
        """Cache by layout builder and table without retaining the request's plan."""
        key = builder, table
        with self._lock:
            cached = self._entries.get(key)
            if cached is not None:
                self._entries.move_to_end(key)
                return cached[0]
        image = build()
        # Charge shared rows and pixels independently, so reuse can
        # only make this estimate more conservative.
        weight = (
            256
            + getsizeof(table)
            + getsizeof(image)
            + getsizeof(image.rows)
            + sum(getsizeof(row) + len(row) * _PIXEL_BYTES for row in image.rows)
        )
        if weight > self._limit:
            return image
        with self._lock:
            cached = self._entries.get(key)
            if cached is not None:
                self._entries.move_to_end(key)
                return cached[0]
            while self._used + weight > self._limit:
                _, (_, evicted) = self._entries.popitem(last=False)
                self._used -= evicted
            self._entries[key] = image, weight
            self._used += weight
        return image
