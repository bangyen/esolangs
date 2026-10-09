"""grapheme generator tests."""

import importlib

import pytest

from esolangs import tools as boolean
from esolangs._grapheme import GraphemeDialect
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.grapheme import run
from esolangs.tools.grapheme import _grapheme_literal, _grapheme_push65, _grapheme_table
from tests.generator_support import evaluate_generated
from tests.tools.test_boolean_contract import _one_minterm


class TestGrapheme:
    def test_there_is_no_branch_left(self) -> None:
        """Indexing a literal needs no skip: parity emits no ``U``/``V``/``X``."""
        parity = boolean.grapheme("01101001")
        assert set("UVX").isdisjoint(parity)
        assert set("UVX").isdisjoint(boolean.grapheme("0" * 8))

    def test_the_table_costs_about_a_third_of_a_character_an_entry(self) -> None:
        """The literal is the table in base 10, so log10(2) letters an entry."""
        sizes = []
        for n in (7, 11):
            table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
            sizes.append(len(boolean.grapheme(table)))
        grown = (sizes[1] - sizes[0]) / ((1 << 11) - (1 << 7))
        assert 0.30 < grown < 0.35, sizes

    def test_the_program_is_only_grapheme_commands(self) -> None:
        """Only int-mode digits and the commands used are emitted."""
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.grapheme(table)) <= set("ABCDEFGHIKLMPRSTWYZ"), table


class TestGraphemeTable:
    """The one literal holding the table, and the index that shifts it."""

    def test_padding_never_reaches_an_entry(self) -> None:
        """Every entry survives the lift that forces a leading decimal 1."""
        for n in range(1, 9):
            for table in (_one_minterm(n), "01" * (2 ** (n - 1))):
                packed = _grapheme_table(table)
                assert str(packed)[0] == "1"
                low = format(packed % (1 << len(table)), f"0{len(table)}b")
                assert low == table

    @pytest.mark.parametrize("n", [6, 7, 8, 9])
    @pytest.mark.medium
    def test_a_table_using_every_input_still_computes(self, n: int) -> None:
        """Six essential inputs reached slot 5, whose old key was ``FFF``."""
        table = _one_minterm(n)
        assert evaluate_generated("Grapheme", table, timeout=60) == table

    def test_parity_at_six_inputs_computes(self) -> None:
        """Parity is the table with nothing to fold, so every input is live."""
        table = "".join(str(bin(row).count("1") & 1) for row in range(64))
        assert evaluate_generated("Grapheme", table, timeout=60) == table

    def test_an_off_by_one_shift_returns_a_wrong_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The positive control: the index is load-bearing, not decoration."""
        packed = _grapheme_table
        module = importlib.import_module("esolangs.tools.grapheme")
        monkeypatch.setattr(module, "_grapheme_table", lambda t: 2 * packed(t))
        table = _one_minterm(6)
        assert evaluate_generated("Grapheme", table, timeout=60) != table


@pytest.mark.parametrize("mode", ["between_letters", "after_each_letter"])
def test_generator_literals_are_exact(mode):
    dialect = GraphemeDialect(integer_conversion=mode)
    for value in (0, 1, 2, 5, 13, 16, 106, 1006, 1263460, 5666666, 9999996):
        io = ScriptedIO("")
        run(_grapheme_literal(value, dialect) + "Y", io, integer_conversion=mode)
        assert io.getvalue() == str(value)
    io = ScriptedIO("")
    run(_grapheme_push65(dialect) + "Y", io, integer_conversion=mode)
    assert io.getvalue() == "65"
