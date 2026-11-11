"""Cyclic tag constant roots consume the input queue without indexed productions."""

import pytest

import esolangs
from esolangs.languages.cyclic_tag.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from scripts.docs.evidence import construction_boundaries
from tests.support.evaluation import _evaluate
from tests.support.generator_support import assert_saved_rows, constant_artifacts


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_uses_one_empty_production_and_deletes_each_embedded_input(
    n, bit
) -> None:
    if n == 1 and bit == "0":
        _check_constants()
    table = bit * (1 << n)
    template = esolangs.generate("Cyclic tag", table)
    assert template.source == "," + "$" * n + bit
    assert len(template.source) == n + 2
    for options in ({}, {"width": 1}, {"width": 8}, {"width": 40}, {"balance": True}):
        program = esolangs.generate("Cyclic tag", table, **options)
        assert _evaluate("Cyclic tag", program, inputs=n) == table
    for row in range(1 << n):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        filled = esolangs.instantiate("Cyclic tag", template, bits)
        io = ScriptedIO("")
        machine = _Machine(filled.source, io)
        assert machine.program == ("",)
        for _ in range(n + 1):
            assert not machine.halted
            machine.step()
        assert machine.halted
        assert machine.read == n + 1
        assert len(machine.data) == n + 1
        machine.step()
        assert io.getvalue() == bit


def _check_constants() -> None:

    language = esolangs.Language("Cyclic tag")
    for witness in construction_boundaries(language.name)["endpoint_and_marker_cutoff"]:
        table = witness.table()
        artifact = language.generate(table)
        rules = artifact.source.partition(",")[0].split(";")
        assert rules[witness.arity] == ("1" if witness.arity == 2 else "10")
        assert_saved_rows(language, artifact, table, range(len(table)))

    for n, bit, _options, template in constant_artifacts("Cyclic tag", range(1, 13)):
        assert template.source.count("$") == n
        for bits in ([0] * n, [1] * n):
            program = esolangs.instantiate("Cyclic tag", template, bits)
            io = ScriptedIO("7")
            machine = _Machine(program.source, io)
            assert machine.data == [str(b) for b in bits] + [bit]
            for count in range(n + 1):
                assert machine.read == count
                machine.step()
                assert not io.getvalue()
            assert machine.halted
            assert machine.read == n + 1
            machine.step()
            assert io.getvalue() == bit
            assert io.reads == 0
            assert io.input_char() == ord("7")


@pytest.mark.medium
def test_minority_marker_keeps_answer_after_padding(monkeypatch) -> None:
    """The final one must stop past its queued zero, without wrapping to input0."""
    for n in (2, 3, 5):
        size = 1 << n
        for table in ("0" * (size - 1) + "1", "1" + "0" * (size - 1)):
            for options in ({}, {"width": 1}, {"balance": True}):
                template = esolangs.generate("Cyclic tag", table, **options)
                assert template.source.count("$") == n
                assert _evaluate("Cyclic tag", template, inputs=n) == table
    for table in ("00000101", "10100000"):
        assert (
            _evaluate("Cyclic tag", esolangs.generate("Cyclic tag", table), inputs=3)
            == table
        )
    totals = [
        sum(
            len(esolangs.generate("Cyclic tag", f"{table:0{1 << n}b}").source)
            for table in range(1 << (1 << n))
        )
        for n in (2, 3)
    ]
    assert totals == [211, 6721]
    from esolangs.languages.cyclic_tag import generator

    assert not hasattr(generator, "_program")
    canonical = generator.input_weights

    def wrong_weights(table, n):
        lookup = canonical(table, n)
        return type(lookup)(lookup.weights[::-1], lookup.table)

    with monkeypatch.context() as patch:
        patch.setattr(generator, "input_weights", wrong_weights)
        mutant = esolangs.generate("Cyclic tag", "0011")
        with pytest.raises(AssertionError):
            assert _evaluate("Cyclic tag", mutant, inputs=2) == "0011"
