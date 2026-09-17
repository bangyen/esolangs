"""The chunked persistent tape behaves as the flat tuple it replaces."""

from __future__ import annotations

import random

import pytest

from esolangs.interpreters.persistent import (
    CHUNK,
    Chunked,
    append,
    chunked,
    flatten,
    get,
    length,
    prepend,
    put,
)


def _random_history(seed: int) -> tuple[list[int], Chunked[int]]:
    """Apply one random mix of appends, prepends and writes to both shapes."""
    rng = random.Random(seed)
    reference: list[int] = []
    tape: Chunked[int] = ()
    for _ in range(rng.randint(0, 3 * CHUNK + 5)):
        roll = rng.random()
        value = rng.randint(0, 9)
        if roll < 0.3:
            reference.append(value)
            tape = append(tape, value)
        elif roll < 0.5:
            reference.insert(0, value)
            tape = prepend(tape, value)
        elif reference:
            index = rng.randrange(len(reference))
            reference[index] = value
            tape = put(tape, index, value)
    return reference, tape


@pytest.mark.parametrize("seed", range(200))
def test_every_history_reads_back_as_the_list(seed: int) -> None:
    """Flatten, length and every index agree with a list after any history."""
    reference, tape = _random_history(seed)
    assert flatten(tape) == tuple(reference)
    assert length(tape) == len(reference)
    for index, expected in enumerate(reference):
        assert get(tape, index) == expected


@pytest.mark.parametrize("seed", range(50))
def test_the_chunk_invariant_holds(seed: int) -> None:
    """Every chunk but the first and last is full; none is empty."""
    _reference, tape = _random_history(seed)
    assert all(len(chunk) == CHUNK for chunk in tape[1:-1])
    assert all(chunk for chunk in tape)


def test_reads_past_the_end_raise() -> None:
    """The end is an error, as it is for a tuple, and so is a negative index."""
    tape = chunked(range(CHUNK + 3))
    with pytest.raises(IndexError):
        get(tape, CHUNK + 3)
    with pytest.raises(IndexError):
        put(tape, CHUNK + 3, 0)
    with pytest.raises(IndexError):
        get(prepend((), 1), 1)
    with pytest.raises(IndexError):
        get((), 0)
    # A tuple would read a negative index from the end; a tape has no end
    # to count from, since its last chunk is partial.
    with pytest.raises(IndexError):
        get(tape, -1)


def test_a_write_shares_every_untouched_chunk() -> None:
    """The point of the shape: a write rebuilds one chunk, not the tape.

    The cycle detector compares snapshots by tuple equality, which is an
    identity check per element, so sharing is what keeps that cheap too.
    """
    tape = chunked(range(4 * CHUNK))
    written = put(tape, CHUNK + 1, -1)
    assert written[1] is not tape[1]
    assert all(written[i] is tape[i] for i in (0, 2, 3))
    assert flatten(written)[CHUNK + 1] == -1


def test_the_tape_is_a_hashable_value() -> None:
    """States hold the tape, and states are hashed and compared."""
    one = append(chunked(range(5)), 9)
    other = put(chunked(range(6)), 5, 9)
    assert one == other
    assert hash(one) == hash(other)
