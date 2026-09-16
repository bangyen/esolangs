"""A persistent tape: an immutable sequence whose writes cost a chunk, not the tape.

The pure interpreters keep their tape inside an immutable state value, so a
write returns a new tape rather than editing one in place.  As a flat tuple
that costs the whole tape per write -- ``(*cells[:i], v, *cells[i + 1:])``
-- and the boolean corpus grows its tapes to Theta(T) cells and writes
Theta(T) times, so a program's execution grew as Theta(T^2) while its
command count stayed linear: BrainIf x2.5 per added input at nine inputs,
LaserFuck x2.6, Jaune x2.5, RAM0 x2.5, against a linear x2.0.

This keeps the tape a value -- a tuple, hashable, comparable, sharable
between states -- and stores it as a tuple of fixed-size chunks.  A write
rebuilds the one chunk it lands in and the outer tuple of chunk references,
``CHUNK + len(tape) / CHUNK`` copies instead of ``len(tape)``, and every
untouched chunk is the *same object* in the new tape.  That sharing is what
makes the cycle detector cheaper too: Brent's check compares snapshots by
tuple equality, and an unchanged chunk compares by identity.

The invariant: every chunk but the first and last holds exactly
:data:`CHUNK` items, and those two hold one to :data:`CHUNK` each, so the
tape grows cheaply at either end -- LaserFuck's ``<`` at the origin grows
it leftward, once per cell the program reaches.  An empty tape is ``()``.
Indexing pads the first chunk up to full on the fly, so a leading partial
chunk costs one subtraction per read rather than a re-chunking per prepend.
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
