"""Exact indexed FRACTRAN transitions and the linear construction."""

# ruff: noqa: SLF001

from __future__ import annotations

import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fractran import _choose, _Machine, _parse
from esolangs.tools.fractran import PAIR, _threshold, fractran
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs


def _row(template: str, table: str, row: int, *, literal: bool) -> tuple[int, int]:
    n = len(table).bit_length() - 1
    code = fill_runs(
        template,
        TEMPLATE_CHAR,
        [PAIR] * n,
        [(row >> (n - 1 - i)) & 1 for i in range(n)],
    )
    io = ScriptedIO("")
    machine = _Machine(code, io)
    assert machine._index is not None
    assert all(keys is not None for keys in machine._index.keys.values())
    if literal:
        value, fractions, _ = _parse(code)
        assert machine.fractions == fractions
    steps = 0
    while not machine.halted:
        if literal:
            index = _choose(value, fractions)
            assert machine._next() == index
            if index is not None:
                a, b = fractions[index]
                value = value * a // b
        machine.step()
        steps += 1
        assert steps <= 4 * n + 4
        if literal:
            assert machine.value == value
    assert machine.value == (2 if table[row] == "1" else 1)
    assert machine.inspections <= 16 * (n + 1) ** 2
    return steps, machine.inspections


@pytest.mark.medium
def test_seeded_tables_and_controls_execute_indexed() -> None:
    rng = random.Random(20261001)
    for n in range(4, 9):
        size = 1 << n
        tables = [
            "0" * size,
            "1" * size,
            "".join(str(row.bit_count() % 2) for row in range(size)),
        ]
        tables += ["".join(rng.choice("01") for _ in range(size)) for _ in range(4)]
        for table in tables:
            template = _threshold(table, n)
            for row in range(size):
                _row(template, table, row, literal=n <= 6)


def test_bounded_bases_do_not_materialize_large_powers() -> None:
    machine = _Machine("3^1000000 5^999999/3^1000000 1/5^999999", ScriptedIO(""))
    assert machine._index is not None
    assert machine._fractions is None
    before = machine.snapshot()
    machine.step()
    assert machine._factors == ((5, 999999),)
    assert machine.snapshot() != before
    assert machine._fractions is None
    machine.step()
    machine.step()
    assert machine.halted
    assert machine.value == 1


def test_index_preserves_reduced_guards_and_nonmonotone_priority() -> None:
    rng = random.Random(7)
    for _ in range(100):
        start = rng.randrange(1, 50)
        pairs = [(rng.randrange(1, 25), rng.randrange(1, 25)) for _ in range(6)]
        code = " ".join([str(start), *(f"{a}/{b}" for a, b in pairs)])
        machine = _Machine(code, ScriptedIO(""))
        assert machine._index is not None
        value, fractions, _ = _parse(code)
        for _step in range(16):
            index = _choose(value, fractions)
            assert machine._next() == index
            machine.step()
            if index is None:
                assert machine.halted
                break
            a, b = fractions[index]
            value = value * a // b
            assert machine.value == value


@pytest.mark.parametrize("width", [1, 3, 4, 9, 10, 19])
def test_narrow_template_provenance(width: int) -> None:
    import esolangs
    from esolangs.exceptions import TemplateError

    table = "0110"
    template = esolangs.generate("fractran", table, width=width)
    for text in (template, str(template)):
        code = esolangs.instantiate("fractran", text, [0, 1], truth_table=table)
        machine = _Machine(code, ScriptedIO(""))
        for _ in range(12):
            if machine.halted:
                break
            machine.step()
        assert machine.halted
        assert machine.value == 2
        with pytest.raises(TemplateError):
            esolangs.instantiate("fractran", text, [0, 1], truth_table="0001")


@pytest.mark.parametrize("n", [5, 7])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_folded_constant_paths_discard_all_embedded_inputs(n: int, bit: str) -> None:
    from esolangs.tools.fractran import fractran_setters

    table = bit * 2**n
    template = fractran(table, 1)
    for bits in [[0] * n, [1] * n]:
        code = fill_runs(template, TEMPLATE_CHAR, fractran_setters(template, n), bits)
        machine = _Machine(code, ScriptedIO(""))
        for _ in range(4 * n + 4):
            if machine.halted:
                break
            machine.step()
        assert machine.halted
        assert machine.value == (2 if bit == "1" else 1)


def test_binary_parity_uses_three_column_fractions() -> None:
    import esolangs

    template = esolangs.generate("FRACTRAN", "0110", width=1)
    assert max(map(len, template.splitlines())) == 3
    assert len(template) == 14
    for row, expected in enumerate("0110"):
        code = esolangs.instantiate("FRACTRAN", template, [row >> 1, row & 1], width=1)
        assert max(map(len, code.splitlines())) == 3
        machine = _Machine(code, ScriptedIO(""))
        for _ in range(8):
            if machine.halted:
                break
            machine.step()
        assert machine.halted
        assert machine.value == 1 + int(expected)
