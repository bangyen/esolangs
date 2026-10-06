"""home_row generator tests."""

import random

import pytest

from tests.tools.fills import _run_form


class TestParameterizedHomeRow:
    """Input-by-substitution boolean generator for the no-input language Home Row."""

    def run_home_row(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.home_row import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from tests.tools.fills import _fill_home_row

        return _fill_home_row(tpl, bits)

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """The setter is two characters whichever bit it carries."""
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

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # majority
            ("1111111100000000", 4),  # top half
        ],
    )
    @pytest.mark.medium
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs import tools as generators

        template = generators.home_row(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_home_row(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    @pytest.mark.medium
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs import tools as generators

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = generators.home_row(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_home_row(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_five_inputs_sample(self) -> None:
        """A sample of dense five-input tables, past the removed n <= 2 cap."""

        from esolangs import tools as generators

        n = 5
        rng = random.Random(0)
        for _ in range(5):
            table = "".join(rng.choice("01") for _ in range(2**n))
            template = generators.home_row(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_home_row(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has input runs, not hardcoded bits."""
        from esolangs import tools as generators

        template = generators.home_row("0110")
        assert "{X" not in template
        # each packing line opens with its two-character run
        assert "a$lsffffaafla$lsffffafl" in template

    def test_each_input_embedded_once(self) -> None:

        from esolangs import tools as generators
        from esolangs.tools.helpers import runs
        from esolangs.tools.home_row import HOME_ROW_PAIR

        template = generators.home_row("0110")
        # ``runs`` refuses a stray ``$``, so two spans is exactly two embeds
        assert len(runs(template, "$", (HOME_ROW_PAIR,) * 2)) == 2
        assert "{C0}" not in template
        assert "{C1}" not in template

    def test_rows_that_agree_with_the_last_share_its_leaf(self) -> None:
        """Only the rows before the table's trailing run get a guarded leaf."""
        from esolangs import tools as generators

        setup = "aaaaaalsffaaaaaaaaffflfa$lsffffaafla$lsffffafl"
        assert generators.home_row("0111") == setup + "fffflflfflk;lffffak"
        assert generators.home_row("0110") == setup + (
            "fffflsflfflk;lfflsflfflak;lfflflfflak;lffffk"
        )

    def test_the_constructed_lengths_are_stable_over_three_inputs(self) -> None:
        """Total emitted bytes over every three-input table.

        49378 while every leaf re-raised a flag, fanned the index into a
        working copy and restored it; 37410 once a leaf only decrements and
        steps; 34521 once the rows agreeing with the last share its leaf.
        """
        from esolangs import tools as generators

        tables = (format(v, "08b") for v in range(256))
        assert sum(len(generators.home_row(t)) for t in tables) == 34521
