"""Tests for the Stisp Boolean generator."""

import pytest

import esolangs
from esolangs import compat
from esolangs.languages.stisp.interpreter import _Machine
from esolangs.languages.stisp.proof_formulas import workspace
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState

#: Every one- and two-input table; a diagram's folding bugs show here first.
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_results_in_its_answer(table: str) -> None:
    if table == "00":
        _check_constants()
    n = len(table).bit_length() - 1
    template = compat.generate("Stisp", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        program = compat.instantiate("Stisp", template, bits)
        got = compat.run("Stisp", program, timeout=5)
        assert esolangs.read_answer("Stisp", got) == table[row], (table, row)
        io = ScriptedIO("7")
        machine = _Machine(program, io)
        written = WrittenState(machine.snapshot())
        steps = 0
        while not machine.halted:
            machine.step()
            written.sample(machine.snapshot())
            steps += 1
            assert io.getvalue() == ""
        assert steps == (1 if len(set(table)) == 1 else n)
        assert written.bits <= workspace(n, program)
        before_dump = written.bits
        machine.step()
        written.sample(machine.snapshot())
        assert written.bits == before_dump + 1
        assert io.getvalue() == table[row]
        assert io.reads == 0
        assert io.input_char() == ord("7")


def test_the_and_template_is_the_documented_one() -> None:
    assert compat.generate("Stisp", "0001") == (
        "(l h)->s[0]=l;(l h)->s[1]=h;c->s[x]=c;(0 (0 1))->s[$]->s[$]"
    )


def test_an_ignored_input_still_selects_one_of_two_identical_children() -> None:
    assert compat.generate("Stisp", "0101") == (
        "(l h)->s[0]=l;(l h)->s[1]=h;c->s[x]=c;((0 1) (0 1))->s[$]->s[$]"
    )


def _check_constants() -> None:
    from esolangs.languages.stisp.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    assert sum(len(compat.generate("Stisp", f"{i:08b}")) for i in range(256)) == 20552
    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                template = compat.generate("Stisp", bit * (1 << n), **options)
                assert str(template).count("$") == n
                if not options:
                    assert len(template) == (15 if n == 1 else 2 * n + 15)
                peak = 0
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    bits = list(map(int, f"{row:0{n}b}"))
                    program = template.fill(bits)
                    io = ScriptedIO("7")
                    machine = _Machine(program, io)
                    head = machine.head
                    values = [head] if n == 1 else []
                    if n > 1:
                        while head != ():
                            value, head = head
                            values.append(value)
                    assert values == list(map(str, bits))
                    written = WrittenState(machine.snapshot())
                    machine.step()
                    written.sample(machine.snapshot())
                    assert machine.halted
                    assert machine.head == bit
                    assert io.getvalue() == ""
                    assert written.bits <= 8 * n + 8
                    peak = max(peak, written.bits)
                    machine.step()
                    written.sample(machine.snapshot())
                    assert io.getvalue() == bit
                    assert io.reads == io.past_end == 0
                    assert io.input_num() == 7
                    assert written.bits <= 8 * n + 9
                assert peak == 8 * n + 8
