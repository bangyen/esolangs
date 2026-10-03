"""bfpda generator tests."""

from tests.tools.fills import _run_form


class TestParameterizedBfpda:
    """Input-by-substitution boolean generator for the no-input language BF-PDA."""

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """Each setter preserves source width."""
        from esolangs.tools.bfpda import BFPDA_PAIR
        from tests.tools.fills import _fill_bfpda

        for n in (1, 2, 3):
            template = _run_form(BFPDA_PAIR, n)
            for i in range(n):
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_bfpda(template, zeros)) == len(
                    _fill_bfpda(template, ones)
                ), f"n={n} input {i}"

    def test_program_structure(self) -> None:
        """Each input is embedded once (pre-loaded), not re-embedded per node."""

        from esolangs import tools as generators
        from esolangs.tools.bfpda import BFPDA_PAIR
        from esolangs.tools.helpers import runs

        template = generators.bfpda("0110")
        # ``runs`` refuses a stray ``$``, so two spans is exactly two embeds
        assert runs(template, "$", (BFPDA_PAIR,) * 2) == [(2, 3), (6, 7)]
        assert template.startswith("@<$<@<$")

    def test_the_constructed_lengths_are_stable_over_three_inputs(self) -> None:
        """Total emitted bytes over every three-input table.

        24127 while each arm pushed a zero to break its loop and popped it
        after, and each leaf pushed its answer; 17578 once the arms end on
        the empty stack a leaf leaves behind; 16042 with fresh-cell setters.
        """
        from esolangs import tools as generators

        total = sum(len(generators.bfpda(format(v, "08b"))) for v in range(256))
        assert total == 16042
