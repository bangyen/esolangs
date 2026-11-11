"""home_row generator tests."""

import random

import pytest

import esolangs
from esolangs.runtime.io import ScriptedIO
from tests.support.analysis_support import assert_analysis_complement
from tests.support.witness_tables import row_bits


@pytest.mark.parametrize("n", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_setters_leave_scratch_zero(n: int, bit: str) -> None:
    from esolangs.languages.home_row.interpreter import _Machine

    if n == 1 and bit == "0":
        _check_constants()
    table = bit * (1 << n)
    programs = [esolangs.generate("Home Row", table, width=w) for w in (None, 1, 20)]
    programs.append(esolangs.generate("Home Row", table, balance=True))
    for program in programs:
        assert program.source.count("$") == n
        for row in range(1 << n):
            bits = [int(value) for value in f"{row:0{n}b}"]
            io = ScriptedIO("")
            machine = _Machine(
                esolangs.instantiate("Home Row", program, bits).source, io
            )
            for _ in range(1000):
                if machine.halted:
                    break
                machine.step()
            assert machine.halted
            assert io.getvalue() == bit


class TestParameterizedHomeRow:
    """Input-by-substitution boolean generator for the no-input language Home Row."""

    def run_home_row(self, prog: str) -> str:
        from esolangs.languages.home_row.interpreter import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Bind native source with explicitly declared setters."""
        from esolangs.languages.home_row.descriptor import HOME_ROW_PAIR

        bindings = esolangs.TemplateBindings(setters=(HOME_ROW_PAIR,) * len(bits))
        template = esolangs.TemplateArtifact(tpl, "Home Row", bindings)
        return esolangs.instantiate("Home Row", template, bits).source

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """The setter is two characters whichever bit it carries."""
        from esolangs.languages.home_row.descriptor import HOME_ROW_PAIR

        for n in (1, 2, 3):
            template = "$" * len(HOME_ROW_PAIR[0]) * n
            for i in range(n):
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(self.instantiate(template, zeros)) == len(
                    self.instantiate(template, ones)
                ), f"n={n} input {i}"

    def test_five_inputs_sample(self) -> None:
        """A sample of dense five-input tables, past the removed n <= 2 cap."""

        from esolangs.languages.home_row import generator as generators

        n = 5
        rng = random.Random(0)
        for _ in range(5):
            table = "".join(rng.choice("01") for _ in range(2**n))
            template = generators.home_row(table)
            for combo in range(2**n):
                bits = row_bits(combo, n)
                got = self.run_home_row(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has input runs, not hardcoded bits."""
        from esolangs._bindings import runs
        from esolangs.languages.home_row import generator as generators
        from esolangs.languages.home_row.descriptor import HOME_ROW_PAIR

        template = generators.home_row("0110")
        assert "{X" not in template
        # each packing line opens with its two-character run
        assert "a$lsfffaffla$lsfafffsfl" in template
        # ``runs`` refuses a stray ``$``, so two spans is exactly two embeds
        assert len(runs(template, "$", (HOME_ROW_PAIR,) * 2)) == 2
        assert "{C0}" not in template
        assert "{C1}" not in template

    def test_pairs_that_agree_with_the_last_share_its_leaf(self) -> None:
        """Only the pairs before the table's trailing run get a guarded leaf."""
        from esolangs.languages.home_row import generator as generators
        from esolangs.languages.home_row.generator import _SETUP

        gates = "a$lsfffaffla$lsfafffsfl"
        assert generators.home_row("0111") == (
            _SETUP + gates + "fff" + "jfffflk;lf" + "dddk"
        )
        # The two pairs of the first run are one leaf behind a clamped decrement.
        gates = "a$lsfffaaffla$lsfffaffla$lsfafffsfl"
        assert generators.home_row("00000110") == _SETUP + gates + "fff" + (
            "jsjddlk;lddds" + "jfffflk;lf" + "fk"
        )

    def test_the_constructed_lengths_are_stable_over_three_inputs(self) -> None:
        """Total emitted bytes over every three-input table."""
        from esolangs.languages.home_row import generator as generators

        tables = (format(v, "08b") for v in range(256))
        assert sum(len(generators.home_row(t)) for t in tables) == 32776


def _check_constants() -> None:
    assert_analysis_complement("Home Row", "read_at")
    from esolangs.languages.home_row.interpreter import _Machine

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Home Row", bit * (1 << n), **options)
                template = "".join(program.source.split())
                slots = {i for i, char in enumerate(template) if char == "$"}
                assert len(slots) == n
                for bits in ([0] * n, [1] * n):
                    io = ScriptedIO("7")
                    machine = _Machine(
                        esolangs.instantiate("Home Row", program, bits).source, io
                    )
                    visited = set()
                    steps = 0
                    while not machine.halted and steps < 200:
                        if machine.ind in slots:
                            assert machine.grid[machine.ptr] == 0
                            visited.add(machine.ind)
                        if machine.code[machine.ind] == "k":
                            assert visited == slots
                        machine.step()
                        steps += 1
                    assert machine.halted
                    assert steps <= 2 * n + 99 + int(bit)
                    assert io.getvalue() == bit
                    assert io.reads == 0
                    assert io.input_char() == ord("7")
