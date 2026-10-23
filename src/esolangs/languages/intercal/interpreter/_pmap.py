"""A persistent mapping: a write copies one bucket, not the whole store."""

from __future__ import annotations

from collections.abc import Hashable, Iterator, Mapping
from itertools import chain
from typing import Any


class _PMap[K: Hashable, V](Mapping[K, V]):
    """An immutable mapping whose writes share every untouched bucket.

    A write copies the bucket tuple and one bucket.  The bucket count is a
    power of two kept near the square root of the size (it doubles when the
    size passes twice its square), so a write copies about ``2 * sqrt(N)``
    slots where ``{**old, key: value}`` copies N: a program holding every
    name up to ``.65535`` writes in near-constant time per statement, and a
    three-name one copies a three-slot dict as before.
    """

    __slots__ = ("_buckets", "_size")

    def __init__(self, items: Mapping[K, V] | None = None) -> None:
        self._buckets: tuple[dict[K, V], ...] = ({},)
        self._size = 0
        if items:
            self._rebuild(dict(items))

    def _rebuild(self, items: dict[K, V]) -> None:
        """Hash ``items`` into the fewest buckets that keep size <= 2 * count^2."""
        count = 1
        while len(items) > 2 * count * count:
            count *= 2
        buckets: list[dict[K, V]] = [{} for _ in range(count)]
        for key, value in items.items():
            buckets[hash(key) & (count - 1)][key] = value
        self._buckets = tuple(buckets)
        self._size = len(items)

    def update(self, changes: Mapping[K, V]) -> _PMap[K, V]:
        """Return this mapping with ``changes`` applied; ``self`` is unchanged."""
        buckets = list(self._buckets)
        mask = len(buckets) - 1
        touched: set[int] = set()
        size = self._size
        for key, value in changes.items():
            at = hash(key) & mask
            if at not in touched:
                touched.add(at)
                buckets[at] = dict(buckets[at])
            size += key not in buckets[at]
            buckets[at][key] = value
        fresh = object.__new__(type(self))
        fresh._buckets = tuple(buckets)  # noqa: SLF001
        fresh._size = size  # noqa: SLF001
        if size > 2 * len(buckets) ** 2:
            fresh._rebuild(dict(fresh.items()))  # noqa: SLF001
        return fresh

    def set(self, key: K, value: V) -> _PMap[K, V]:
        """Return this mapping with ``key`` bound to ``value``."""
        buckets = self._buckets
        at = hash(key) & (len(buckets) - 1)
        bucket = buckets[at]
        fresh = object.__new__(type(self))
        fresh._buckets = (  # noqa: SLF001
            *buckets[:at],
            {**bucket, key: value},
            *buckets[at + 1 :],
        )
        fresh._size = self._size + (key not in bucket)  # noqa: SLF001
        if fresh._size > 2 * len(buckets) ** 2:  # noqa: SLF001
            fresh._rebuild(dict(fresh.items()))  # noqa: SLF001
        return fresh

    def __getitem__(self, key: K) -> V:
        buckets = self._buckets
        return buckets[hash(key) & (len(buckets) - 1)][key]

    def get(self, key: K, default: Any = None) -> Any:
        buckets = self._buckets
        return buckets[hash(key) & (len(buckets) - 1)].get(key, default)

    def __contains__(self, key: object) -> bool:
        buckets = self._buckets
        return key in buckets[hash(key) & (len(buckets) - 1)]

    def __iter__(self) -> Iterator[K]:
        return chain.from_iterable(self._buckets)

    def __len__(self) -> int:
        return self._size
