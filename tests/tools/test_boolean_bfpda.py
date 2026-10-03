"""bfpda generator tests."""

import pytest

from tests.tools.fills import _run_form


class TestParameterizedBfpda:
    """Input-by-substitution boolean generator for the no-input language BF-PDA."""

    def run_bfpda(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bf_pda import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from tests.tools.fills import _fill_bfpda

        return _fill_bfpda(tpl, bits)

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """The setter is four characters whichever bit it carries."""
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

        template = generators.bfpda(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_bfpda(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    @pytest.mark.medium
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs import tools as generators

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = generators.bfpda(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_bfpda(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has input runs, not hardcoded bits."""
        from esolangs import tools as generators

        template = generators.bfpda("0110")
        assert "{X" not in template
        # The first marker's ``<`` is dropped: ``@`` pushes a 1 onto the empty stack.
        assert template.startswith("@<$<@<$")

    def test_program_structure(self) -> None:
        """Each input is embedded once (pre-loaded), not re-embedded per node."""

        from esolangs import tools as generators
        from esolangs.tools.bfpda import BFPDA_PAIR
        from esolangs.tools.helpers import runs

        template = generators.bfpda("0110")
        # ``runs`` refuses a stray ``$``, so two spans is exactly two embeds
        assert runs(template, "$", (BFPDA_PAIR,) * 2) == [(2, 3), (6, 7)]
        assert "{C0}" not in template  # the marker is a constant, not a complement
        assert "{C1}" not in template

    def test_leaf_leaves_the_stack_empty(self) -> None:
        """A zero drains and prints the empty stack; a one prints the bottom marker.

        Both arms of a node end on an empty stack, so the ``]`` closing
        each exits without a pushed zero, and nothing is left to pop.
        """
        from esolangs import tools as generators

        assert generators.bfpda("10") == "@<$[>>.]>[>@.>]"  # NOT
        assert generators.bfpda("0110") == (
            "@<$<@<$[>>[>>.]>[>@.>]]>[>[>>@.>]>[>.]]"  # XOR
        )

    def test_the_constructed_lengths_are_stable_over_three_inputs(self) -> None:
        """Total emitted bytes over every three-input table.

        24127 while each arm pushed a zero to break its loop and popped it
        after, and each leaf pushed its answer; 17578 once the arms end on
        the empty stack a leaf leaves behind; 16042 with fresh-cell setters.
        """
        from esolangs import tools as generators

        total = sum(len(generators.bfpda(format(v, "08b"))) for v in range(256))
        assert total == 16042
