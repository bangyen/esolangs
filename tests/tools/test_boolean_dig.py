"""dig generator tests."""

import importlib

import pytest

import esolangs
from esolangs import tools as boolean
from esolangs.interpreters.grid_based.dig import _Machine
from esolangs.tools.dig import _DIG_STRIDE
from tests.interpreters.dig_observer import Factory


class TestDig:
    def test_four_input_parity_keeps_the_compact_layout(self) -> None:
        """Dropping the banded candidate grew this program from 436 to 706."""
        table = "0110100110010110"
        program = boolean.dig(table)
        assert len(program) <= 436

    def test_alternating_layout_has_linear_area(self) -> None:
        """Text per entry stays under a constant as the arity grows.

        The rectangle approaches nine cells an entry from *below* -- the
        leaf's own box is fixed and the tree above it adds the padding --
        so "two more levels at most quadruple" is not the contract; the
        constant is.  Thirty was the reading while every entry was a leaf.
        """
        sizes = [len(boolean.dig("01" * (2 ** (n - 1)))) / 2**n for n in (7, 9, 11)]
        assert max(sizes) < 9

    def test_banded_layout_remains_available_for_width_requests(self) -> None:
        """A banded tree fits when the flat tree exceeds the requested width."""
        from esolangs.tools.dig import _dig_grid

        table = "0110100110010110"
        n = 4
        flat = _dig_grid(table, n, None)
        banded = _dig_grid(table, n, -(-(n + 2) // 2))
        assert len(banded) < len(flat)
        program = boolean.dig(table, width=18)
        assert max(map(len, program.splitlines())) <= 18
        assert len(program) <= len(banded)

    def test_constant_subtrees_prune_their_rows(self) -> None:
        """A folded node's descendants are never written.

        Both tables have four ones, so the difference is arrangement alone:
        ``11110000`` is two constant halves and keeps one row per half,
        while parity has no constant slice above a single row and fills the
        grid.
        """
        folded = boolean.dig("11110000")
        full = boolean.dig("10010110")
        assert len(folded) < len(full)
        assert sum(1 for r in folded.split("\n") if r.strip()) < sum(
            1 for r in full.split("\n") if r.strip()
        )
        assert all(row.strip() for row in folded.splitlines())

    def test_a_long_read_run_chains_its_windows(self) -> None:
        """Past nine cells the ``$`` runs chain rather than growing a digit.

        ``$`` takes its count from the digit beside it, so one window holds
        at most nine cells -- six reads plus the three that print.  A
        constant table at n == 7 needs more than that, and must still run.
        """
        table = "1" * 128  # n == 7, constant
        program = boolean.dig(table)
        assert program.count("$") > 1  # more than one window
        assert esolangs.run("Dig", program, stdin="\n".join(["1"] * 7)).strip() == "1"

    def test_a_width_turns_the_tree_round_and_it_still_computes(self) -> None:
        """A narrower grid is the same walk, folded back over its own columns.

        The deep levels run west through mirrored blocks, so the mole meets
        each ``$`` first either way.  Only running it says the turn kept
        every path intact.
        """
        for table in ("0110", "10010110", "0110100110010110", "00010111"):
            n = len(table).bit_length() - 1
            flat = boolean.dig(table, 10_000)
            wide = max(len(row) for row in flat.splitlines())
            floor = max(len(row) for row in boolean.dig(table, 1).splitlines())
            assert floor < wide, f"{table} never narrows"
            for width in (1, 12, 18, 24, wide):
                narrow = boolean.dig(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= max(width, floor), (table, width, columns)
                factory = Factory(narrow.splitlines(), _Machine)
                for combo in range(2**n):
                    factory.check(" ".join(format(combo, f"0{n}b")), table[combo])

    @pytest.mark.parametrize("width", [1, 2, 3, 4, 7])
    def test_xor_polynomial_uses_four_operand_columns(self, width: int) -> None:

        program = esolangs.generate("Dig", "0110", width)
        assert max(map(len, program.splitlines())) == 4

    def test_a_folded_table_keeps_the_flat_layout(self) -> None:
        """Turning round is not always narrower, so the narrower one wins.

        A table that folds has few blocks to spread in the first place, and
        what the turn costs -- a spare column a level, and a leaf padded so
        its digits fall where the other band does not look -- can come to
        more than the fold saved.  ``dig`` lays both out and keeps the
        narrower, so a width it cannot meet still gets the best there is.

        These also drive the banded leaf's chained windows: a constant table
        at ``n == 6`` folds at the root and still owes six reads, one more
        than a single window covers.
        """
        for table in ("1" * 64, "1" * 32 + "0" * 32):
            len(table).bit_length() - 1
            flat = boolean.dig(table, 10_000)
            assert boolean.dig(table, 1) == flat, table

    def test_the_layout_check_refuses_a_stride_that_collides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The clearance check is what licenses the two bands sharing columns.

        With a stride of six the eastbound hops miss every westbound ``$``,
        ``#`` and digit; with the flat layout's five they do not, and the
        grid that comes out is wrong in a way only a run would show.  So the
        check has to refuse it -- a silent pass here would mean it was
        licensing nothing at all.
        """
        dig_module = importlib.import_module("esolangs.tools.dig")

        monkeypatch.setattr(dig_module, "_DIG_BAND", _DIG_STRIDE)
        for table in ("0110", "10010110", "0110100110010110"):
            with pytest.raises(AssertionError):
                boolean.dig(table, 8)
        monkeypatch.undo()
        # and the stride the rule names still builds
        table = "0110100110010110"
        factory = Factory(boolean.dig(table, 1).splitlines(), _Machine)
        for row, expected in enumerate(table):
            factory.check(" ".join(format(row, "04b")), expected)
