"""Unit tests for the tape-based boolean generators.

Covers the generators in :mod:`esolangs.tools.boolean.tape` plus the
single-language modules that share its tape-machine shape: ``rotfuck``,
``six_five``, ``dimensional``, and ``streetcode``.
"""

import contextlib

import pytest

from esolangs.tools import boolean
from esolangs.tools.boolean.six_five import _six_five_markers
from tests.tools.boolean_runners import (
    run_bf,
    run_bit_tilde,
    run_brainif,
    run_circlefuck,
    run_dimensional,
    run_factor,
    run_jaune,
    run_painfuck,
    run_rotfuck,
    run_sbleq,
    run_six_five,
    run_streetcode,
    run_suffolk,
    run_three_d_brainfuck,
)


def _columns(program: str) -> int:
    """The widest row of a grid program, which is what a width bounds."""
    return max(len(line) for line in program.split("\n"))


def _markers(program: str) -> int:
    """How many ``4`` markers a 6-5 program really has.

    Counting ``4`` characters overcounts: a ``8n`` jump whose operand is
    ``4`` contributes one, so this tokenizes the way the interpreter does.
    """
    from esolangs.interpreters.tape_based.six_five import _tokens

    return sum(1 for token in _tokens(program) if token == "4")


def _leaves(table: str) -> int:
    """How many leaves a tree that folds constant subtrees spends on ``table``.

    One per maximal constant slice: the walk stops as soon as the rows it
    covers agree, so this is ``2**n`` only when no slice above a single row
    is constant.
    """
    if len(set(table)) == 1:
        return 1
    half = len(table) // 2
    return _leaves(table[:half]) + _leaves(table[half:])


