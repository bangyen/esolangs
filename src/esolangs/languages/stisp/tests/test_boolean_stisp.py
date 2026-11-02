"""Tests for the Stisp Boolean generator."""

import pytest

import esolangs

#: Every one- and two-input table; a diagram's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_results_in_its_answer(table: str) -> None:
    if table == "00":
        _check_constants()
    n = len(table).bit_length() - 1
    template = esolangs.generate("Stisp", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        program = esolangs.instantiate("Stisp", template, bits)
        got = esolangs.run("Stisp", program, timeout=5)
        assert esolangs.read_answer("Stisp", got) == table[row], (table, row)


def test_the_and_template_is_the_documented_one() -> None:
    assert esolangs.generate("Stisp", "0001") == (
        "3->s[0]=0;3->s[1]=2;2->s[0]=0;2->s[1]=1;c->s[x]=c;3->s[$]->s[$]"
    )


def test_an_ignored_input_is_one_equation_over_a_variable() -> None:
    assert esolangs.generate("Stisp", "0101") == (
        "3->s[x]=2;2->s[0]=0;2->s[1]=1;c->s[x]=c;3->s[$]->s[$]"
    )


def _check_constants() -> None:
    from esolangs.languages.stisp.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                template = esolangs.generate("Stisp", bit * (1 << n), **options)
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
                    machine.step()
                    written.sample(machine.snapshot())
                    assert io.getvalue() == bit
                    assert io.reads == io.past_end == 0
                    assert io.input_num() == 7
                    assert written.bits <= 8 * n + 9
                    peak = max(peak, written.bits)
                assert peak == 8 * n + 9
