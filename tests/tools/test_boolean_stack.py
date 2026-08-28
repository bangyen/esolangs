"""Unit tests for the stack-based boolean generators.

Covers the generators in :mod:`esolangs.tools.boolean.stack`: Grapheme,
Forþ, Modulous, BFStack, and Unsquare.
"""

import pytest

from esolangs.tools import boolean
from esolangs.tools.boolean.helpers import permute_truth_table
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
        """More inputs mean more tree functions, and every input is read."""
        # Parity folds nothing under any order, so it spends the full tree.
        parity = "".join(str(bin(row).count("1") % 2) for row in range(32))
        program = boolean.forth(parity)
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

        Which subtrees are constant depends on the order the tree splits
        in, and the order is chosen per table: ``00001111`` depends on the
        first input alone and ``01010101`` on the last, so each collapses to
        the two root children under the order that tests its input first.
        A stack-ordered tree could only fold the second.

        Parity is what folds under no order at all, so it is the witness
        that the fold is doing work rather than the search hiding it.
        """
        assert boolean.forth("1" * 8).count("{") == 2
        assert boolean.forth("01" * 4).count("{") == 2
        assert boolean.forth("0" * 4 + "1" * 4).count("{") == 2
        parity = "".join(str(bin(row).count("1") % 2) for row in range(8))
        assert boolean.forth(parity).count("{") == 2 ** (3 + 1) - 2

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

    def test_reordering_only_shrinks(self) -> None:
        """No table comes out longer than the stack-ordered program.

        The natural order here is the *reversal* -- ``;`` pops, so the tree
        has always tested the last input at the root -- and it is tried
        first with ties keeping it.  Pinning against that build is what
        proves the search cannot churn an emission it does not shorten.
        """
        from esolangs.tools.boolean.stack import _forth_ordered

        natural = (2, 1, 0)
        improved = 0
        for value in range(256):
            table = format(value, "08b")
            dispatched = len(boolean.forth(table))
            stack_ordered = len(
                _forth_ordered(permute_truth_table(table, natural), natural)
            )
            assert dispatched <= stack_ordered, table
            improved += dispatched < stack_ordered
        assert improved == 112

    def test_rotations_are_interleaved_with_the_reads(self) -> None:
        """Weaving the rotations into the reads reaches more arrangements.

        ``v`` and ``c`` touch only the top three cells, so rotating after
        all ``n`` reads can only permute the last three bits -- 6
        arrangements however wide the table.  Moving a bit while it is
        still near the top reaches three times as many at n == 4 and nine
        times as many at n == 5, which is what keeps the saving from
        collapsing as ``n`` grows.
        """
        from esolangs.tools.boolean.stack import _forth_stack_programs

        # The reachable *set* has a closed form, which is what pins the
        # search: after each read the new bit is on top, and the only
        # lasting freedom is how far it sinks -- 0, 1 or 2 places, one
        # independent choice per read past the first.
        for n in range(2, 7):
            assert len(_forth_stack_programs(n)) == 2 * 3 ** (n - 2)
        assert len(_forth_stack_programs(3)) == 6  # all of 3!
        assert len(_forth_stack_programs(4)) == 18  # of 24
        assert len(_forth_stack_programs(5)) == 54  # of 120

        # The reads themselves are still one per input, whatever the weave.
        for n in (3, 4, 5):
            for program in _forth_stack_programs(n).values():
                assert program.count(",68*-") == n

    def test_sinking_a_bit_deeper_than_the_stack_is_skipped(self) -> None:
        """A sink needs values below it, so early reads have fewer choices.

        The first read cannot sink at all and the second can sink at most
        one place, which is why the arrangement count is ``2 * 3**(n - 2)``
        rather than ``3**n``: the enumeration walks every combination and
        drops the ones that would sink a bit past the bottom of the stack.
        """
        from esolangs.tools.boolean.stack import _forth_sink_top, _forth_stack_programs

        assert len(_forth_stack_programs(1)) == 1  # nothing to rearrange
        assert len(_forth_stack_programs(2)) == 2  # the second bit may swap

        # The sink itself keeps everything but the moved bit in order.
        assert _forth_sink_top((0, 1, 2), 0) == (0, 1, 2)
        assert _forth_sink_top((0, 1, 2), 1) == (0, 2, 1)
        assert _forth_sink_top((0, 1, 2), 2) == (2, 0, 1)

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
