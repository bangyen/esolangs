"""A persistent tape: an immutable sequence whose writes cost a chunk, not the tape.

A flat-tuple write ``(*cells[:i], v, *cells[i + 1:])`` copies the whole
tape, and the boolean corpus writes Theta(T) times to Theta(T) cells, so
execution grew Theta(T^2): BrainIf x2.5 per added input at nine inputs,
LaserFuck x2.6, Jaune x2.5, RAM0 x2.5, against a linear x2.0.  Stored as
a tuple of fixed-size chunks, a write costs ``CHUNK + len(tape) / CHUNK``
copies and every untouched chunk is the *same object*, which also makes
Brent's snapshot equality compare by identity.

Invariant: every chunk but the first and last holds exactly :data:`CHUNK`
items, those two hold one to :data:`CHUNK`, and an empty tape is ``()``.
Indexing pads the first chunk on the fly, so a prepend never re-chunks.
"""

from __future__ import annotations

from collections.abc import Iterable

#: Items per chunk.  A power of two so the index splits with a shift and a
#: mask; 32 puts the crossover with a flat tuple near sixty cells, below
#: every boolean program's tape, and keeps a write under a hundred copies out
#: to the two thousand cells the ten-input corpus reaches.
CHUNK = 32
_SHIFT = CHUNK.bit_length() - 1
_MASK = CHUNK - 1

type Chunked[T] = tuple[tuple[T, ...], ...]


def chunked[T](items: Iterable[T]) -> Chunked[T]:
    """Build a chunked tape from a sequence."""
    flat = tuple(items)
    return tuple(flat[i : i + CHUNK] for i in range(0, len(flat), CHUNK))


def flatten[T](tape: Chunked[T]) -> tuple[T, ...]:
    """Return the tape as one flat tuple, for the views that report it."""
    return tuple(item for chunk in tape for item in chunk)


def length[T](tape: Chunked[T]) -> int:
    """Return how many items the tape holds."""
    if len(tape) < 2:
        return len(tape[0]) if tape else 0
    return (len(tape) - 2) * CHUNK + len(tape[0]) + len(tape[-1])


def _locate[T](tape: Chunked[T], index: int) -> tuple[int, int]:
    """Split ``index`` into (chunk, offset), padding the first chunk."""
    if index < 0:
        raise IndexError(index)
    pad = CHUNK - len(tape[0])
    padded = index + pad
    outer, inner = padded >> _SHIFT, padded & _MASK
    # The first chunk is stored without its padding, so its offsets shift
    # back down; every later chunk is full and its offsets stand.
    return outer, inner - pad if outer == 0 else inner


def get[T](tape: Chunked[T], index: int) -> T:
    """Return the item at ``index``; raises :class:`IndexError` past the end."""
    outer, inner = _locate(tape, index)
    chunk = tape[outer]
    if outer and inner >= len(chunk):
        raise IndexError(index)
    return chunk[inner]


def put[T](tape: Chunked[T], index: int, value: T) -> Chunked[T]:
    """Return the tape with ``index`` set to ``value``.

    ``index`` must be inside the tape; growth is :func:`append` and
    :func:`prepend`.
    """
    outer, inner = _locate(tape, index)
    chunk = tape[outer]
    if outer and inner >= len(chunk):
        raise IndexError(index)
    chunk = (*chunk[:inner], value, *chunk[inner + 1 :])
    return (*tape[:outer], chunk, *tape[outer + 1 :])


def append[T](tape: Chunked[T], value: T) -> Chunked[T]:
    """Return the tape one item longer at the right end."""
    if tape and len(tape[-1]) < CHUNK:
        return (*tape[:-1], (*tape[-1], value))
    return (*tape, (value,))


def prepend[T](tape: Chunked[T], value: T) -> Chunked[T]:
    """Return the tape one item longer at the left end, ``value`` at index 0."""
    if tape and len(tape[0]) < CHUNK:
        return ((value, *tape[0]), *tape[1:])
    return ((value,), *tape)
