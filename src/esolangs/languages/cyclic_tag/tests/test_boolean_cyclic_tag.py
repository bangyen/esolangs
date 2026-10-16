"""Cyclic tag constant roots consume the input queue without indexed productions."""

import pytest

import esolangs
from esolangs.languages.cyclic_tag.interpreter import _Machine
from esolangs.runtime._evaluate import _evaluate
from esolangs.runtime.io import ScriptedIO


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_uses_one_empty_production_and_deletes_each_embedded_input(
    n, bit
) -> None:
    table = bit * (1 << n)
    template = esolangs.generate("Cyclic tag", table)
    assert template == "," + "$" * n + bit
    assert len(template) == n + 2
    for options in ({}, {"width": 1}, {"width": 8}, {"width": 40}, {"balance": True}):
        program = esolangs.generate("Cyclic tag", table, **options)
        assert _evaluate("Cyclic tag", program, inputs=n) == table
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
