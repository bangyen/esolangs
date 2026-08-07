"""Collatz support for the ZTOALC text generator.

The committed ``ztoalc_starts`` table covers most text lengths; for lengths
it misses, these helpers search for a start whose Collatz trajectory is long
enough and has the smallest maximum visited value.
"""

from array import array

_ZTOALC_TABLE_LIMIT = 1_000_000
_ZTOALC_MAX_LIMIT = 10_000_000
_length_table_cache: dict = {}


def _collatz_prefix(start, n):
    values = []
    value = start
    for _ in range(n):
        values.append(value)
        value = value // 2 if value % 2 == 0 else 3 * value + 1
    return values


def _collatz_length_table(limit):
    """Stopping times for every start up to ``limit``, as unsigned shorts.

    Index ``value`` holds the number of Collatz steps from ``value`` to 1;
    index 1 is 0 and a zero elsewhere means "not yet computed". Chain values
    above ``limit`` are walked through without being stored, keeping the
    table bounded at two bytes per entry.
    """
    lengths = array("H", [0]) * (limit + 1)
    lengths[1] = 0

    for start in range(2, limit + 1):
        if lengths[start]:
            continue

        path = []
        value = start
        while value > 1 and (value > limit or not lengths[value]):
            path.append(value)
            value = value // 2 if value % 2 == 0 else 3 * value + 1

        length = lengths[value] if value <= limit else 0
        for value in reversed(path):
            length += 1
            if value <= limit:
                lengths[value] = length

    return lengths


def _collatz_lengths(limit):
    if limit not in _length_table_cache:
        _length_table_cache[limit] = _collatz_length_table(limit)
    return _length_table_cache[limit]


def _search_start(n: int) -> int:
    """Best start for a text length the committed table does not cover."""
    best: tuple[int, int] | None = None
    limit = _ZTOALC_TABLE_LIMIT
    lengths = _collatz_lengths(limit)
    candidate = _ZTOALC_TABLE_LIMIT

    while candidate <= _ZTOALC_MAX_LIMIT:
        if candidate > limit:
            limit = min(limit * 2, _ZTOALC_MAX_LIMIT)
            lengths = _collatz_lengths(limit)
            continue
        if best is not None and candidate >= best[0]:
            break
        if lengths[candidate] >= n:
            cand_size = max(_collatz_prefix(candidate, n))
            if best is None or cand_size < best[0]:
                best = (cand_size, candidate)
        candidate += 1

    if best is None:
        raise ValueError(
            f"no Collatz start with a trajectory of length {n} within the search limit"
        )
    return best[1]
