"""grapheme generator tests."""

import importlib

import pytest

from esolangs import tools as boolean
from esolangs.tools.grapheme import _grapheme_table
from tests.generator_support import evaluate_generated
from tests.tools.boolean_runners import (
    run_grapheme,
)


class TestGrapheme:
    def test_a_literal_pushes_its_value(self) -> None:
        """Int mode spells every value, 6 included, as one literal."""
        from esolangs.tools.grapheme import _grapheme_literal

        for value in (0, 1, 16, 106, 1006, 1_263_460, 9_999_996, 5_666_666):
            code = _grapheme_literal(value)
            assert run_grapheme(code + "Y", []) == str(value), value

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

    @staticmethod
    def _one_minterm(n: int) -> str:
        """A table whose single 1 makes every one of its ``n`` inputs matter."""
        return "1" + "0" * (2**n - 1)

    def test_padding_never_reaches_an_entry(self) -> None:
        """Every entry survives the lift that forces a leading decimal 1."""
        for n in range(1, 9):
            for table in (self._one_minterm(n), "01" * (2 ** (n - 1))):
                packed = _grapheme_table(table)
                assert str(packed)[0] == "1"
                low = format(packed % (1 << len(table)), f"0{len(table)}b")
                assert low == table

    def test_an_off_by_one_shift_returns_a_wrong_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The positive control: the index is load-bearing, not decoration.

        Doubling the packed table shifts every entry one bit up, which the
        accumulator's power of two no longer cancels.  Without this control a
        table that happened to read right anywhere would look like proof.
        """
        packed = _grapheme_table
        module = importlib.import_module("esolangs.tools.grapheme")
        monkeypatch.setattr(module, "_grapheme_table", lambda t: 2 * packed(t))
        table = self._one_minterm(6)
        assert evaluate_generated("Grapheme", table, timeout=60) != table