class TestSixFive:
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
        program = boolean.six_five(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_branch_structure(self) -> None:
        """Each level reads a bit and branches to a 4 marker."""
        program = boolean.six_five("0110")
        assert program.startswith("B" + "2" * 8)
        assert "78" in program
        assert program.endswith("A0")

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("11", 1),
            ("1111", 2),
            ("11110000", 3),
            ("1111111100000000", 4),
            ("1" * 32, 5),
        ],
    )
    def test_constant_subtrees_fold(self, table: str, n: int) -> None:
        """A constant subtree emits one leaf instead of a full branch set.

        The comparison table has the same ones-count, so a shorter program
        means the tree folded rather than that some other count shrank.
        """
        mixed = {
            1: "10",
            2: "1010",
            3: "10010110",
            4: "1001011001101001",
            5: "10010110" * 4,
        }[n]
        assert len(boolean.six_five(table)) < len(boolean.six_five(mixed))
        # One ``A`` per emitted leaf: the fold collapses the leaf count to
        # the number of distinct constant regions, not ``2**n``.
        assert boolean.six_five(table).count("A") == _leaves(table)

    @pytest.mark.parametrize(
        ("table", "n"),
        [("11", 1), ("1111", 2), ("11110000", 3), ("1000000000000000", 4)],
    )
    def test_folded_leaf_still_reads_every_input(self, table: str, n: int) -> None:
        """Every path through a folded tree reads all ``n`` inputs.

        A folded leaf skips branches but not reads: a caller feeding several
        programs from one stream would desync if a short path left bits
        unconsumed.  The interpreter raises ``EOFError`` on an over-read, so
        supplying exactly ``n`` bits proves no path reads too many, and
        counting the ``B``s down each path proves none reads too few.
        """
        program = boolean.six_five(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

        # Walk the emitted tree: a branch spends one read, then its two
        # halves follow; a leaf carries the reads its fold skipped.
        def reads_on_each_path(code: str) -> set[int]:
            if not code.startswith("B" + "2" * 8):  # a leaf
                return {code.count("B")}
            body = code[len("B" + "2" * 8) + len("78") + 2 :]
            depth = 0
            for i, char in enumerate(body):
                if body[i : i + 2] == "78":
                    depth += 1
                elif char == "4":
                    if depth == 0:
                        left, right = body[:i], body[i + 1 :]
                        break
                    depth -= 1
            else:  # pragma: no cover - a branch always has its 4 separator
                raise AssertionError("no separator")
            return {1 + r for r in reads_on_each_path(left) | reads_on_each_path(right)}

        assert reads_on_each_path(program) == {n}

    @pytest.mark.parametrize(
        ("table", "n", "labels"),
        [
            ("0" * 63 + "1", 6, 6),  # AND6: was refused by both paths
            ("1" * 32 + "0" * 32, 6, 1),  # one split
            ("1" * 48 + "0" * 16, 6, 2),  # two regions
            ("1" * 64, 6, 0),  # constant
            ("0" * 255 + "1", 8, 8),  # AND8
        ],
    )
    def test_tree_past_five_inputs(self, table: str, n: int, labels: int) -> None:
        """A folded tree that fits the label budget is used at any ``n``.

        The old gate was ``n <= 5`` on the *unfolded* node count, so these
        tables fell through to the arithmetic kernel -- which refuses most of
        them, since a table with ones at high indices has a huge ``T``.
        Folding is what spends the labels, so the choice counts them instead.
        """
        program = boolean.six_five(table)
        assert _markers(program) == labels <= 35
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_marker_precheck_matches_emitted_tree(self) -> None:
        """The dispatch's label count is what the tree actually allocates.

        The gate decides before building, so a miscount would either refuse a
        renderable table or emit one past the 35-label budget.  Counting
        ``4`` *characters* is not the same thing -- an ``8n`` jump whose
        operand is ``4`` contributes one -- so this compares against the
        interpreter's own tokenizer.
        """
        for table in (
            "0" * 63 + "1",
            "1" + "0" * 63,
            "1" * 48 + "0" * 16,
            "1" * 64,
            "1" * 127 + "0",
            "0" * 255 + "1",
        ):
            assert _six_five_markers(table) == _markers(boolean.six_five(table))

    def test_wide_table_is_refused(self) -> None:
        """A table whose folded tree exceeds 35 labels has no representation.

        The arithmetic kernel that used to catch these was retired: it needs
        ``T`` (or its complement) small enough to build, which confines the
        ones to low indices, which leaves the rest of the table constant --
        the shape that folds well inside the budget.  So it never covered a
        table the tree could not.
        """
        scattered = "10010110" * 8  # n == 6, 63 labels after folding
        assert _six_five_markers(scattered) > 35
        with pytest.raises(ValueError, match="35 branch labels"):
            boolean.six_five(scattered)

    @pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
    def test_total_through_five_inputs(self, n: int) -> None:
        """Every table up to five inputs renders: the worst case still fits.

        An alternating table folds nothing, so it spends the full ``2**n - 1``
        internal nodes -- 31 at n == 5, inside the 35-label budget.  The
        refusals therefore begin at n == 6, where that worst case is 63.
        """
        alternating = ("10" * 2**n)[: 2**n]
        assert _six_five_markers(alternating) == 2**n - 1 <= 35
        boolean.six_five(alternating)  # renders rather than raising

    def test_refusals_begin_at_six_inputs(self) -> None:
        """n == 6 is the first width whose worst case overflows the budget."""
        alternating = ("10" * 64)[:64]
        assert _six_five_markers(alternating) == 63 > 35
        with pytest.raises(ValueError, match="35 branch labels"):
            boolean.six_five(alternating)

    def test_retired_arithmetic_kernel_is_gone(self) -> None:
        """The second construction and its assembler are no longer exported."""
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.boolean.six_five")

        assert not hasattr(boolean, "six_five_arithmetic")
        assert module.__all__ == ["six_five"]
        assert not hasattr(module, "_SixFiveAsm")  # the assembler went too
        assert not hasattr(module, "_six_five_nav")


class TestStreetcode:
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
        program = boolean.streetcode(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_streetcode(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_constant_subtrees_fold(self) -> None:
        """A subtree whose rows agree prints instead of driving down halls.

        Streetcode splits most-significant-first, so a subtree is a
        contiguous run: ``11110000`` is two constant halves and collapses,
        while ``10101010`` is constant over no run and keeps every hall.
        """
        constant = len(boolean.streetcode("11111111"))
        halves = len(boolean.streetcode("11110000"))
        scattered = len(boolean.streetcode("10101010"))
        assert constant < scattered
        assert halves < scattered
        # a folded leaf still prints the right digit for every input
        for table in ("11111111", "11110000", "11001100"):
            program = boolean.streetcode(table)
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                got = run_streetcode(program, [str(b) for b in bits])
                assert got == table[combo], f"{table} inputs {bits}"

    def test_folded_leaf_keeps_the_cell_pointer_advances(self) -> None:
        """A folded leaf spends the ``=`` its skipped halls would have.

        Each hall advances CP by one on the way down, so a leaf reached
        without them prints from the wrong cell -- an all-zeros table came
        out as ``'\\x00'`` before this was threaded through.
        """
        program = boolean.streetcode("00000000")
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            assert run_streetcode(program, [str(b) for b in bits]) == "0"

    def test_width_is_a_shape_choice(self) -> None:
        """A width picks a narrower shape, and that shape still computes.

        The shapes differ in aspect -- the ring is the shortest program but
        the widest -- so a width the default overruns is met by a shape that
        was built anyway, at the cost of rows.  A Streetcode program cannot
        be reflowed after the fact, so this is the only way a width is met.
        """
        table = "10"
        default = boolean.streetcode(table)
        narrow = boolean.streetcode(table, 25)
        assert _columns(narrow) <= 25 < _columns(default)
        assert narrow.count("\n") > default.count("\n")
        for bit in ("0", "1"):
            assert run_streetcode(narrow, [bit]) == table[int(bit)]

    def test_width_takes_the_narrowest_when_none_fits(self) -> None:
        """Below every shape's width the narrowest one is returned.

        The generator has no shape narrower than its own decision tree, so
        an impossible width is a preference it cannot honour rather than an
        error; returning the best available beats returning nothing.
        """
        table = "10"
        program = boolean.streetcode(table, 1)
        assert _columns(program) == min(
            _columns(boolean.streetcode(table, w)) for w in (1, 25, 100)
        )
        for bit in ("0", "1"):
            assert run_streetcode(program, [bit]) == table[int(bit)]

    def test_width_none_is_unchanged(self) -> None:
        """Passing no width builds exactly what the generator always built."""
        for table in ("10", "0110", "11111110"):
            assert boolean.streetcode(table, None) == boolean.streetcode(table)


class TestDimensional:
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
        program = boolean.dimensional(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_dimensional(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_moves_are_pinned_to_dimension_zero(self) -> None:
        """A bare >/< would take its dimension from the cell's value."""
        program = boolean.dimensional("0110")
        rest = program.replace(">0", "").replace("<0", "")
        assert ">" not in rest
        assert "<" not in rest

    def test_scales_beyond_the_old_reference_cap(self) -> None:
        """The v3.0 interpreter's unbounded cells lift the old n <= 12 cap."""
        program = boolean.dimensional("0" * 4095 + "1")
        got = run_dimensional(program, ["1"] * 12)
        assert got == "1"

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.dimensional("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.dimensional("02")


class TestDimensionalTree:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111100000000", 4),
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.dimensional_tree(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_dimensional(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_tree_small_on_dense_tables(self) -> None:
        """The tree shares bit tests, so dense tables stay small."""
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        assert len(boolean.dimensional_tree(xor6)) < 10_000

    def test_dimensional_is_the_tree(self) -> None:
        """dimensional is the tree, sparse or dense.

        A survivor evaluator used to sit beside it, chosen when it came out
        shorter.  Folding constant subtrees put the tree ahead on every
        table at n <= 4, so the survivor was unreachable and was removed.
        """
        sparse = "0" * 15 + "1"  # AND4
        assert boolean.dimensional(sparse) == boolean.dimensional_tree(sparse)
        xor = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(16))
        assert boolean.dimensional(xor) == boolean.dimensional_tree(xor)


class TestCirclefuck:
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
        program = boolean.circlefuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_circlefuck(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize(
        ("values", "n"),
        [
            ([0, 255], 1),
            ([48, 49, 50, 51], 2),
        ],
    )
    def test_byte_values(self, values: list[int], n: int) -> None:
        """circlefuck_byte outputs the given byte per input combination."""
        program = boolean.circlefuck_byte(values)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_circlefuck(program, [str(b) for b in bits])
            assert got == chr(values[combo]), f"inputs {bits}"

    def test_byte_values_require_a_power_of_two_table(self) -> None:
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.circlefuck_byte([1, 2, 3])

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice prints its answer instead of branching further.

        Circlefuck branches on the cell the pointer is over, which is the
        *last* input, so its subtrees are strided rather than contiguous
        runs -- a table like ``11110000`` is constant over halves, an axis
        this split never sees, and folds nothing.  ``10101010`` is constant
        along the axis it does split on, so it collapses.
        """
        assert len(boolean.circlefuck("11111111")) < len(
            boolean.circlefuck("10101010"),
        )
        assert len(boolean.circlefuck("10101010")) < len(
            boolean.circlefuck("10010110"),
        )
        assert len(boolean.circlefuck("11110000")) == len(
            boolean.circlefuck("10010110"),
        )

    def test_folded_leaf_clears_its_cell(self) -> None:
        """A folded leaf builds its value on a cleared cell.

        The ``[-]`` a full-depth leaf relies on is emitted inside each
        ``[`` on the way down, so a leaf that skips those levels has to
        clear the cell itself.  Without it the cell still holds the input
        bit and every one-valued input prints one too high -- which only
        shows on an input of ``1``, so it is worth pinning per input.
        """
        program = boolean.circlefuck("11111111")
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            got = run_circlefuck(program, [str(b) for b in bits])
            assert got == "1", f"inputs {bits}"


class TestBf:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
            ("1000000000000000", 4),  # single one (AND4)
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.brainfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bf(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_bf_is_the_tree(self) -> None:
        """bf is the folded tree, for constant and sparse tables alike.

        There used to be a minterm construction here and ``bf`` returned
        whichever was shorter.  Folding left the tree ahead on every table
        but the two constant ones -- where it costs about 2.5x, a bounded
        factor on two tables out of 65536 -- so the minterm went away and
        the constant tables go to the tree with everything else.
        """
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        for table in ("0" * 16, "0" * 15 + "1", xor6):  # constant, AND4, dense
            assert boolean.brainfuck(table) == boolean.bf_tree(table)

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.brainfuck("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.brainfuck("02")


class TestBfTree:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1111111100000000", 4),
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.bf_tree(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bf(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_tree_small_on_dense_tables(self) -> None:
        """The tree shares bit tests, so dense tables stay small."""
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        assert len(boolean.bf_tree(xor6)) < 10_000

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice emits a leaf instead of branching on more bits.

        Both tables have the same number of ones, so the difference is the
        arrangement alone: ``11110000`` is two constant halves and folds to
        one leaf each, while the parity table has no constant subtree above
        a single row and emits the full tree.
        """
        assert len(boolean.bf_tree("11110000")) < len(boolean.bf_tree("10010110"))

    def test_parity_table_is_unfolded(self) -> None:
        """A table with no constant subtree still spends a leaf per row.

        The guard against a fold that fires too eagerly: parity has no
        constant slice above one row, so every one of the ``2**n`` rows
        keeps its own leaf.
        """
        xor3 = "10010110"
        assert boolean.bf_tree(xor3).count(".") == 8

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.bf_tree("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.bf_tree("02")


class TestThreeDBf:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
            ("1000000000000000", 4),  # single one (AND4)
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.three_d_brainfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_three_d_brainfuck(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_array_moves_use_the_3d_axes(self) -> None:
        """3D Brainfuck's >/< are no-ops, so the array moves with e/w."""
        program = boolean.three_d_brainfuck("0110")
        assert ">" not in program
        assert "<" not in program
        assert "e" in program
        assert "w" in program

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.three_d_brainfuck("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.three_d_brainfuck("02")


class TestFactor:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.factor(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_factor(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_is_the_decimal_encoding_of_the_bf_program(self) -> None:
        """factor delegates to the brainfuck generator and encodes its
        output, same as the text generator's factor()."""
        from esolangs.tools.text.tape import _factor_encode

        table = "0110"
        assert boolean.factor(table) == str(_factor_encode(boolean.brainfuck(table)))

    def test_sparse_tables_stay_small_at_n_four(self) -> None:
        """Sparse tables (few one-rows) encode a short brainfuck program,
        so they stay well under the digit cap even at n == 4."""
        assert boolean.factor("0" * 16).isdigit()
        assert boolean.factor("1" * 16).isdigit()

    def test_dense_table_past_the_digit_cap_is_rejected(self) -> None:
        """A dense n == 4 table (XOR4) encodes a brainfuck program whose
        Factor integer exceeds CPython's int-to-string digit limit; the
        generator raises instead of letting that ValueError leak from
        str() with its raw CPython wording."""
        xor4 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(16))
        with pytest.raises(ValueError, match="digit limit"):
            boolean.factor(xor4)

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.factor("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.factor("02")


class TestSuffolk:
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
            ("1111111100000000", 4),  # top half
            ("1000000000000000", 4),  # single one (AND4)
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.suffolk(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_suffolk(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_constant_tables_collapse_but_still_read(self) -> None:
        """A constant table skips the minterms but still reads its inputs.

        Dropping the evaluation is the win; the reads are the language's
        interface and have to stay, or the caller's bits are left unread on
        the input stream for whatever runs next.
        """
        for table in ("00", "11"):
            assert boolean.suffolk(table).count(",") == 1  # n == 1

    def test_dense_tables_evaluate_the_complement(self) -> None:
        """A table with more ones than zeros is evaluated from its zero rows.

        Cost is one minterm block per evaluated row, so before this the
        length rose monotonically with the ones-count.  Now it peaks at half
        and falls again -- the signature of picking whichever row-set is
        smaller -- which is what this pins.
        """
        lengths = [len(boolean.suffolk("1" * k + "0" * (8 - k))) for k in range(1, 8)]
        assert lengths[3] == max(lengths)  # four ones is the worst case
        assert lengths[6] < lengths[3]  # seven ones is cheaper than four
        # and roughly as cheap as its one-one mirror image
        assert abs(lengths[6] - lengths[0]) < lengths[0] // 4

    @pytest.mark.parametrize(
        "table",
        ["11111110", "1111111111111110", "0111111111111111", "11111100"],
    )
    def test_complemented_tables_still_compute(self, table: str) -> None:
        """The inverted print stage answers the original table, not its flip.

        ``.`` emits ``chr(acc - 1)`` and ``!`` computes
        ``max(0, cell + 1 - acc)``, so the constant the flip cell carries has
        to account for both; preloading it one low prints ``'/'`` instead of
        ``'0'``, which is how an earlier attempt failed.
        """
        n = (len(table) - 1).bit_length()
        program = boolean.suffolk(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_suffolk(program, [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.suffolk("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.suffolk("02")


class TestPainfuck:
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
            ("1111111100000000", 4),  # top half
            ("1000000000000000", 4),  # single one (AND4)
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.painfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_painfuck(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_commands_are_preshifted_for_the_trans_table(self) -> None:
        """The interpreter shifts commands through its cycles, so the source
        must be the inverse shift; the translated commands are the BF moves."""
        from esolangs.interpreters.tape_based.painfuck import _translate

        program = boolean.painfuck("0110")
        translated = _translate(program)
        assert "a" in translated  # [ loops
        assert "b" in translated  # ] loops
        assert translated.count("a") == translated.count("b")
        assert "rl" in translated or "l" in translated  # pointer moves

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.painfuck("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.painfuck("02")


class TestBitTilde:
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
            ("1000000000000000", 4),  # single one (AND4)
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.bit_tilde(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bit_tilde(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_single_read_and_output(self) -> None:
        """One read per input and a single final output."""
        program = boolean.bit_tilde("0110")
        assert program.startswith(")")
        assert program.count(")") == 2
        assert program.count("(") == 1
        assert program.endswith("(")

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.bit_tilde("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.bit_tilde("02")


class TestJaune:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("00", 1),  # constant zero
            ("01", 1),  # identity
            ("10", 1),  # NOT
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.jaune(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_jaune(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.jaune(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_jaune(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_reads_every_input_whatever_the_table(self) -> None:
        """Every table consumes exactly ``n`` inputs, folds included.

        This is the cross-cutting contract in
        ``test_boolean_contract.py``, pinned here because that sweep
        cannot see Jaune: it iterates the generators registered in
        ``BY_FUNCTION``, and Jaune is not one of them.  The reads used to
        sit *at* the tree's nodes, so a folded tree skipped them and a
        constant table consumed no input at all -- making the program's
        stream consumption a function of its truth table.  Without this
        test nothing would catch that coming back.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.jaune import run

        n = 3
        for table in ("11111111", "00000000", "11110000", "10101010", "10010110"):
            io = ScriptedIO("0\n" * n)
            with contextlib.suppress(Exception, SystemExit):
                run(boolean.jaune(table), io=io)
            assert io.position() == n, (
                f"{table} consumed {io.position()} inputs, expected {n}"
            )

    def test_unused_inputs_are_clobbered_not_stored(self) -> None:
        """An input no node branches on is read without keeping a cell.

        ``10101010`` depends only on its last input, so the first two
        reads need no cell of their own and the tree navigates a
        one-cell block instead of a three-cell one.
        """
        assert boolean.jaune("10101010").startswith("vvv")
        # every input matters here, so every read keeps its cell
        assert boolean.jaune("10010110").startswith("v>v>v>")

    def test_bad_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.jaune("011")

    @pytest.mark.parametrize(
        ("a", "b"),
        [
            (0, 5),
            (5, 0),
            (0, 0),
            (3, 4),
            (12, 34),
            (99, 99),
            (100, 7),
            (7, 100),
            (7, 123),
            (123, 456),
            (12345, 6789),
            (99999, 99999),
        ],
    )
    def test_multiply(self, a: int, b: int) -> None:
        """The sentinel-delimited multiply reads any-length operands."""
        program = boolean.jaune_multiply()
        lines = [*list(str(a)), "*", *list(str(b)), "#"]
        got = run_jaune(program, lines)
        assert got == str(a * b), f"{a} * {b}"

    def test_multiply_all_small_operands(self) -> None:
        """Every single-digit pair produces the right product."""
        program = boolean.jaune_multiply()
        for a in range(10):
            for b in range(10):
                lines = [*list(str(a)), "*", *list(str(b)), "#"]
                got = run_jaune(program, lines)
                assert got == str(a * b), f"{a} * {b}"


class TestBasicfuck:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_program_shape(self, table: str, n: int) -> None:
        """The program declares its cells, reads n inputs, and prints once."""
        program = boolean.basicfuck(table)
        assert program.startswith("#basicfuck t=unbounded r=0~255 o=wrap")
        assert (
            program.splitlines()[1]
            == "#allocate " + ", ".join(f"a{i}" for i in range(1, n + 1)) + ", out"
        )
        assert program.count("read ->") == n  # one read per input
        # One leaf per *constant slice*, not per row: the tree folds a
        # subtree whose rows agree, so a table with no constant slice above
        # a single row (parity) still spends 2**n leaves while a constant
        # table spends one.
        assert program.count("write <- out ;") == _leaves(table)

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice emits one leaf instead of branching further."""
        assert boolean.basicfuck("1" * 16).count("write <- out ;") == 1
        assert boolean.basicfuck("11110000").count("write <- out ;") == 2
        # parity has no constant slice above one row, so nothing folds
        assert boolean.basicfuck("10010110").count("write <- out ;") == 8

    def test_decision_tree(self) -> None:
        """Each internal node branches both ways with the wiki's if!(...)."""
        program = boolean.basicfuck("0110")
        assert program.count("if (a1) {") == 1
        assert program.count("if !(a1) {") == 1
        assert program.count("if (a2) {") == 2
        assert program.count("if !(a2) {") == 2

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.basicfuck("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.basicfuck("02")


class TestSbleq:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("0000000000000000", 4),  # constant zero
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.sbleq(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_sbleq(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_program_structure(self) -> None:
        """The root reads and normalizes, then every leaf outputs and halts."""
        program = boolean.sbleq("0110")
        cells = [int(tok) for tok in program.split()]
        data_base = len(cells) - 13
        assert cells[:3] == [data_base + 4, -2, data_base + 7]  # root read
        assert cells[3:6] == [  # root normalize
            data_base + 4,
            data_base,
            data_base + 10,
        ]
        assert cells[-13:-9] == [-49, 48, 49, -1]  # NEG49, D48, D49, HALT
        code = cells[:data_base]
        triples = [tuple(code[i : i + 3]) for i in range(0, len(code), 3)]
        outputs = [
            t for t in triples if t[0] == -3
        ]  # one output per leaf, in combo order
        assert outputs == [
            (-3, data_base + 1, 0),
            (-3, data_base + 2, 0),
            (-3, data_base + 2, 0),
            (-3, data_base + 1, 0),
        ]
        assert [t for t in triples if t == (0, 0, data_base + 3)] == 4 * [
            (0, 0, data_base + 3)
        ]  # one halt per leaf

    def test_mismatched_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.sbleq("011")

    def test_bad_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.sbleq("0123")


class TestBrainIf:
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
        program = boolean.brainif(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_brainif(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """The answer byte is built first, then an input is read and tested."""
        program = boolean.brainif("10")
        assert program.startswith("if 0 increment")
        assert "if 0 input" in program
        assert "if 48 goto" in program

    def test_the_answer_byte_is_built_once(self) -> None:
        """The climb to 48 is paid before the tree, not once per digit.

        Two per-digit output routines cost 48 + 49 increments and dominated
        the program; building the byte ahead of the branch leaves the tree
        deciding only whether to add one, so the count is 48 plus one line
        per ``1`` *leaf*.  Leaves, not rows: a constant slice folds to one
        leaf, so ``11111110`` spends three rather than seven.
        """
        for table, one_leaves in (("10", 1), ("0110", 2), ("11111110", 3)):
            assert boolean.brainif(table).count("increment") == 48 + one_leaves

    def test_one_shared_output_tail(self) -> None:
        """Both answers print from the same two lines."""
        program = boolean.brainif("0110")
        assert program.count("output") == 2

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice stops the branching, though not the reads.

        Reads carry the pointer home, so a leaf spends no moves reaching
        the answer and the fold is not handed back -- which is what an
        earlier layout, with the answer past the inputs, did.
        """
        assert len(boolean.brainif("11111111")) < len(boolean.brainif("11110000"))
        assert len(boolean.brainif("11110000")) < len(boolean.brainif("10010110"))


class TestRotfuck:
    """The ROTfuck boolean generator.

    ROTfuck rotates the program after every command, so the generator lays
    out ``[ body ]`` blocks whose ``]`` is a phantom encoded at the ``[``-fire
    seek state; both the skip and body paths re-converge in the same rotation
    state because every body length is 7 (mod 8).
    """

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
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1111111100000000", 4),  # high half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.rotfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_rotfuck(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_program_round_trips_every_table_at_n_2(self) -> None:
        """Every two-input table produces the right result."""
        for table_int in range(2 ** (2**2)):
            table = format(table_int, "04b")
            program = boolean.rotfuck(table)
            for combo in range(4):
                bits = [(combo >> (1 - i)) & 1 for i in range(2)]
                got = run_rotfuck(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.rotfuck("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.rotfuck("02")
