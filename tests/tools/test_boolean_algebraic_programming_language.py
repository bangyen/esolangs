"""Algebraic source budgets, width behavior, and public integration."""

import pytest

import esolangs
from esolangs import tools as boolean
from esolangs.tools.helpers import best_input_order
from tests.tools.boolean_runners import five_input_sample


class TestAlgebraicProgrammingLanguage:
    def test_a_one_entry_table_is_refused(self) -> None:
        with pytest.raises(ValueError, match="a one-entry table is a constant"):
            boolean.algebraic_programming_language("0")

    def test_narrowing_below_the_floor_does_not_widen(self) -> None:
        # Unclamped folding made width 1 wider than width 20.
        for table in ("11111111", "0110100110010110", "01111111"):
            widths = [
                max(
                    len(row)
                    for row in boolean.algebraic_programming_language(
                        table, w
                    ).splitlines()
                )
                for w in (1, 5, 10)
            ]
            assert widths == sorted(widths), (table, widths)

    def test_default_full_tree_growth_is_linear(self) -> None:
        # Parity folds no subtree, so source doubles with each input.
        sizes = []
        for n in (7, 8):
            table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
            sizes.append(len(boolean.algebraic_programming_language(table)))
        assert sizes[1] < 2 * sizes[0] + 32


class TestAlgebraicProgrammingLanguageShapes:
    def test_inline_three_input_corpus_size(self) -> None:
        from esolangs.tools.algebraic_programming_language import _apl_tree_ordered

        total = sum(
            len(best_input_order(f"{value:08b}", _apl_tree_ordered))
            for value in range(256)
        )
        assert total == 16303

    def test_retained_source_corpus_sizes(self) -> None:
        from esolangs.tools.algebraic_programming_language import _apl_tree_ordered

        three = [f"{value:08b}" for value in range(256)]
        for tables, before, after in (
            (three, 16303, 16599),
            (five_input_sample(), 42875, 42440),
        ):
            inline = [len(best_input_order(t, _apl_tree_ordered)) for t in tables]
            reduced = [len(boolean.algebraic_programming_language(t)) for t in tables]
            assert (sum(inline), sum(reduced)) == (before, after)
            previous = 16067 if len(tables) == 256 else 40684
            assert sum(reduced) * 100 < previous * 105


def test_apl_elementary_floor_and_corpus_size() -> None:
    assert (
        max(map(len, boolean.algebraic_programming_language("0110", 1).splitlines()))
        == 4
    )
    assert (
        sum(
            len(boolean.algebraic_programming_language(format(v, "08b"), 1))
            for v in range(256)
        )
        == 20448
    )


@pytest.mark.parametrize("width", [1, 9, 17, 40, 80])
@pytest.mark.parametrize("as_string", [False, True])
def test_apl_elementary_public_tagged_and_plain_source(
    width: int, *, as_string: bool
) -> None:
    program = esolangs.generate("Algebraic Programming Language", "0110", width)
    if as_string:
        program = str(program)
    for bits, expected in (("00", "0"), ("01", "1"), ("10", "1"), ("11", "0")):
        stdin = "\n".join(bits) + "\n"
        assert (
            esolangs.run("Algebraic Programming Language", program, stdin)
            == expected + "\n"
        )
