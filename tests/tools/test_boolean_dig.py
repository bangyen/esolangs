"""dig generator tests."""

import importlib

import pytest

import esolangs
from esolangs import tools as boolean
from esolangs.tools.dig import _DIG_BRANCH, _DIG_RETURN, _DIG_STRIDE
from tests.tools.boolean_runners import (
    run_dig,
)


class TestDig:
    def test_four_input_parity_keeps_the_compact_layout(self) -> None:
        """Dropping the banded candidate grew this program from 436 to 706."""
        table = "0110100110010110"
        program = boolean.dig(table)
        assert len(program) <= 436
        for row, expected in enumerate(table):
            assert run_dig(program, list(format(row, "04b"))) == expected

    @pytest.mark.medium
    def test_alternating_layout_executes_every_row(self) -> None:
        """The alternating-axis tree computes two dense wide tables."""
        for n in (5, 6):
            size = 1 << n
            tables = (
                ("01101001" * size)[:size],
                "".join(str((row * 73 + row // 3) & 1) for row in range(size)),
            )
            for table in tables:
                program = boolean.dig(table)
                for combo in range(size):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    assert run_dig(program, [str(bit) for bit in bits]) == table[combo]

    def test_alternating_layout_has_linear_area(self) -> None:
        """Text per entry stays under a constant as the arity grows."""
        sizes = [len(boolean.dig("01" * (2 ** (n - 1)))) / 2**n for n in (7, 9, 11)]
        assert max(sizes) < 9

    def test_xor_layout(self) -> None:
        """The XOR gate produces the standard two-level decision tree."""
        expected = (
            "'         >$30:@\n"
            "     >$3~;#\n"
            "          >$31:@\n"
            ">$3~;#\n"
            "          >$31:@\n"
            "     >$3~;#\n"
            "          >$30:@"
        )
        assert boolean.dig("0110", width=80) == expected

    def test_banded_layout_remains_available_for_width_requests(self) -> None:
        """A banded tree fits when the flat tree exceeds the requested width."""
        from esolangs.tools.dig import _dig_grid

        table = "0110100110010110"
        n = 4
        flat = _dig_grid(table, n, None)
        banded = _dig_grid(table, n, -(-(n + 2) // 2))
        assert len(banded) < len(flat)
        assert boolean.dig(table, width=18) == banded

    def test_a_constant_table_is_one_line(self) -> None:
        """Nothing to branch on, so the whole grid is a single leaf."""
        program = boolean.dig("1111")
        assert program.split("\n") == ["'", ">$5~~1:@"]

    def test_constant_subtrees_prune_their_rows(self) -> None:
        """A folded node's descendants are never written."""
        folded = boolean.dig("11110000")
        full = boolean.dig("10010110")
        assert len(folded) < len(full)
        assert sum(1 for r in folded.split("\n") if r.strip()) < sum(
            1 for r in full.split("\n") if r.strip()
        )
        assert all(row.strip() for row in folded.splitlines())

    def test_unaligned_leaf_chains_seven_input_reads(self) -> None:
        """A folded flat leaf needs two windows beyond its six-read tail."""
        from esolangs.interpreters.grid_based.dig import run
        from esolangs.interpreters.io import ScriptedIO

        for expected in "01":
            program = boolean.dig(expected * 128, 1000)
            for row in range(128):
                io = ScriptedIO("\n".join(format(row, "07b")) + "\n")
                run(program.splitlines(), io)
                assert io.getvalue() == expected
                assert io.reads == 7

    def test_a_long_read_run_chains_its_windows(self) -> None:
        """Past nine cells the ``$`` runs chain rather than growing a digit."""
        table = "1" * 128  # n == 7, constant
        program = boolean.dig(table)
        assert program.count("$") > 1  # more than one window
        assert esolangs.run("Dig", program, stdin="\n".join(["1"] * 7)).strip() == "1"

    def test_a_width_turns_the_tree_round_and_it_still_computes(self) -> None:
        """A narrower grid is the same walk, folded back over its own columns."""
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
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    got = run_dig(narrow, [str(b) for b in bits])
                    assert got == str(int(table[combo])), (table, width, bits)

    def test_rotated_small_dig_trees_keep_all_operand_reads(self) -> None:
        """Quarter-turning changes neighbor priority, so execute every path."""
        assert max(map(len, boolean.dig("0110", 1).splitlines())) == 4
        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                program = boolean.dig(table, 1)
                for row, expected in enumerate(table):
                    bits = list(format(row, f"0{n}b"))
                    assert run_dig(program, bits) == expected

    def test_xor_polynomial_uses_four_operand_columns(self) -> None:
        from esolangs.interpreters.grid_based.dig import run
        from esolangs.interpreters.io import ScriptedIO

        # Every width up to 7 builds this same program.
        program = esolangs.generate("Dig", "0110", width=1)
        assert max(map(len, program.splitlines())) == 4
        for row, expected in enumerate("0110"):
            io = ScriptedIO("\n".join(f"{row:02b}") + "\n")
            run(program.splitlines(), io)
            assert (io.getvalue(), io.reads) == (expected, 2)

    def test_a_folded_table_keeps_the_flat_layout(self) -> None:
        """Turning round is not always narrower, so the narrower one wins."""
        for table in ("1" * 64, "1" * 32 + "0" * 32):
            n = len(table).bit_length() - 1
            flat = boolean.dig(table, 10_000)
            assert boolean.dig(table, 1) == flat, table
            for combo in (0, 2 ** (n - 1), 2**n - 1):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_dig(flat, [str(b) for b in bits])
                assert got == str(int(table[combo])), (table, bits)

    def test_the_turn_mirrors_the_blocks_it_writes(self) -> None:
        """Past the turn a block is written backwards, so its ``$`` comes first."""
        narrow = boolean.dig("0110100110010110", 1)
        assert _DIG_BRANCH[::-1] in narrow, "no mirrored block: the tree never turned"
        assert _DIG_RETURN in narrow, "nothing points the mole west"
        flat = boolean.dig("0110100110010110", 10_000)
        assert _DIG_BRANCH[::-1] not in flat
        assert _DIG_RETURN not in flat

    def test_the_layout_check_refuses_a_stride_that_collides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The clearance check is what licenses the two bands sharing columns."""
        dig_module = importlib.import_module("esolangs.tools.dig")

        monkeypatch.setattr(dig_module, "_DIG_BAND", _DIG_STRIDE)
        for table in ("0110", "10010110", "0110100110010110"):
            with pytest.raises(AssertionError):
                boolean.dig(table, 8)
        monkeypatch.undo()
        # and the stride the rule names still builds
        assert boolean.dig("0110100110010110", 1)

    def test_ignored_leading_inputs_are_read_down_one_column(self) -> None:
        """Leading ignored inputs and constants cost a column, not a wider tree."""
        inner = "0110"
        for count in (1, 7, 8, 9):
            table = inner * (1 << count)
            n = count + 2
            program = boolean.dig(table)
            assert program.endswith("\n" + boolean.dig(inner))
            for row in (0, 1, 2, 3, (1 << n) - 1, (1 << n) - 2):
                bits = [str(row >> (n - 1 - i) & 1) for i in range(n)]
                assert run_dig(program, bits) == table[row], (count, row)
        for n in (6, 7, 8):
            for value in "01":
                program = boolean.dig(value * (1 << n))
                assert len(program) < 4 * n + 8
                assert run_dig(program, ["1"] * n) == value
