"""Unit tests for the stack-based boolean generators.

Covers the generators in :mod:`esolangs.tools.boolean.stack`: Grapheme,
Forþ, Modulous, BFStack, and Unsquare.
"""

import pytest

from esolangs.tools import boolean
from tests.tools.boolean_runners import (
    run_bfstack,
    run_forth,
    run_grapheme,
    run_modulous,
)


class TestGrapheme:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity
            ("10", 1),  # NOT
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.grapheme(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_grapheme(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.grapheme(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_grapheme(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_bad_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.grapheme("011")

    def test_non_binary_rejected(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.grapheme("02")


class TestForth:
    def test_program_structure(self) -> None:
        """The program defines one function per surviving node, reading n bits.

        AND's zero-side subtree is constant, so it folds to a leaf: four
        nodes rather than the full six.
        """
        program = boolean.forth("0001")
        assert program.endswith("1+;.")
        assert program.count("{") == program.count("}") == 4
        assert program.count(",68*-") == 2  # read and normalize 2 inputs

    def test_leaf_results_are_the_byte(self) -> None:
        """Each leaf pushes 48 + its table entry."""
        program = boolean.forth("0001")
        assert "3F*3+" in program  # '0' leaves push 48 = 3*15+3
        assert "3F*4+" in program  # the '1' leaf pushes 49 = 3*15+4

    def test_scales(self) -> None:
        """More inputs mean more tree functions."""
        program = boolean.forth("0" * 16 + "1" * 16)
        assert program.count("{") == 2 ** (5 + 1) - 2
        assert program.count(",68*-") == 5

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_truth_table(self, n: int) -> None:
        """Every table up to three inputs produces the right result.

        The other Forþ tests assert program structure only; this runs the
        program, which is what pins the fold's behaviour rather than its
        shape.
        """
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.forth(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_forth(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_constant_subtrees_fold(self) -> None:
        """A constant subtree answers in place and drops its descendants.

        Forþ stores each scope in a dict keyed by the number pushed before
        ``{`` and calls it with a default, so an unemitted node simply
        never exists -- folding is skip-emission with no renumbering.

        The tree splits least-significant bit first (see ``_forth_combo``),
        so its subtrees are strides rather than contiguous runs: a table
        like ``00001111`` is constant over an axis this tree never splits
        on and keeps every node, while ``01010101`` collapses to the two
        root children.
        """
        assert boolean.forth("1" * 8).count("{") == 2
        assert boolean.forth("01" * 4).count("{") == 2
        assert boolean.forth("0" * 4 + "1" * 4).count("{") == 2 ** (3 + 1) - 2

    def test_folded_subtree_leaves_no_orphans(self) -> None:
        """Folding drops the whole subtree, not just the two children.

        A grandchild below a folded node is just as unreachable; emitting
        it would be dead code the program never calls, so the node count
        must fall to exactly the surviving frontier.
        """
        from esolangs.tools.boolean.stack import _forth_const

        program = boolean.forth("1" * 8)
        for m in range(3, 15):  # every node below the two root children
            assert _forth_const(m) + "{" not in program

    def test_const_large(self) -> None:
        """Constants above 225 need multiple base-15 digits."""
        from esolangs.tools.boolean.stack import _forth_const

        assert _forth_const(0) == "0"
        assert len(_forth_const(300)) > len(_forth_const(48))


class TestModulous:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.modulous(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_modulous(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function reads one input then branches on it."""
        assert boolean.modulous("10").startswith("[INP INT]")
        assert "[JMP F 2 IF 0]" in boolean.modulous("10")

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice pushes its answer instead of branching further.

        Modulous branches on the stack top, which is the *last* input, so
        its subtrees are strided rather than contiguous runs -- a table
        like ``11110000`` has no constant subtree under that split and
        folds nothing.  A table that agrees outright still collapses to a
        single push, which is where the saving comes from.
        """
        leaves = "[PRT INT]"
        assert boolean.modulous("11111111").count(leaves) == 1
        assert boolean.modulous("10010110").count(leaves) == 8


class TestBfstack:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1000000000000000", 4),  # AND4
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.bfstack(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bfstack(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_encode_decode_structure(self) -> None:
        """The program encodes the inputs then tests the zero rows."""
        program = boolean.bfstack("0110")
        assert program.startswith(">>+,")  # result cell, accumulator, first input
        assert program.count(",") == 2  # one read per input
        assert program.endswith("+" * 48 + ".")  # print 48 + result


class TestUnsquare:
    def test_program_shape(self) -> None:
        """The program reads n inputs and prints once."""
        program = boolean.unsquare("0110")
        assert program.startswith("iA>-<P" * 2)
        assert program.count("iA>-<P") == 2  # one read per input
        assert program.endswith("o")

    def test_decision_tree(self) -> None:
        """Each internal node branches on a bit with the flip primitive."""
        program = boolean.unsquare("0110")
        assert "x->IA<" in program  # the stack-clean flip
        assert program.count("x>") >= 3  # one guard per branch

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice prints its answer instead of branching further.

        Like Modulous, Unsquare branches on the last input first, so its
        subtrees are strided and a table such as ``11110000`` folds
        nothing; a table that agrees outright collapses to one leaf.
        """
        assert boolean.unsquare("11111111").count("P") == 3 + 1  # 3 reads, 1 leaf
        assert boolean.unsquare("10010110").count("P") == 3 + 8

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.unsquare("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.unsquare("02")
