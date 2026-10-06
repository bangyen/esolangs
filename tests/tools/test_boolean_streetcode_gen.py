"""Covers :mod:`esolangs.tools.streetcode`."""

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
    def test_the_flat_lookup_addresses_every_entry(self, combo: int) -> None:
        """Each input's room walks the pointer by its own weight."""
        n = 6
        table = "".join(str(index.bit_count() & 1) for index in range(2**n))
        program = boolean.streetcode(table)
        bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
        assert run_streetcode(program, [str(bit) for bit in bits]) == table[combo]

    def test_the_flat_lookup_is_nine_rows_at_every_arity(self) -> None:
        """The layout is a street, so the rectangle is linear by its height."""
        for n in range(6, 12):
            table = "".join(str(index.bit_count() & 1) for index in range(2**n))
            program = boolean.streetcode(table)
            rows = program.splitlines()
            assert len(rows) == 9, n
            assert len(rows) * max(map(len, rows)) <= 18 * 2**n + 3200, n
            assert len(program) <= 11 * 2**n + 3000, n

    def test_compact_layout_compares_both_rotations(self) -> None:
        """Rotation strips the dense tree's leading triangular padding."""
        from esolangs.tools.streetcode import _streetcode_rotate

        table = "01101001"
        original = boolean.streetcode(table, width=10_000)
        rotated = _streetcode_rotate(original)
        assert len(rotated) < len(original)
        assert boolean.streetcode(table) == rotated

    def test_default_uses_only_shared_layouts(self) -> None:
        """Through five inputs, defaults choose only shared layouts."""
        module = import_module("esolangs.tools.streetcode")

        for n in (1, 2, 3, 5):
            values = (0x9466E472,) if n == 5 else range(1 << (1 << n))
            for value in values:
                table = format(value, f"0{1 << n}b")
                tree = module._streetcode_tree(table)  # noqa: SLF001
                shared = module._streetcode_shared_programs(table, n, tree)  # noqa: SLF001
                all_programs = [
                    *shared,
                    *(module._streetcode_rotate(p) for p in shared),  # noqa: SLF001
                ]
                assert boolean.streetcode(table) == shortest(*all_programs)

    def test_constant_subtrees_fold(self) -> None:
        """A subtree whose rows agree prints instead of driving down halls."""
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
        """A folded leaf spends the ``=`` its skipped halls would have."""
        program = boolean.streetcode("00000000")
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            assert run_streetcode(program, [str(b) for b in bits]) == "0"

    def test_input_reordering_folds_a_scattered_table(self) -> None:
        """The tree splits in whichever order folds most, not input order."""
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
        """The identity order is built first and ties keep it."""
        parity = boolean.streetcode("01101001")
        # Parity is the table where every order is equally bad, so the
        # program is the identity one and carries no reordering walks.
        assert "_I" not in parity

    @pytest.mark.parametrize(
        "table",
        ["10101010", "11001100", "01011010", "00111100", "10010110"],
    )
    def test_reordered_programs_compute_the_table(self, table: str) -> None:
        """A reordered program still computes its function."""
        program = boolean.streetcode(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            got = run_streetcode(program, [str(b) for b in bits])
            assert got == table[combo], f"{table} inputs {bits}"

    def test_reordering_keeps_the_reads_in_stream_order(self) -> None:
        """Reordering moves where a bit is stored, never when it is read."""
        for table in ("10101010", "11110000", "01101001"):
            assert boolean.streetcode(table).count("I") == 3

    def test_width_is_a_shape_choice(self) -> None:
        """A width picks a narrower shape, and that shape still computes."""
        table = "10"
        default = boolean.streetcode(table)
        narrow = boolean.streetcode(table, 25)
        assert _columns(narrow) <= 25 < _columns(default)
        assert narrow.count("\n") > default.count("\n")
        for bit in ("0", "1"):
            assert run_streetcode(narrow, [bit]) == table[int(bit)]

    def test_width_takes_the_narrowest_when_none_fits(self) -> None:
        """Below every shape's width the narrowest one is returned."""
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
        """A width that *can* be met is met, measured on the emitted columns."""
        for table, width in (("0001", 33), ("0110", 33), ("01", 29)):
            program = boolean.streetcode(table, width)
            assert _columns(program) <= width, (table, width)

    def test_the_narrowest_fallback_is_really_the_narrowest(self) -> None:
        """Below every shape's width, the narrowest shape comes back."""
        program = boolean.streetcode("0100", 1)
        assert _columns(program) == 7
        for combo in range(4):
            bits = [str((combo >> 1) & 1), str(combo & 1)]
            assert run_streetcode(program, bits) == "0100"[combo]

    def test_a_width_equal_to_a_shape_is_wide_enough(self) -> None:
        """The fit test is inclusive: exactly the shape's width fits it."""
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
        """The layout is deterministic down to the character."""
        assert len(boolean.streetcode(table)) == length

    def test_no_trailing_blank_row(self) -> None:
        """The grid ends on its last real row."""
        for table in ("01", "0101", "0110", "11111110"):
            program = boolean.streetcode(table)
            assert not program.endswith("\n"), table
            assert program.split("\n")[-1].strip(), table

    def test_the_program_is_only_streetcode_characters(self) -> None:
        """Only the glyphs Streetcode reads, plus layout space."""
        allowed = set(" +-;=CIOU^_|~\n")
        for table in ("01", "0000", "0110", "11111110"):
            assert set(boolean.streetcode(table)) <= allowed, table
        for width in (1, 20, 29, 33):
            assert set(boolean.streetcode("0110", width)) <= allowed, width

    def test_only_identity_and_greedy_orders_are_offered(self) -> None:
        """Streetcode never renders more than two order candidates."""
        from esolangs.tools.helpers import input_orders

        table = "01011010"
        assert input_orders(table)[0] == (0, 1, 2)
        assert len(input_orders(table)) <= 2


def test_a_width_past_the_crossover_still_chooses_a_shape() -> None:
    """Past the crossover a quarter turn gives the shared seven-column floor."""
    table = "0110100110010110" * 4
    both = (boolean.streetcode(table), _columns(boolean.streetcode(table)))
    assert boolean.streetcode(table, 10_000) == both[0]
    assert _columns(boolean.streetcode(table, 1)) == 7


@pytest.mark.parametrize("n", [1, 3, 6])
@pytest.mark.parametrize("row", [0, 1, -1])
@pytest.mark.parametrize("width", [1, 8])
def test_quarter_turned_lookup_preserves_input_order(
    n: int, row: int, width: int
) -> None:
    from esolangs.interpreters.grid_based.streetcode import run
    from esolangs.interpreters.io import ScriptedIO

    table = "".join(str((value * 73 + value // 3) & 1) for value in range(1 << n))
    row %= len(table)
    program = boolean.streetcode(table, width)
    assert _columns(program) == (7 if width < 9 else 9)
    io = ScriptedIO(f"{row:0{n}b}")
    run(program.splitlines(), io)
    assert (io.getvalue(), io.reads) == (table[row], n)


def test_quarter_turned_rendered_size_is_linear() -> None:
    from itertools import pairwise

    sizes = [
        len(boolean.streetcode("01101001" * (2 ** (n - 3)), 1)) for n in (5, 6, 7, 8)
    ]
    assert all(later < 2 * earlier for earlier, later in pairwise(sizes))
