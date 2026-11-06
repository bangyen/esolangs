"""Explicit wire projections for owned immutable snapshot values."""

from collections.abc import Callable, Hashable
from dataclasses import dataclass


@dataclass(frozen=True)
class SnapshotCodec[T]:
    """Lossless projection; native persistent storage remains unchanged."""

    cls: type[T]
    encode: Callable[[T], Hashable]
    decode: Callable[[Hashable], T]
