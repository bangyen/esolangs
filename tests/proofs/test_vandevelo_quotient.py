"""Exact quotient fallback, including a forced positive control."""

import pytest

from esolangs.tools.vandevelo import (
    _best,
    _ensure_popular,
    _Node,
    _popularities,
    _quotient_popularities,
)


def _span(directions: list[int]) -> set[int]:
    span = {0}
    for direction in directions:
        span |= {value ^ direction for value in span}
    return span


@pytest.mark.parametrize("directions", [[], [3], [3, 24], [3, 24, 36]])
def test_quotient_counts_match_the_full_transform(directions: list[int]) -> None:
    n = 6
    span = _span(directions)
    points = {base ^ value for base in (0, 4, 16) for value in span}
    node = _Node(0, points, span, None)
    full = _popularities(points, n)
    expected = {
        value: full[value]
        for value in range(1, 1 << n)
        if value == min(value ^ offset for offset in span)
    }
    assert dict(_quotient_popularities(node, n)) == expected


def test_fallback_uses_the_quotient_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    module = importlib.import_module("esolangs.tools.vandevelo")
    span = _span([3, 24, 36])
    points = {base ^ value for base in (0, 4) for value in span}
    full = _popularities(points, 6)
    node = _Node(0, points, span, None)
    dimensions = []
    original = _popularities

    def traced(points: set[int], n: int) -> list[int]:
        dimensions.append(n)
        return original(points, n)

    monkeypatch.setattr(module, "_popularities", traced)
    _ensure_popular(node, 6)
    assert dimensions == [3]
    direction, count = _best(node)
    best = max(full[value] for value in range(64) if value not in span)
    assert count == best
    assert direction == next(
        value for value in range(64) if value not in span and full[value] == best
    )


@pytest.mark.medium
def test_identifier_charge_on_a_rendered_wide_program() -> None:
    import random
    import re

    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.other.vandevelo import _Machine
    from esolangs.tools.helpers import short_name
    from esolangs.tools.vandevelo import _ALPHABET, _bank_cap, vandevelo
    from esolangs.vm import run_until_halt_or_cycle

    n = 13
    table = f"{random.Random(0).getrandbits(1 << n):0{1 << n}b}"
    program = vandevelo(table)
    identifiers = [
        name
        for name in re.findall(r"[A-Za-z0-9_&*$]+", program)
        if name not in {"Inp", "Nil", "loop"}
    ]
    limit = len(short_name(n + _bank_cap(n) - 1, _ALPHABET))
    assert max(map(len, identifiers)) == 2
    assert max(map(len, identifiers)) <= limit
    assert sum(map(len, identifiers)) > len(identifiers)
    for row in (0, 1, (1 << n) - 1):
        stdin = "".join(f"{bit}\n" for bit in f"{row:0{n}b}")
        machine = _Machine(program, ScriptedIO(stdin))
        actual = "0" if run_until_halt_or_cycle(machine, limit=100_000) else "1"
        assert actual == table[row]


def test_projection_only_compacts_one_point_per_coset():
    shifts = []

    class CountedPoint(int):
        def __rshift__(self, bits):
            shifts.append(bits)
            return int(self) >> bits

    span = _span([3, 24, 36])
    points = {CountedPoint(base ^ value) for base in (0, 4) for value in span}
    node = _Node(0, points, span, None)
    expected = _popularities(set(map(int, points)), 6)
    counts = dict(_quotient_popularities(node, 6))
    assert counts == {
        value: expected[value]
        for value in range(1, 64)
        if value == min(value ^ offset for offset in span)
    }
    assert len(shifts) == 2 * 3
