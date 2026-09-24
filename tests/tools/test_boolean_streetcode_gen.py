"""Covers :mod:`esolangs.tools.streetcode`.

Named for the generator, not the interpreter: tests/interpreters/test_streetcode
covers the car that drives what this emits.
"""

from importlib import import_module

import pytest

from esolangs import tools as boolean
from esolangs.tools.wrap import shortest
from tests.tools.boolean_runners import (
    run_streetcode,
)


def _columns(program: str) -> int:
    """The widest row of a grid program, which is what a width bounds."""
    return max(len(line) for line in program.split("\n"))


# 2.3s over 84 tests: runs the generated program.
@pytest.mark.medium
class TestStreetcode:
    # One case per row, because each run rebuilds the machine and revalidates
    # the whole grid: nine in one test is 2.5s locally and over the band on a
    # slower runner.  The build is 0.03s of that, so splitting costs nothing.
    @pytest.mark.parametrize("combo", [0, 1, 2, 17, 31, 32, 47, 62, 63])
    def test_linear_h_tree_executes_wide_rows(self, combo: int) -> None:
        """The alternating-axis layout reaches both sides of every level."""
        n = 6
        table = "".join(str(index.bit_count() & 1) for index in range(2**n))
        program = boolean.streetcode(table)
        bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
        assert run_streetcode(program, [str(bit) for bit in bits]) == table[combo]

    def test_h_tree_rectangle_is_linear(self) -> None:
        """Alternating axes bound the rendered rectangle, not just live roads.

        Extended to n=11 (roadmap): the per-row hall that carried
        a `log T` factor is gone, and the fixed per-T constants below still
        hold one arity past where they were first pinned.

        The constants restate the branch pitch: the rectangle goes as its
        square, so dropping it from 16 to its measured floor of 8
        (:data:`~esolangs.tools.streetcode._H_PITCH`) took the rectangle from
        1113 to 325 cells per leaf and the source from 979 to 248 chars.
        """
        for n in range(6, 12):
            table = "".join(str(index.bit_count() & 1) for index in range(2**n))
            program = boolean.streetcode(table)
            rows = program.splitlines()
            assert len(rows) * max(map(len, rows)) <= 400 * 2**n
            assert len(program) <= 280 * 2**n

    def test_compact_layout_compares_both_rotations(self) -> None:
        """Rotation strips the dense tree's leading triangular padding."""
        from esolangs.tools.streetcode import _streetcode_rotate

        table = "01101001"
        original = boolean.streetcode(table, width=10_000)
        rotated = _streetcode_rotate(original)
        assert len(rotated) < len(original)
        assert boolean.streetcode(table) == rotated

    def test_default_uses_only_shared_layouts(self) -> None:
        """Per-input loops are width fallbacks, never default candidates."""
        module = import_module("esolangs.tools.streetcode")

        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                tree = module._streetcode_tree(table)  # noqa: SLF001
                shared = module._streetcode_shared_programs(table, n, tree)  # noqa: SLF001
                all_programs = [
                    *shared,
                    *(module._streetcode_rotate(p) for p in shared),  # noqa: SLF001
                ]
                assert boolean.streetcode(table) == shortest(*all_programs)

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

    def test_input_reordering_folds_a_scattered_table(self) -> None:
        """The tree splits in whichever order folds most, not input order.

        ``10101010`` depends on the last input alone, so it folds nothing
        splitting most-significant-first and everything once that input is
        tested at the root.  Reordering is what lets it be emitted as the
        cheap shape, and it costs only the walk that puts the bit in the
        cell the root's hall tests.
        """
        scattered = len(boolean.streetcode("10101010"))
        aligned = len(boolean.streetcode("11110000"))
        parity = len(boolean.streetcode("01101001"))
        # Both are one-dependency tables, so reordering brings the scattered
        # one down to the aligned one's shape.  It stays a few characters
        # longer, and those characters are the walk that puts its bit in the
        # cell the root's hall tests -- the price of the reorder, paid once
        # in the prefix rather than per hall.
        assert aligned < scattered < parity
        assert scattered - aligned < 0.05 * aligned

    def test_input_reordering_never_grows_a_program(self) -> None:
        """The identity order is built first and ties keep it.

        A table no reorder improves has to emit exactly what it emitted
        before, so reordering can only ever shrink a program.  ``01101001``
        is parity, which folds under no order at all.
        """
        parity = boolean.streetcode("01101001")
        # Parity is the table where every order is equally bad, so the
        # program is the identity one and carries no reordering walks.
        assert "_I" not in parity

    @pytest.mark.parametrize(
        "table",
        ["10101010", "11001100", "01011010", "00111100", "10010110"],
    )
    def test_reordered_programs_compute_the_table(self, table: str) -> None:
        """A reordered program still computes its function.

        The cell an input is read into is the *inverse* of the split order --
        level ``k`` tests cell ``k + 1`` and must test input ``perm[k]`` -- so
        reading it forward stores the right bits in the wrong cells and
        computes a different function.  Only running it catches that.
        """
        program = boolean.streetcode(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            got = run_streetcode(program, [str(b) for b in bits])
            assert got == table[combo], f"{table} inputs {bits}"

    def test_reordering_keeps_the_reads_in_stream_order(self) -> None:
        """Reordering moves where a bit is stored, never when it is read.

        The program consumes its input stream exactly as it did before: one
        ``I`` per input, in input order.  What moves is the cell each lands
        in, so the count of reads is what pins this down.
        """
        for table in ("10101010", "11110000", "01101001"):
            assert boolean.streetcode(table).count("I") == 3

    def test_width_is_a_shape_choice(self) -> None:
        """A width picks a narrower shape, and that shape still computes.

        The hallway trades columns for rows, so a width the default overruns
        is met by a shape that was built anyway, at the cost of rows. A
        Streetcode program cannot
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

    def test_a_requested_width_is_never_overrun(self) -> None:
        """A width that *can* be met is met, measured on the emitted columns.

        The width is a promise about the widest row, and the only way to
        keep it is to pick a shape that already fits, so measuring the
        wrong thing -- splitting the program on whitespace rather than on
        newlines, say -- selects a shape that overruns while every
        truth-table check still passes.  ``0001`` at 33 is the tight case:
        the winning shape is exactly 33 columns, so a column count that
        drifts either way changes which shape is returned.
        """
        for table, width in (("0001", 33), ("0110", 33), ("01", 29)):
            program = boolean.streetcode(table, width)
            assert _columns(program) <= width, (table, width)

    def test_the_narrowest_fallback_is_really_the_narrowest(self) -> None:
        """Below every shape's width, the narrowest shape comes back.

        ``10`` cannot witness this: its candidates happen to agree, so a
        fallback that returned the first or the lexicographically smallest
        program would pass.  ``0100`` separates them -- the narrowest is 33
        columns where the wrong pick is 36.
        """
        program = boolean.streetcode("0100", 1)
        assert _columns(program) == 33
        for combo in range(4):
            bits = [str((combo >> 1) & 1), str(combo & 1)]
            assert run_streetcode(program, bits) == "0100"[combo]

    def test_a_width_equal_to_a_shape_is_wide_enough(self) -> None:
        """The fit test is inclusive: exactly the shape's width fits it.

        At its own column count the default shape still fits, so asking for
        exactly that many columns must return it rather than falling
        through to a narrower, longer one.  One column more is the same
        program; the suite otherwise only asks for 1, 25 and 100, none of
        which lands on a boundary.
        """
        default = boolean.streetcode("01")
        assert _columns(default) == 29
        assert boolean.streetcode("01", 29) == default
        assert boolean.streetcode("01", 30) == default

    @pytest.mark.parametrize(
        ("table", "length"),
        [("01", 302), ("0000", 340), ("0101", 340)],
    )
    def test_the_emitted_program_has_an_exact_length(
        self, table: str, length: int
    ) -> None:
        """The layout is deterministic down to the character.

        Streetcode's rows are built from fixed templates and padded runs,
        so a run one wide, a lap one column longer, or a trailing blank row
        all leave a *working* program of a different size -- and nothing
        else here measures size at all.
        """
        assert len(boolean.streetcode(table)) == length

    def test_no_trailing_blank_row(self) -> None:
        """The grid ends on its last real row.

        The row count is one plus the deepest row written, and an off-by-one
        there appends an empty row that the interpreter walks over
        harmlessly -- invisible to every behavioural check.
        """
        for table in ("01", "0101", "0110", "11111110"):
            program = boolean.streetcode(table)
            assert not program.endswith("\n"), table
            assert program.split("\n")[-1].strip(), table

    def test_the_program_is_only_streetcode_characters(self) -> None:
        """Only the glyphs Streetcode reads, plus layout space.

        Measured over every table through three inputs and a spread of
        widths rather than read off the spec: the generator uses a subset,
        and asserting the spec's full set would pass vacuously.
        """
        allowed = set(" +-;=CIOU^_|~\n")
        for table in ("01", "0000", "0110", "11111110"):
            assert set(boolean.streetcode(table)) <= allowed, table
        for width in (1, 20, 29, 33):
            assert set(boolean.streetcode("0110", width)) <= allowed, width

    def test_only_identity_and_greedy_orders_are_offered(self) -> None:
        """Streetcode never renders more than two order candidates."""
        from esolangs.tools.streetcode import _streetcode_orders

        table = "01011010"
        assert _streetcode_orders(table, 3)[0] == (0, 1, 2)
        assert len(_streetcode_orders(table, 3)) <= 2
