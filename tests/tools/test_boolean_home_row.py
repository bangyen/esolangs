"""home_row generator tests."""

from tests.tools.fills import _run_form


class TestParameterizedHomeRow:
    """Input-by-substitution boolean generator for the no-input language Home Row."""

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """Each setter preserves source width."""
        from esolangs.tools.home_row import HOME_ROW_PAIR
        from tests.tools.fills import _fill_home_row

        for n in (1, 2, 3):
            template = _run_form(HOME_ROW_PAIR, n)
            for i in range(n):
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_home_row(template, zeros)) == len(
                    _fill_home_row(template, ones)
                ), f"n={n} input {i}"

    def test_each_input_embedded_once(self) -> None:

        from esolangs import tools as generators
        from esolangs.tools.helpers import runs
        from esolangs.tools.home_row import HOME_ROW_PAIR

        template = generators.home_row("0110")
        # ``runs`` refuses a stray ``$``, so two spans is exactly two embeds
        assert len(runs(template, "$", (HOME_ROW_PAIR,) * 2)) == 2
        assert "a$lsffffaafla$lsffffafl" in template

    def test_rows_that_agree_with_the_last_share_its_leaf(self) -> None:
        """Only the rows before the table's trailing run get a guarded leaf."""
        from esolangs import tools as generators

        shared = generators.home_row("0111")
        separate = generators.home_row("0110")
        assert shared.count("k;") == 1
        assert separate.count("k;") == 3
        assert len(shared) < len(separate)

    def test_the_constructed_lengths_are_stable_over_three_inputs(self) -> None:
        """Total emitted bytes over every three-input table.

        49378 while every leaf re-raised a flag, fanned the index into a
        working copy and restored it; 37410 once a leaf only decrements and
        steps; 34521 once the rows agreeing with the last share its leaf.
        """
        from esolangs import tools as generators

        tables = (format(v, "08b") for v in range(256))
        assert sum(len(generators.home_row(t)) for t in tables) == 34521
