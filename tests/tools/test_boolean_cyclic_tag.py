"""Cyclic tag constant roots consume the input queue without indexed productions."""

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.queue_based.cyclic_tag import _Machine
from esolangs.tools.cyclic_tag import PAIR, _program
from esolangs.tools.helpers import TEMPLATE_CHAR, mark_runs, unmark
from esolangs.tools.wrap import balance_program, balance_score


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_uses_one_empty_production_and_deletes_each_embedded_input(n, bit):
    table = bit * (1 << n)
    template = esolangs.generate("Cyclic tag", table)
    assert template == "," + "$" * n + bit
    assert len(template) == n + 2
    legacy = _program(table, keep_constant_walk=True)
    assert len(template) < len(legacy)
    for options in ({}, {"width": 1}, {"width": 8}, {"width": 40}, {"balance": True}):
        program = esolangs.generate("Cyclic tag", table, **options)
        assert _evaluate("Cyclic tag", program, inputs=n) == table
        if options.get("balance"):
            marked = mark_runs(legacy, TEMPLATE_CHAR, (PAIR,) * n)
            old = unmark(balance_program(marked, "cyclic_tag"), TEMPLATE_CHAR, n)
            assert balance_score(program) <= balance_score(old)
    for row in range(1 << n):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        filled = esolangs.instantiate("Cyclic tag", template, bits)
        io = ScriptedIO("")
        machine = _Machine(filled, io)
        assert machine.program == ("",)
        for _ in range(n + 1):
            assert not machine.halted
            machine.step()
        assert machine.halted
        assert machine.read == n + 1
        assert len(machine.data) == n + 1
        machine.step()
        assert io.getvalue() == bit
