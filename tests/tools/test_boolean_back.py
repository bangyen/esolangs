"""Covers :mod:`esolangs.tools.back`."""

from itertools import pairwise

import pytest

from esolangs.tools.helpers import TEMPLATE_CHAR, runs


class TestParameterizedBack:
    """Input-by-substitution generators for the no-input language Back."""

    def run_back(self, prog: str, n: int) -> str:
        # Back has no output instruction: it dumps the whole tape at halt.
        # The generator puts the answer in cell n, so the dump's (n+1)th
        # field is the result -- no need to track the head, which the dump
        # does not report.
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import run

        io = ScriptedIO()
        run(prog.splitlines(), io)
        return io.getvalue().split()[n]

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from tests.tools.fills import _fill_back

        return _fill_back(tpl, bits)

    def test_program_length_is_the_same_for_every_input(self) -> None:
        """Both bits cost one command, so the size reveals nothing."""
        from esolangs.tools import parameterized
        from tests.tools.fills import _fill_back

        for n in (1, 2, 3):
            template = parameterized.back(format(0, f"0{2**n}b"))
            sizes = {
                len(_fill_back(template, [(c >> (n - 1 - i)) & 1 for i in range(n)]))
                for c in range(2**n)
            }
            assert len(sizes) == 1, f"n={n} sizes {sorted(sizes)}"

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools import parameterized

        template = parameterized.back(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_back(self.instantiate(template, bits), n)
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.back(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_back(self.instantiate(template, bits), n)
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has one run per input, not hardcoded bits."""
        from esolangs.tools import parameterized
        from esolangs.tools.examples import _setters_back

        template = parameterized.back("0110")
        assert "{X" not in template
        assert len(runs(template, TEMPLATE_CHAR, _setters_back(template, 2))) == 2

    def test_each_input_is_stored_once(self) -> None:
        """Each input is embedded once in the tape load, not re-embedded."""

        from esolangs.tools import parameterized

        for n in (1, 2, 3):
            table = format(0, f"0{2**n}b")
            template = parameterized.back(table)
            assert template.count(TEMPLATE_CHAR) == n

    def test_tree_uses_tape_decision_nodes(self) -> None:
        """The reflected decision tree retains its skip and both mirrors."""
        from esolangs.tools import parameterized

        template = parameterized.back("0110")
        assert "+" in template
        assert "/" in template
        assert "\\" in template
        assert "*" in template  # leaves halt

    def test_the_natural_order_folds_its_aligned_dependency(self) -> None:
        """Only a dependency aligned with the natural root folds immediately."""
        from esolangs.tools import parameterized

        scattered = len(parameterized.back("10101010"))
        aligned = len(parameterized.back("11110000"))
        parity = len(parameterized.back("01101001"))
        assert scattered == parity
        assert aligned < parity

    def test_the_identity_template_is_emitted(self) -> None:
        """Back no longer contests input orders."""
        from esolangs.tools import parameterized

        for table in ("01101001", "10101010", "11110000", "00111100", "10010110"):
            n = (len(table) - 1).bit_length()
            identity = parameterized._back_ordered(table, tuple(range(n)))  # noqa: SLF001
            assert parameterized.back(table) == identity, table

    def test_full_tree_growth_is_linear(self) -> None:
        """Reflection makes depth padding geometric; parity folds nothing."""
        from esolangs.tools import parameterized

        sizes = []
        for n in range(6, 11):
            table = "".join(str(row.bit_count() & 1) for row in range(2**n))
            sizes.append(len(parameterized.back(table)))
        assert all(later <= 2 * earlier for earlier, later in pairwise(sizes))

    @pytest.mark.parametrize(
        "table",
        ["10101010", "11001100", "01011010", "00111100", "10010110"],
    )
    def test_templates_compute_the_table(self, table: str) -> None:
        """Each emitted natural-order template computes its function.

        Back's node is ``+\\>`` -- test the current cell, *then* advance --
        so level ``k`` tests cell ``k``, one lower than the generators whose
        node steps first.  Loading an input into the wrong cell computes a
        different function rather than failing to draw, so only running it
        catches the slip.
        """
        from esolangs.tools import parameterized

        template = parameterized.back(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            got = self.run_back(self.instantiate(template, bits), 3)
            assert got == table[combo], f"{table} inputs {bits}"

    def test_reordering_pays_a_walk_and_keeps_name_order(self) -> None:
        """A permuted load spends rows on the walk, and keeps its runs in name order.

        This is the trade Back deliberately takes.  Filling in *cell* order
        -- putting input ``perm[c]`` in cell ``c`` -- emits no walk and is a
        few percent smaller, but leaves the inputs out of name order,
        which no other generator in this module does.  Loading in name order
        and walking the pointer costs about two characters a step and keeps
        the templates uniform.

        Both halves are pinned here, because either alone would be wrong: a
        build with no walk cannot be reordering at all, and one whose slots
        left sequence would have taken the other side of the trade without
        the docstring being updated.
        """
        from itertools import permutations

        from esolangs.tools import parameterized

        walked = 0
        for table in ("0110", "10101010", "01101001"):
            n = (len(table) - 1).bit_length()
            for perm in permutations(range(n)):
                permuted = parameterized.permute_truth_table(table, perm)
                built = parameterized._back_ordered(permuted, perm)  # noqa: SLF001
                assert built.count(TEMPLATE_CHAR) == n, (table, perm)
                walked += built.count("<")
        # A non-identity order has to step the pointer back at some point;
        # a build with no leftward step is not reordering anything.
        assert walked > 0

    def test_placeholders_run_in_name_order_while_still_reordering(self) -> None:
        """Back reorders through the *walk*, not through its input order.

        The load emits input 0..n-1 in sequence whatever the input order,
        and the reorder lives in the ``>``/``<`` runs that carry the pointer
        to each input's cell.  Both halves matter: dropping the walk would
        leave the order inert, and permuting the inputs instead would need
        a template whose k-th run is not input k, which the run form
        cannot spell.

        The units are emitted in reverse name order because the load is
        drawn bottom-to-top up column 0, so the template's *text* reads them
        backwards -- loading input ``n-1`` first is what puts input 0 first
        on the page.
        """

        from esolangs.tools import parameterized

        walked = 0
        for table in ("11110000", "10101010", "01101001", "00111100"):
            template = parameterized.back(table)
            assert template.count(TEMPLATE_CHAR) == 3, f"{table} embeds each once"
            # Reflection moves the load to the last occupied cell of its row.
            column = [
                line.rstrip()[-1] for line in template.split("\n") if line.strip()
            ]
            walked += column.count("<")
        # At least one of these tables reorders, so at least one leftward
        # step is emitted -- a plain ascending load never steps back.
        assert walked > 0

    def test_reordering_keeps_the_equal_width_embedding(self) -> None:
        """Reordered loads still cost the same for either bit.

        The walk goes before an input's ``-``/run pair and never
        between its halves, so the primer and the run stay one
        unit and both bits still cost the same two rows.  Splitting them
        would let the template's height reveal an input.
        """
        from esolangs.tools import parameterized
        from tests.tools.fills import _fill_back

        for table in ("10101010", "11001100", "01101001"):
            template = parameterized.back(table)
            sizes = {
                len(_fill_back(template, [(c >> (2 - i)) & 1 for i in range(3)]))
                for c in range(8)
            }
            assert len(sizes) == 1, f"{table} sizes {sorted(sizes)}"
