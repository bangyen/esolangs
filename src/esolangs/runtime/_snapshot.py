"""Explicit wire projections for owned immutable snapshot values."""

from collections.abc import Callable, Hashable
from dataclasses import dataclass


@dataclass(frozen=True)
class SnapshotCodec[T]:
    """Lossless projection; native persistent storage remains unchanged."""

    cls: type[T]
    encode: Callable[[T], Hashable]
    decode: Callable[[Hashable], T]


def named_tuple_codec[T: tuple[object, ...]](
    cls: type[T], make: Callable[[tuple[object, ...]], T]
) -> SnapshotCodec[T]:
    """Keep the type of a named tuple explicitly declared by its owner."""

    def decode(payload: Hashable) -> T:
        if type(payload) is not tuple:
            raise TypeError("named tuple snapshot requires a tuple payload")
        return make(payload)

    return SnapshotCodec(cls, tuple, decode)
