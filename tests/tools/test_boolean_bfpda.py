"""bfpda generator tests."""

from tests.tools.fills import _run_form


class TestParameterizedBfpda:
    """Input-by-substitution boolean generator for the no-input language BF-PDA."""

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """The setter is four characters whichever bit it carries."""
        from esolangs.tools.bfpda import BFPDA_PAIR
        from tests.tools.fills import fill

        _fill_bfpda = fill("BF-PDA")

        for n in (1, 2, 3):
            template = _run_form(BFPDA_PAIR, n)
            for i in range(n):
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_bfpda(template, zeros)) == len(
                    _fill_bfpda(template, ones)
                ), f"n={n} input {i}"

    def test_leaf_leaves_the_stack_empty(self) -> None:
        """A zero drains and prints the empty stack; a one prints the bottom marker."""
        from esolangs import tools as generators

        assert generators.bfpda("10") == "@<$[>>.]>[>@.>]"  # NOT
        assert generators.bfpda("0110") == (
            "@<$<@<$[>>[>>.]>[>@.>]]>[>[>>@.>]>[>.]]"  # XOR
        )

    def test_the_constructed_lengths_are_stable_over_three_inputs(self) -> None:
        """Total emitted bytes over every three-input table."""
        from esolangs import tools as generators

        total = sum(len(generators.bfpda(format(v, "08b"))) for v in range(256))
        assert total == 14502
