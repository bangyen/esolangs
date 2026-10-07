"""Sampled popular-direction fallback, with a forced positive control."""

import importlib

import pytest

from esolangs.tools.vandevelo import _SAMPLES, _best, _ensure_popular, _Node, _pairs


def test_fallback_draws_a_half_average_direction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Three span cosets with no scored candidate: the fallback must fire."""
    module = importlib.import_module("esolangs.tools.vandevelo")
    span = set(range(4))
    points = {base ^ offset for base in (0, 4, 8) for offset in span}
    node = _Node.root(points).below(1).below(2)
    draws = []

    def counted(node: _Node, v: int) -> int:
        draws.append(v)
        return _pairs(node, v)

    monkeypatch.setattr(module, "_pairs", counted)
    _ensure_popular(node, 6)
    direction, count = _best(node)
    assert direction is not None
    assert direction not in span
    assert count == sum((point ^ direction) in points for point in points) == 8
    assert 2 * count * 64 >= len(points) ** 2
    assert 1 <= len(draws) <= _SAMPLES


def test_assure_finds_a_half_average_direction() -> None:
    """Sparse, dense, and inside a span: the pigeonhole bucket count suffices."""
    import random

    from esolangs.tools.vandevelo import _assure

    rng = random.Random(3)
    n = 8
    for density, span_dirs in ((0.05, []), (0.6, []), (0.97, []), (0.6, [0b1011])):
        points = {p for p in range(1 << n) if rng.random() < density}
        node = _Node.root(points)
        for v in span_dirs:
            node = node.below(v)
        _assure(node, n)
        direction, count = _best(node)
        assert direction is not None
        assert node.reduce(direction)
        assert count == _pairs(node, node.reduce(direction))
        size, span = node.size, 1 << node.dim
        assert 2 * count * ((1 << n) - span) >= size * (size - span)


def test_the_clause_bound_holds_on_assure_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No scored candidates, no sampling: the guarded chains still bound C."""
    import random

    from esolangs.tools.vandevelo import _Peel

    module = importlib.import_module("esolangs.tools.vandevelo")
    monkeypatch.setattr(module, "_nearest", lambda *_, **__: [])
    monkeypatch.setattr(module, "_ensure_popular", lambda *_: None)
    rng = random.Random(7)
    for n in (8, 10):
        ones = {p for p in range(1 << n) if rng.random() < 0.5}
        cubes = _Peel(set(ones), n).run()
        covered: set[int] = set()
        for base, dirs in cubes:
            cube = {base}
            for v in dirs:
                cube |= {p ^ v for p in cube}
            covered |= cube
        assert covered == ones
        assert len(cubes) * n <= 17 << n
        assert len(cubes) * n < 1 << n


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
