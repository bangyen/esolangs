"""Unit tests for the single-language boolean generators.

Covers the generators in :mod:`esolangs.tools.boolean.other` and
:mod:`esolangs.tools.boolean.ztoalc_l`, plus the shared validation and
helper edge paths exercised across generator modules.
"""

import pytest

from esolangs.interpreters.io import IO
from esolangs.tools import boolean, laserfuck_layout
from tests.tools.boolean_runners import (
    run_between,
    run_clockwise,
    run_container,
    run_flowchart,
    run_forbin_boolean,
    run_laserfuck,
    run_myscript,
    run_nevermind,
    run_suptiftam,
    run_taglate,
    run_ztoalc,
)


class TestSuptiftam:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity
            ("10", 1),  # NOT
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1000000000000000", 4),  # AND4
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.suptiftam(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_suptiftam(program, bits)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_minterm_structure(self) -> None:
        """The program reads one row per input and sums the minterms."""
        program = boolean.suptiftam("0001")
        assert program.startswith("sum=0\np=1\nfd mulStep :x")
        assert program.count("%-[read]22%") == 2  # one normalized read per input
        assert program.count("down(:read:)") == 2
        assert program.endswith("term=sum")

    def test_constant_tables_skip_the_minterms(self) -> None:
        """A constant-zero table has no minterm rows at all."""
        program = boolean.suptiftam("0000")
        assert "mulStep(:p:)if(p)" not in program

    def test_a_dense_table_is_summed_over_its_zeros(self) -> None:
        """More ones than zeros costs less summed the other way and inverted.

        An all-ones table is the interesting case: it complements to no
        minterms at all, leaving ``sum`` at 0, and the inversion turns that
        into the 1 it should print -- so it needs no special-casing the way
        a gate-network generator's constant table does.
        """
        assert "term=%-[1]sum%" in boolean.suptiftam("1111")
        assert "mulStep(:p:)if(p)" not in boolean.suptiftam("1111")
        assert "term=sum" in boolean.suptiftam("0001")  # sparse: drawn directly
        # and both still compute their table
        for table in ("1111", "11111110"):
            n = len(table).bit_length() - 1
            program = boolean.suptiftam(table)
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_suptiftam(program, bits) == table[combo]

    def test_bit_names_extend_beyond_the_alphabet(self) -> None:
        """Identifiers are alphabetical, so past 'z' the names grow a prefix."""
        from esolangs.tools.boolean.other import _suptiftam_bit

        assert _suptiftam_bit(0) == "b"
        assert _suptiftam_bit(24) == "z"
        assert _suptiftam_bit(25) == "bb"
        assert _suptiftam_bit(49) == "bz"
        assert _suptiftam_bit(50) == "bbb"

    def test_rejects_bad_table(self) -> None:
        with pytest.raises(ValueError, match="entries"):
            boolean.suptiftam("011")

    def test_rejects_non_binary(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.suptiftam("02")


class TestForbinBoolean:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.forbin_boolean(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_forbin_boolean(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_uses_the_lsb_of_each_input(self) -> None:
        """Each input is read as 8 bits and only the LSB drives the tree."""
        program = boolean.forbin_boolean("01")
        # one 8-variable read, then a decision tree that prints '1' for bit 1
        assert "i0_0,i0_1,i0_2,i0_3,i0_4,i0_5,i0_6,i0_7 = (in 0);" in program

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice returns its answer instead of branching further."""
        assert boolean.forbin_boolean("11111111").count("return 0;") == 1
        assert boolean.forbin_boolean("11110000").count("return 0;") == 2
        assert boolean.forbin_boolean("10010110").count("return 0;") == 8

    def test_rejects_bad_table(self) -> None:
        with pytest.raises(ValueError, match="entries"):
            boolean.forbin_boolean("011")

    def test_rejects_non_binary(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.forbin_boolean("02")


class TestFlowchart:
    """The Flowchart boolean generator (works for arbitrary n)."""

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity
            ("10", 1),  # NOT
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0111", 2),  # OR
            ("0110", 2),  # XOR
            ("1110", 2),  # NAND
            ("01101001", 3),  # XOR3
            ("11111110", 3),  # NAND3
            ("0110100110010110", 4),  # XOR4
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result.

        The read count is checked alongside the answer: a folded leaf
        carries the reads of the levels it skipped, so a heavily folding
        table (the constants, AND4) must still consume all ``n`` inputs.
        Without those the drawing would be correct and the program would
        still leave the caller's remaining bits on the stream.
        """
        import contextlib

        from esolangs.interpreters.grid_based.flowchart import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import run_until_halt_or_cycle

        program = boolean.flowchart(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_flowchart(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"
        io = ScriptedIO("0\n" * (n + 4))
        with contextlib.suppress(Exception, SystemExit):
            run_until_halt_or_cycle(_Machine(program.splitlines(), io))
        assert io.position() == n, (
            f"table {table} consumed {io.position()} inputs, expected {n}"
        )

    def test_tree_depth_matches_input_count(self) -> None:
        """One ``/ /`` read node sits on each path from entry to a leaf."""
        program = boolean.flowchart("0110100110010110")
        assert program.count("< >") == 15  # 2**4 - 1 internal nodes
        assert program.count("(( ))") == 16  # 2**4 leaves

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice is one leaf, and takes one column band.

        The leaves keep their pitch but are handed out as the walk reaches
        them, so a folded subtree narrows the drawing rather than leaving a
        gap where its rows would have been.
        """
        assert boolean.flowchart("11111111").count("(( ))") == 1
        assert boolean.flowchart("11110000").count("(( ))") == 2
        assert boolean.flowchart("10010110").count("(( ))") == 8  # no fold
        # a constant table needs no switch at all
        assert boolean.flowchart("11111111").count("< >") == 0
        assert boolean.flowchart("11110000").count("< >") == 1

    @pytest.mark.parametrize(
        "table", ["01", "0001", "01101001", "0110100110010110", "1000000000000000"]
    )
    def test_vertical_rails_meet_node_middles(self, table: str) -> None:
        """Every ``│`` connects to the middle of the node above and below it.

        The wiki asks that "vertical paths connecting into a node are expected
        to connect to the middle of the node", and all three of its worked
        examples honour it.  The interpreter is deliberately lenient about
        this -- it enters a node through any cell of its box, which is why an
        earlier, misdrawn version of this tree still computed the right table
        -- so nothing else would catch the drawing drifting off centre.

        The rule is about vertical rails only: the Kolakoski example's top row
        chains nodes horizontally (``( )─[ }─\\[ ]/``), attaching at their end
        cells rather than their middles.
        """
        from esolangs.interpreters.grid_based.flowchart import _Machine

        machine = _Machine(boolean.flowchart(table).splitlines(), IO())
        for row, line in enumerate(machine.grid):
            for col, char in enumerate(line):
                if char != "│":
                    continue
                for neighbour in (row - 1, row + 1):
                    node = machine.nodes.get((neighbour, col))
                    if node is None:
                        continue
                    spelling, start = node
                    middle = start + len(spelling) // 2
                    assert col == middle, (
                        f"rail at ({col}, {row}) meets {spelling!r} at column {col}, "
                        f"but its middle is column {middle}"
                    )

    def test_each_run_reads_exactly_n_bits(self) -> None:
        """The drawn read nodes outnumber the reads any one run performs.

        A depth-4 tree draws 15 ``/ /`` nodes, but a run walks a single
        root-to-leaf path and consumes exactly 4 bits, so the duplication is
        spatial rather than a bit being read more than once (see the
        generator's docstring on why the parameterized once-only embedding
        rule does not apply to an input-reading generator).
        """
        program = boolean.flowchart("0110100110010110")
        assert program.count("/ /") == 15

        consumed = 0

        class _CountingIO(IO):
            def input_str(self, _prompt: str = "Input: ") -> str:
                nonlocal consumed
                consumed += 1
                return "1"

            def print_str(self, text: str) -> None:
                pass

        from esolangs.interpreters.grid_based.flowchart import run as fc_run

        fc_run(program.splitlines(), _CountingIO())
        assert consumed == 4

    def test_rejects_a_malformed_table(self) -> None:
        """A table whose length is not a power of two is rejected."""
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.flowchart("011")


class TestBetween:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.between(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_between(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_program_structure(self) -> None:
        """One declare/read/normalize triplet per input, one branch per node."""
        program = boolean.between("0110")
        lines = program.splitlines()
        assert lines[:3] == ["'0'v.", "[0]i.", "[0]s|[0]c.|"]
        # XOR has no constant slice above a single row, so nothing folds and
        # every combination keeps its own leaf.
        assert lines.count(".x.") == 4

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice becomes one leaf instead of branching further.

        The jump addresses come from a second walk over the tree, so this
        also covers the two walks agreeing: a leaf count that matched while
        the addresses did not would still run the wrong branch, which
        :meth:`test_truth_table` would catch.
        """
        assert boolean.between("11111111").count(".x.") == 1
        assert boolean.between("11110000").count(".x.") == 2
        assert boolean.between("10010110").count(".x.") == 8  # parity: no fold

    def test_mismatched_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.between("011")

    def test_bad_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.between("0123")


class TestNevermind:
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
        program = boolean.nevermind(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_nevermind(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function reads one input and branches on it."""
        program = boolean.nevermind("10")
        assert program.startswith("input,?")
        assert "if,$a,==,0" in program
        assert program.count("endif") == 2

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice prints its answer instead of branching further."""
        assert boolean.nevermind("11111111").count("print,") == 1
        assert boolean.nevermind("11110000").count("print,") == 2
        assert boolean.nevermind("10010110").count("print,") == 8  # no fold


class TestContainer:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # NOT
            ("10", 1),
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.container(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_container(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """The program reads n inputs and keeps one survivor per row."""
        program = boolean.container("0110")
        assert program.startswith("T:\n+1 T>=T")
        assert ":" in program.splitlines()[:4]  # the empty-named reader
        assert program.count("S") >= 4  # a survivor per row
        assert program.count("PRINT:") == 1

    def test_dense_tables_evaluate_the_complement(self) -> None:
        """A dense table is summed from its zero rows and inverted.

        ``OUT`` costs one ``+1 S{row}>=Gout`` line per row the table sends
        to 1, so before this the length rose with the ones-count all the way
        to the all-ones table.  Now it peaks at half and falls back
        symmetrically, which is the signature of taking whichever row-set is
        smaller.
        """
        lengths = [len(boolean.container("1" * k + "0" * (8 - k))) for k in range(9)]
        assert lengths[4] == max(lengths)  # four ones is the worst case
        assert lengths == lengths[::-1]  # and the curve is symmetric

    @pytest.mark.parametrize("table", ["11111110", "11111111", "1110", "0111"])
    def test_complemented_tables_still_compute(self, table: str) -> None:
        """The inverted form answers the original table.

        It starts ``OUT`` at 49 and subtracts one per surviving zero row, so
        the printed byte is ``49 - S``; the container clamp at zero never
        bites, since the value stays at 48 or 49.
        """
        n = (len(table) - 1).bit_length()
        program = boolean.container(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_container(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.container("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.container("02")


class TestZtoalc:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("00000001", 3),  # AND3
            ("01101001", 3),  # XOR3
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.ztoalc_l_boolean(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_ztoalc(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to two inputs produces the right result."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.ztoalc_l_boolean(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                assert run_ztoalc(program, [str(b) for b in bits]) == table[combo]

    def test_structure(self) -> None:
        """The program rides a Collatz descent with jumps and prints."""
        program = boolean.ztoalc_l_boolean("0110")
        lines = program.splitlines()
        assert lines[0].strip().isdigit()  # line 1 is the starting value
        assert any("jump" in line for line in lines)
        assert any(line.strip().startswith("print") for line in lines)

    def test_xor4_linear_fallback(self) -> None:
        """Dense symmetric tables fall back to a huge linear program."""
        program = boolean.ztoalc_l_boolean("0110100110010110")  # XOR4 = parity
        assert len(program.splitlines()) > 100_000  # linear, not the small tree
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            got = run_ztoalc(program, [str(b) for b in bits])
            assert got == str(int("0110100110010110"[combo])), f"inputs {bits}"

    def test_dense_non_symmetric_places_under_a_reordered_tree(self) -> None:
        """A table the identity order cannot place is rendered by another order.

        This table used to be refused: its tree found no collision-free
        placement and it is not popcount-symmetric, so the linear fallback
        could not help either.  Choosing the input split order gives the
        search a differently-shaped tree to place, and one of the orders
        fits -- the same effect that shrinks factor's unrenderable set.
        """
        from esolangs.tools.boolean.ztoalc_l import _ztoalc_ordered

        table = "1010001000011000"
        assert not _ztoalc_ordered(table, (0, 1, 2, 3)), (
            "the identity order should still fail to place this table"
        )
        program = boolean.ztoalc_l_boolean(table)
        for combo in range(16):
            bits = [str((combo >> (3 - i)) & 1) for i in range(4)]
            assert run_ztoalc(program, bits) == table[combo], f"inputs {bits}"

    def test_wrong_length_rejected(self) -> None:
        """A truth table of the wrong length is malformed."""
        with pytest.raises(ValueError, match="entries"):
            boolean.ztoalc_l_boolean("011")

    def test_invalid_chars_rejected(self) -> None:
        """A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.ztoalc_l_boolean("02")


class TestClockwise:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),
            ("10", 1),
            ("00", 1),
            ("11", 1),
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("00000001", 3),  # AND3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination prints the result as an ASCII digit."""
        program = boolean.clockwise(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_clockwise(program, bits)
            assert got == table[combo], f"inputs {bits}"

    def test_ring_starts_at_origin(self) -> None:
        """The program is a closed ring whose pointer starts at (0, 0)."""
        program = boolean.clockwise("0110")
        lines = program.splitlines()
        assert lines[0][0] == " "
        assert run_clockwise(program, ["1", "0"]) == "1"  # XOR(1, 0)

    @pytest.mark.parametrize(("table", "n"), [("0001", 2), ("01101001", 3)])
    def test_tree_sits_against_the_left_edge(self, table: str, n: int) -> None:
        """No column is dead: the spine starts as far left as it can.

        The tree's turns are relative, so its absolute column never
        matters; a spine further right is pure padding.  It only has to
        clear the ``2**(n + 1) - 1`` columns its leftward branches span,
        leaving column 0 for the closing corner.
        """
        program = boolean.clockwise(table)
        rows = program.splitlines()
        width = max(len(row) for row in rows)
        grid = [row.ljust(width) for row in rows]
        dead = [x for x in range(width) if all(row[x] == " " for row in grid)]
        assert not dead, f"dead columns {dead}"
        assert width == 2 ** (n + 1) + 1

    def test_constant_subtrees_narrow_the_ring(self) -> None:
        """A folded subtree spends no displacement, so the grid narrows.

        Width grows as ``2 ** (n + 1)``, and a node only displaces its
        one-branch when it actually branches -- so a table whose subtrees
        collapse needs fewer columns.  A scattered table folds nothing and
        must be unchanged.
        """
        scattered = boolean.clockwise("10010110")
        for table in ("11111111", "11110000"):
            folded = boolean.clockwise(table)
            assert len(folded) < len(scattered), table
        assert len(boolean.clockwise("11001100")) < len(scattered)

    def test_folded_column_still_reads_every_input(self) -> None:
        """A folded column keeps the reads it skipped branching on.

        Clockwise reads *inside* the tree -- seven ``.`` per level -- so a
        folded leaf that dropped them would consume fewer inputs than an
        unfolded one and desync a caller feeding several programs from one
        stream.  Every column therefore carries ``7 * n`` reads.
        """
        for table in ("11111111", "11110000", "11001100"):
            n = len(table).bit_length() - 1
            program = boolean.clockwise(table)
            rows = program.splitlines()
            width = max(len(row) for row in rows)
            grid = [row.ljust(width) for row in rows]
            columns = [sum(1 for row in grid if row[x] == ".") for x in range(width)]
            # the deepest column reads every input; none reads more
            assert max(columns) <= 7 * n, table
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_clockwise(program, bits) == table[combo], (table, bits)

    def test_folding_never_grows_the_program(self) -> None:
        """The hoist floor: narrowing must not cost more than it saves.

        Hoisting the root's seven reads onto row 0 retires seven rows, but
        needs seven free columns left of the root.  At ``n == 2`` a tree
        folded to seven columns loses that and comes out *larger* than the
        unfolded program, so the width never narrows below what the hoist
        needs.
        """
        for n in (1, 2, 3):
            # the alternating table folds nothing at any level, so it is the
            # full-size program every other table must come in at or under
            unfolded = len(boolean.clockwise("10" * (2 ** (n - 1))))
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                assert len(boolean.clockwise(table)) <= unfolded, table


class TestTaglate:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("00", 1),
            ("01", 1),
            ("10", 1),
            ("11", 1),
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("1110", 2),  # NAND
            ("00000001", 3),  # majority
            ("0000000000000001", 4),  # 4-AND
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.taglate(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            # Odd n > 1 uses a ghost digit (fake zero first input)
            inputs = (
                ["0"] + [str(b) for b in bits]
                if n % 2 == 1 and n > 1
                else [str(b) for b in bits]
            )
            got = run_taglate(program, inputs)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_all_two_input_tables(self) -> None:
        """Every two-input truth table produces the right result."""
        for table in range(16):
            tt = format(table, "04b")
            for combo in range(4):
                bits = [(combo >> 1) & 1, combo & 1]
                got = run_taglate(boolean.taglate(tt), [str(b) for b in bits])
                assert got == tt[combo], f"{tt} inputs {bits}"

    def test_all_three_input_tables(self) -> None:
        """Every three-input truth table produces the right result."""
        failures = 0
        for table in range(256):
            tt = format(table, "08b")
            program = boolean.taglate(tt)
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                inputs = ["0"] + [str(b) for b in bits]  # ghost digit
                got = run_taglate(program, inputs)
                if got != tt[combo]:
                    failures += 1
                    if failures <= 3:
                        print(
                            f"  FAIL {tt} inputs {bits}: "
                            f"got {got!r} expected {tt[combo]!r}"
                        )
        assert failures == 0, f"{failures} failures out of 2048 combos"

    def test_tables_ignoring_inputs_shrink(self) -> None:
        """A table that ignores inputs is emitted as the smaller table.

        Taglate's cost is almost all fixed overhead scaled by the input
        count -- the seed alone is ``2**(n_eff + 2)`` cells -- so dropping
        an input drops a whole tier.  Every table of a given ``n`` used to
        be the same length; now the ones that depend on fewer inputs are
        dramatically shorter.
        """
        full = len(boolean.taglate("10010110"))  # depends on all three
        for table in ("11110000", "11001100", "10101010", "00000000"):
            assert len(boolean.taglate(table)) < full // 10, table

    def test_reduced_programs_still_read_every_input(self) -> None:
        """A reduced program consumes the inputs it no longer uses.

        The ignored ones are read and discarded (``h`` appends to the
        queue's tail, ``e`` once per queued cell rotates it to the front,
        ``f`` drops it), so the queue is left exactly as it was and a caller
        feeding several programs from one stream stays in sync.  Odd ``n``
        above 1 also takes a leading ghost digit, which is one more read.
        """
        for n in (1, 2, 3, 4):
            expected = n + (1 if n % 2 == 1 and n > 1 else 0)
            for table in (
                "1" * 2**n,
                "1" * 2 ** (n - 1) + "0" * 2 ** (n - 1),
                ("10" * 2**n)[: 2**n],
            ):
                program = boolean.taglate(table)
                assert program.count("h") == expected, (n, table)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("1111111100000000", 4),  # depends on input 0
            ("1111000011110000", 4),  # input 1
            ("1010101010101010", 4),  # input 3
            ("1111111111111111", 4),  # none at all
        ],
    )
    def test_reduced_tables_compute_past_three_inputs(self, table: str, n: int) -> None:
        """The reduction stays correct deeper than the exhaustive sweep."""
        program = boolean.taglate(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            ghost = ["0"] if n % 2 == 1 and n > 1 else []
            got = run_taglate(program, ghost + [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"

    def test_wrong_length_truth_table_rejected(self) -> None:
        """A truth table of the wrong length is malformed."""
        with pytest.raises(ValueError, match="entries"):
            boolean.taglate("011")

    def test_invalid_truth_table_chars_rejected(self) -> None:
        """A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.taglate("0120")


class TestThreeX:
    def test_identity_program_structure(self) -> None:
        """The 01 table reads a bit and stores it before printing."""
        program = boolean.three_x("01")
        assert program.startswith("?")
        assert program.endswith("!")

    def test_wrong_length_truth_table_rejected(self) -> None:
        """A truth table of the wrong length is malformed."""
        with pytest.raises(ValueError, match="entries"):
            boolean.three_x("011")

    def test_invalid_truth_table_chars_rejected(self) -> None:
        """A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.three_x("02")

    def test_uses_input_variables(self) -> None:
        """Each input bit is read into a distinct variable."""
        program = boolean.three_x("0001")
        assert program.count("?") == 2
        assert "333x" in program  # the constant-0 encoding appears
        assert "3333x3x" in program  # the constant-1 encoding appears

    def test_constant_table_has_no_override_blocks(self) -> None:
        """When every row equals the default, no ( ... ) guards are emitted."""
        assert "(" not in boolean.three_x("0" * 4)
        assert "(" not in boolean.three_x("1" * 4)

    def test_majority_default_handles_zero_row(self) -> None:
        """A zero row differing from a majority-1 default still overrides it."""
        program = boolean.three_x("0110")  # XOR: two 1s, two 0s
        assert program.startswith("?")
        assert program.endswith("!")
        assert "(" in program  # the zero row needs an override block

    def test_scales_to_more_inputs(self) -> None:
        """The generator handles n beyond the built-in constants."""
        program = boolean.three_x("0" * (2**7))
        assert program.count("?") == 7

    def test_shared_tree_prefix_sharing(self) -> None:
        """Differing combos share prefix guards instead of repeating them."""
        # top-half n=5: 16 zero-rows all share MSB=0.  A full tree has
        # 31 guard nodes; independent chains would emit 16 * 5 = 80.
        program = boolean.three_x("0" * 16 + "1" * 16)
        assert program.count("(") < 40

    def test_digit_constant_encodings(self) -> None:
        """The base-3 digit seeds are the closed-form minimal programs."""
        from esolangs.tools.boolean import other

        assert other._const(0) == "333x"  # noqa: SLF001
        assert other._const(1) == "3333x3x"  # noqa: SLF001
        assert other._const(2) == "3333x3x3333x3x3x"  # noqa: SLF001

    def test_base_three_digits_accumulate(self) -> None:
        """Each base-3 digit past the first appends the 3v+d affine step."""
        from esolangs.tools.boolean import other

        # 12 is "110" in base 3: seed 1, then d=1, then d=0.  Each transform
        # adds exactly one `#` (the swap before the `x`), and no seed has one.
        twelve = other._const(12)  # noqa: SLF001
        assert twelve.startswith(other._const(1))  # noqa: SLF001
        assert twelve.count("#") == 2

    def test_formula_scales_logarithmically(self) -> None:
        """The closed form grows with the digit count, not the value."""
        from esolangs.tools.boolean import other

        small, large = other._const(100), other._const(1_000_000)  # noqa: SLF001
        assert len(small) < 120  # 100 is "10201": 5 digits
        assert len(large) < 350  # 1_000_000 is 13 base-3 digits
        assert len(large) < len(small) * 4


class TestLaserFuck:
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
            ("00000001", 3),  # AND3
            ("1111111100000000", 4),  # top half
            ("0110100110010110", 4),  # XOR4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.laserfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            for heading in range(4):
                got = run_laserfuck(program, [str(b) for b in bits], heading)
                assert got == str(int(table[combo])), f"inputs {bits} heading {heading}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.laserfuck(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_laserfuck(program, [str(b) for b in bits], 3)
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_funnel_is_heading_independent(self) -> None:
        """Every initial heading reaches the tree on the top row."""
        program = boolean.laserfuck("0110")
        for heading in range(4):
            assert run_laserfuck(program, ["1", "0"], heading) == "1"

    def test_decimal_output_mode(self) -> None:
        """No ``\\xff`` marker, so the tape dumps as numbers, not bytes.

        Byte mode would print the answer as ``chr(result)``, which is why
        the leaves used to add 48 to reach ASCII ``'0'``/``'1'``.  In decimal
        mode the leaf writes the result itself.
        """
        program = boolean.laserfuck("10")
        assert program.splitlines()[0][0] != "\u00ff"
        assert "\u00ff" not in program

    def test_prints_only_the_answer(self) -> None:
        """The dump is exactly the result: no input cells, no separators.

        The input cells are driven negative by the leaf, and ``dump`` skips
        negative cells, so nothing but the answer survives.
        """
        program = boolean.laserfuck("0001")  # AND2
        for bits, want in (([0, 1], "0"), ([1, 1], "1")):
            got = run_laserfuck(program, [str(b) for b in bits], 3)
            assert got == want, f"inputs {bits}"

    def test_loop_free_tree(self) -> None:
        """The decision tree branches with #, ) and a turning mirror."""
        program = boolean.laserfuck("0110")
        assert "#" in program
        assert ")" in program
        # the tree is mirrored, so a one-branch turns on '/' rather than '\\'
        assert "/" in program

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.laserfuck("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.laserfuck("02")

    @pytest.mark.parametrize(
        ("table", "n", "width"),
        [
            # The tree is never folded and grows six columns per node, so the
            # narrowest width a table can honour rises with its input count:
            # roughly 19, 34, and 63 columns for one, two, and three inputs.
            ("01", 1, 20),
            ("01", 1, 40),
            ("10", 1, 80),
            ("0110", 2, 34),
            ("0110", 2, 80),
            ("1000", 2, 120),
            ("01101001", 3, 63),
            ("01101001", 3, 80),
            ("11111110", 3, 120),
        ],
    )
    def test_honours_a_width(self, table: str, n: int, width: int) -> None:
        """``width`` bounds the columns and the table still computes.

        The grid's width is dominated by its straight runs -- 49 columns per
        input reader and another 49 per leaf -- so those fold into zigzags
        that cost rows instead.  The decision tree is not folded: its
        columns carry the descent paths.  Every heading is checked, since
        the fold adds cells the funnel's beam could otherwise land on.
        """
        program = boolean.laserfuck(table, width)
        assert max(len(line) for line in program.split("\n")) <= width
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            for heading in range(4):
                got = run_laserfuck(program, [str(b) for b in bits], heading)
                assert got == str(int(table[combo])), f"{bits} heading {heading}"

    def test_a_width_stands_the_reader_on_end(self) -> None:
        """A width too narrow for the reader rotates it rather than failing.

        Laid flat the rings are one row and forty-odd columns; stood on end
        they are two columns and forty-odd rows, so a width the flat form
        cannot meet is still met.
        """
        table = "01101001"  # XOR3
        natural = max(len(ln) for ln in boolean.laserfuck(table).split("\n"))
        assert natural > 30
        narrow = boolean.laserfuck(table, 30).split("\n")
        assert max(len(ln) for ln in narrow) <= 30
        assert len(narrow) > len(boolean.laserfuck(table).split("\n"))

    def test_the_fold_uses_its_return_rows(self) -> None:
        """A same-character run fills the leftward leg, not just the right.

        A return row's beam travels left, so it may only carry ops that
        read the same in reverse -- which a run of one repeated character
        does.  The boolean generator's readers are rings now, but the fold
        still lays every leaf band and the whole text generator, so the
        fill is exercised directly here.
        """
        grid = [[" "] * 20 for _ in range(2)]
        end_row, end_col = laserfuck_layout.fold(grid, "-" * 30, 0, 3, 20)
        rows = ["".join(line).rstrip() for line in grid]
        assert rows[0].endswith("v")
        assert rows[1].endswith("{")
        assert "-" in rows[1], "the return row should carry the spilled run"
        # 30 ops at width 20: 16 on the segment row, the rest reversed onto
        # the return row, so the run never needs a second segment row.
        assert end_row == 2, "a same-character run should not need a third row"
        assert end_col == laserfuck_layout.MARGIN + 1

    def test_return_rows_only_take_a_same_character_run(self) -> None:
        """The fill stops at the first character that differs.

        A mixed run may only reverse its leading same-character stretch;
        whatever follows has to resume rightwards on the next segment row.
        """
        grid = [[" "] * 20 for _ in range(2)]
        laserfuck_layout.fold(grid, "-" * 30 + ">+++", 0, 3, 20)
        rows = ["".join(line).rstrip() for line in grid]
        body = rows[1][laserfuck_layout.MARGIN + 1 :].rstrip()
        ops = body[:-1].strip() if body.endswith("{") else body.strip()
        assert set(ops) <= {"-"}, f"mixed ops on a return row: {ops!r}"
        # the '>' that broke the run resumes on the next segment row
        assert ">" in rows[2]

    def test_folded_readers_are_rings(self) -> None:
        """The folded reader loops rather than writing 48 '-' per input.

        Two rings sit on the first row: one multiplies 8 by 6 to build the
        48 a ``,`` needs subtracting, the other spends that counter one unit
        at a time across the counter and every input.  Both are one row, so
        the reader costs a fixed two rows however many inputs there are.
        """
        rows = boolean.laserfuck("0110", 80).split("\n")
        # columns 0..2 are the funnel; the reader starts at the margin
        head = rows[0][laserfuck_layout.MARGIN :]
        legs = rows[1][laserfuck_layout.MARGIN :]
        assert head.count("}") == 3, "the reader's own '}' plus one per ring"
        assert head.count("#/)") == 2, "each ring tests its counter"
        assert legs.count("^") == 2, "each ring returns to its own '}'"
        # no 48-'-' run survives anywhere in the program
        assert "-" * 10 not in "\n".join(rows)

    def test_ringed_leaves_sit_on_their_own_descent_rows(self) -> None:
        """A leaf needs no corridor: the beam already arrives moving right.

        The old layout dropped each leaf down a private column into a band
        of its own below the tree.  With the rings the leaf simply follows
        the ``\\`` that turns the beam onto its row -- so no ``v``, no return
        row and no band, and the grid loses better than half its rows.
        """
        # width 50 forces the mirrored form, where the tree hangs below
        rows = boolean.laserfuck("0110", 50).split("\n")
        # 'x' only ever ends a leaf, so the leaf rows are exactly these
        leaves = [line for line in rows if "x" in line]
        assert len(leaves) == 4, "one leaf per input combination"
        # the all-zero leaf rides the row the tree starts on, so only the
        # mirrored, a one-branch's leaf hangs under a '/' and its code runs
        # leftward, so the 'x' comes *before* the turn.  The all-zero leaf
        # shares the tree's first row, which carries the entry mirror too.
        first = min(index for index, line in enumerate(rows) if "x" in line)
        turned = [
            line for index, line in enumerate(rows) if "x" in line and index > first
        ]
        assert len(turned) == 3
        for line in turned:
            assert line.index("x") < line.index("/")
        # nothing below the leaves: no bands, no drop corridors.  Mirrored,
        # a leaf's row ends at its turn rather than at its 'x'.
        assert rows[-1].rstrip()[-1] in "x/"

    def test_a_dropping_beam_crosses_no_other_row_s_code(self) -> None:
        """A one-branch drops through the rows above its own catcher.

        Every ``v`` sends the beam down its column until a mirror faces it
        along a row again; whatever it passes on the way is executed.  The
        rows in between must therefore be blank in that column -- which is
        what lets the tree share rows at all.
        """
        for table in ("0110", "01101001", "0110100110010110"):
            rows = boolean.laserfuck(table, 200).split("\n")
            for index, line in enumerate(rows):
                for column, char in enumerate(line):
                    if char != "v" or index < 3:
                        continue  # the funnel and reader steer themselves
                    # find the '\' that catches this drop
                    below = [
                        (k, rows[k])
                        for k in range(index + 1, len(rows))
                        if column < len(rows[k])
                    ]
                    for k, lower in below:
                        cell = lower[column]
                        if cell in "\\/":
                            break  # caught, as intended
                        assert cell == " ", (
                            f"{table}: beam from row {index} column {column} "
                            f"runs {cell!r} on row {k}"
                        )

    def test_a_wide_grid_runs_the_tree_on_the_reader_s_rows(self) -> None:
        """Given the width, the tree needs no rows of its own at all.

        The beam leaves the reader still moving right, so the cheapest
        thing is to carry straight on: the tree starts in the next column
        along, on the rows the reader is already using.  A width too narrow
        for that falls back to hanging the tree underneath, mirrored.
        """
        wide = boolean.laserfuck("0110", 80).split("\n")
        narrow = boolean.laserfuck("0110", 50).split("\n")
        assert len(wide) < len(narrow), "sharing rows should cost fewer rows"
        assert max(len(line) for line in wide) > max(len(line) for line in narrow)
        # the reader's own first row carries tree code too
        assert "#/)" in wide[0], "the reader's last ring is on row 0"
        assert ">#v)" in wide[0], "and the tree's first node follows it there"

    def test_widths_come_in_bands_not_a_cliff(self) -> None:
        """Each reader block turns on its own, so widths degrade gradually.

        Turning the whole reader at once gave two sizes and nothing in
        between; turning its blocks independently fills the gap, and a
        tighter width buys rows rather than being ignored.
        """
        seen = {
            max(len(line) for line in boolean.laserfuck("0110", width).split("\n"))
            for width in (45, 40, 30, 25, 18)
        }
        assert len(seen) >= 4, f"expected several distinct widths, got {seen}"
        # asking for less never gives more
        widths = [
            max(len(line) for line in boolean.laserfuck("0110", w).split("\n"))
            for w in (45, 40, 30, 25, 18)
        ]
        assert widths == sorted(widths, reverse=True)

    def test_a_narrow_width_beats_the_old_floor(self) -> None:
        """Standing blocks on end reaches widths the flat reader cannot."""
        for table, floor in (("0110", 18), ("01101001", 24)):
            program = boolean.laserfuck(table, floor).split("\n")
            assert max(len(line) for line in program) <= floor

    def test_ringed_leaves_leave_a_zero_answer_alone(self) -> None:
        """Cell 0 is the counter *and* the answer, so zero costs nothing.

        The rings spend the counter down to zero and leave it touched,
        which is exactly what dump() prints for a zero answer -- so a leaf
        writes a '+' only when the answer is one.

        Both tables are constant, so each folds to a single leaf that fits
        on the reader's own row; the '+' is counted over the whole program
        rather than over the rows below the reader, which a folded tree no
        longer occupies.
        """
        zero = boolean.laserfuck("0000", 80)
        ones = boolean.laserfuck("1111", 80)
        assert ones.count("+") == zero.count("+") + 1, "a one costs exactly one '+'"

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice becomes one leaf instead of branching further.

        Leaves are the ``x`` that ends each one, so counting those counts
        the leaves: a constant table spends one, two constant halves spend
        two, and a parity table -- which has no constant slice above a
        single row -- still spends one per combination.
        """
        assert boolean.laserfuck("11111111").count("x") == 1
        assert boolean.laserfuck("11110000").count("x") == 2
        assert boolean.laserfuck("10010110").count("x") == 8

    def test_a_table_that_folds_nothing_keeps_the_sized_sweep(self) -> None:
        """Parity's leaves retire each input by its own bit, not flatly.

        Only the cells above a leaf's depth need the flat two-``-``
        retiring; a parity table has no folded leaf, so every cell is one
        its path consumed and every run is sized to the bits.  Reading the
        runs back off each leaf is what pins that -- a leaf reached by
        ``bits`` spends ``bit + 1`` dashes per cell, most recent first.
        """
        program = boolean.laserfuck("10010110")
        leaves = program.split("x")[:-1]
        for path in range(8):
            bits = [(path >> (2 - i)) & 1 for i in range(3)]
            want = "".join("-" * (b + 1) + "<" for b in reversed(bits))
            assert any(leaf.endswith(want) or want in leaf for leaf in leaves), (
                f"no leaf retires {bits} with its sized run {want!r}"
            )

    def test_without_a_width_is_unchanged(self) -> None:
        """The default stays exactly what the generator always produced."""
        for table in ("01", "10", "0110", "01101001"):
            assert boolean.laserfuck(table) == boolean.laserfuck(table, None)

    def test_too_narrow_a_width_is_ignored(self) -> None:
        """A width the tree cannot fit in is ignored rather than raising.

        The tree grows six columns per node and is never folded, so below
        some width there is nothing the fold can do; the generator emits the
        grid it can build instead of failing, matching the rest of the
        width plumbing.
        """
        program = boolean.laserfuck("01101001", 8)
        assert run_laserfuck(program, ["0", "0", "0"], 3) == "0"


class TestMyScript:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.myscript(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_myscript(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice says its answer instead of branching further."""
        assert boolean.myscript("11111111").count("say") == 1
        assert boolean.myscript("11110000").count("say") == 2
        assert boolean.myscript("10010110").count("say") == 8  # parity: no fold

    def test_rejects_bad_table(self) -> None:
        with pytest.raises(ValueError, match="entries"):
            boolean.myscript("011")

    def test_rejects_non_binary(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.myscript("02")


class TestGeneratorEdgePaths:
    """Coverage for validation and helper edge paths in the generators."""

    def test_parameterized_validation(self) -> None:
        """bio/back reject malformed truth tables."""
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.bio("011")
        with pytest.raises(ValueError, match="only '0' and '1'"):
            parameterized.bio("0123")
        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.back("011")

    def test_dimensional_tree_validation(self) -> None:
        """The Dimensional decision-tree generator rejects bad truth tables."""
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.dimensional_tree("011")
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.dimensional_tree("0123")

    def test_six_five_helper_edges(self) -> None:
        """The +5 tail of the constant encoder.

        ``_six_five_nav`` was retired with the arithmetic kernel; the folded
        leaf's own hop to cell 1 is a literal ``13``.
        """
        from esolangs.tools.boolean.six_five import _six_five_const

        assert _six_five_const(5) == "5"
        assert _six_five_const(11) == "65"

    def test_ztoalc_simulator_rejects_bad_program(self) -> None:
        """An empty or non-numeric first line fails the fast simulator."""
        from esolangs.tools.boolean.ztoalc_l import _ztoalc_ok

        assert _ztoalc_ok({}, 0, "", "") is False
        assert _ztoalc_ok({0: "not-a-number"}, 0, "", "") is False

    def test_ztoalc_simulator_input_exhausted(self) -> None:
        """A '=' instruction with no input left fails the fast simulator."""
        from esolangs.tools.boolean.ztoalc_l import _ztoalc_ok

        assert _ztoalc_ok({0: "2", 1: "a = 1"}, 1, "", "") is False
