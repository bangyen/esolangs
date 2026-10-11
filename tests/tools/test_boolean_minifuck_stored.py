"""Stored residuals preserve live cells through scratch-separated gates."""

import itertools
import random

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.minifuck import _Machine
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from esolangs.tools.minifuck import _lookup_balance, _lookup_layout, _solve
from esolangs.tools.minifuck.sim import PAIR
from esolangs.tools.minifuck.stored import _Plan, plan


@pytest.mark.medium
def test_stored_conjunction_preserves_live_cells():
    rng = random.Random(622026)
    for left, right in ((12, 17), (17, 12), (12, 12)):
        builder = _Plan()
        builder.conjunction(left, right, 22)
        source = builder.render(None)
        assert source is not None
        assert len(source) == builder.size
        for row in range(8):
            for _ in range(8):
                before = rng.getrandbits(32)
                for cell, bit in ((12, row >> 2), (17, row >> 1 & 1), (22, row & 1)):
                    before = (before & ~(1 << cell)) | (bit << cell)
                machine = _Machine(source, ScriptedIO(""))
                machine.state = (source, before, 40, 0, 0)
                while not machine.halted:
                    machine.step()
                after = machine.state[1]
                expected = (before >> 22 & 1) ^ (
                    (before >> left & 1) & (before >> right & 1)
                )
                assert after >> 22 & 1 == expected
                assert machine.state[3] == 0
                for cell in (12, 17, 27):
                    assert after >> cell & 1 == before >> cell & 1
                assert after & 4095 == before & 4095


@pytest.mark.medium
def test_every_small_stored_table_runs():
    for n in range(1, 4):
        for values in itertools.product("01", repeat=1 << n):
            table = "".join(values)
            builder = plan(table)
            template = builder.render(None)
            assert template is not None
            assert len(template) == builder.size
            assert builder.render(builder.size) == template
            assert builder.render(builder.size - 1) is None
            for row, expected in enumerate(table):
                bits = [row >> shift & 1 for shift in range(n - 1, -1, -1)]
                source = fill_runs(template, TEMPLATE_CHAR, (PAIR,) * n, bits)
                assert esolangs.run("Minifuck", source) == expected


@pytest.mark.medium
@pytest.mark.parametrize("seed", range(4))
def test_wider_stored_tables_run(seed):
    rng = random.Random(622026 + seed)
    n = 5
    table = "".join(str(rng.randrange(2)) for _ in range(1 << n))
    builder = plan(table)
    template = builder.render(None)
    assert template is not None
    assert len(template) == builder.size
    for row, expected in enumerate(table):
        bits = [row >> shift & 1 for shift in range(n - 1, -1, -1)]
        source = fill_runs(template, TEMPLATE_CHAR, (PAIR,) * n, bits)
        assert esolangs.run("Minifuck", source) == expected


@pytest.mark.medium
@pytest.mark.parametrize(
    ("width", "balance"), [(None, False), (1, False), (40, False), (None, True)]
)
def test_public_wider_sharing_runs(width, balance):
    n = 12
    table = "".join(str(int(row.bit_count() >= 2)) for row in range(1 << n))
    template = esolangs.generate("Minifuck", table, width=width, balance=balance)
    assert isinstance(template, str)
    natural = _solve(table)
    legacy = (
        _lookup_balance(table, natural)
        if balance
        else _lookup_layout(table, n, natural, width)
    )
    assert len(template) < len(legacy)
    for row in (0, 1, 3, 7, (1 << n) - 1):
        bits = [row >> shift & 1 for shift in range(n - 1, -1, -1)]
        source = esolangs.instantiate("Minifuck", template, bits)
        assert esolangs.run("Minifuck", source) == table[row]
