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
    node = _Node(0, points, span, None)
    draws = []

    def counted(pts: set[int], v: int) -> int:
        draws.append(v)
        return _pairs(pts, v)

    monkeypatch.setattr(module, "_pairs", counted)
    _ensure_popular(node, 6)
    direction, count = _best(node)
    assert direction is not None
    assert direction not in span
    assert count == sum((point ^ direction) in points for point in points) == 8
    assert 2 * count * 64 >= len(points) ** 2
    assert 1 <= len(draws) <= _SAMPLES


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
