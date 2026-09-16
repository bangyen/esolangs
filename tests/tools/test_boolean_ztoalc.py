"""Covers :mod:`esolangs.tools.ztoalc_l`."""

import importlib

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_ztoalc,
)


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
        program = boolean.ztoalc_l(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_ztoalc(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to two inputs produces the right result."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.ztoalc_l(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                assert run_ztoalc(program, [str(b) for b in bits]) == table[combo]

    def test_structure(self) -> None:
        """The program is a branch-free array lookup on a Collatz trajectory."""
        program = boolean.ztoalc_l("0110")
        lines = program.splitlines()
        assert lines[0].strip().isdigit()  # line 1 is the starting value
        assert any(line.strip().startswith("t = [") for line in lines)
        assert any(line.strip().startswith("print") for line in lines)
        # The construction branches on nothing, so the tree's jumps are gone.
        assert not any("jump" in line for line in lines)

    def test_commands_are_placed_without_collisions(self) -> None:
        """Every command occupies its own line, in trajectory order.

        This is the placement guarantee stated directly: a Collatz
        trajectory visits distinct values until it reaches 1, so the
        commands land on distinct lines and each executes exactly once --
        and a subset of the trajectory's positions is still visited in
        trajectory order, so skipping the large values changes nothing.
        """
        from esolangs.tools.ztoalc_l import _commands, _slots

        for table in ("0110", "1010001000011000", "0110100110010110"):
            n = len(table).bit_length() - 1
            cmds = _commands(table, n)
            program = boolean.ztoalc_l(table)
            start, slots = _slots(len(cmds))
            assert len(set(slots)) == len(slots), table
            assert 1 not in slots, table
            emitted = program.splitlines()
            assert int(emitted[0]) == start, table
            assert [emitted[v - 1] for v in slots] == cmds, table

    def test_the_slots_are_the_smallest_usable_values(self) -> None:
        """Placement takes the L smallest values, so size is minimal.

        The emitted line count is the largest slot, and any L values of
        the trajectory work (they stay in visit order), so the L smallest
        are the cheapest correct choice -- the prefix the old placement
        used peaks superexponentially instead, which is what capped the
        generator at eight inputs.
        """
        from esolangs.tools.ztoalc_l import (
            _MAX_LINES,
            _slots,
            _usable_values,
        )

        for length in (8, 23, 199, 329):
            start, slots = _slots(length)
            usable = _usable_values(start, _MAX_LINES)
            assert len(slots) == length
            assert sorted(slots) == sorted(usable)[:length]
            visit_order = {v: i for i, v in enumerate(usable)}
            assert [visit_order[v] for v in slots] == sorted(
                visit_order[v] for v in slots
            )

    def test_xor4_is_small(self) -> None:
        """XOR4 renders compactly, where the old linear fallback was huge.

        The removed fallback placed a branch-free program on the pure
        power-of-two descent, so its ``2**L`` lines put XOR4 at 524,288.  A
        trajectory's peak grows far slower, and the same program fits in
        hundreds of lines.
        """
        table = "0110100110010110"
        program = boolean.ztoalc_l(table)
        assert len(program.splitlines()) < 1000
        for combo in range(16):
            bits = [str((combo >> (3 - i)) & 1) for i in range(4)]
            assert run_ztoalc(program, bits) == table[combo], f"inputs {bits}"

    def test_dense_non_symmetric_table(self) -> None:
        """A dense non-symmetric table renders; it once could not be placed.

        Neither the tree (under any input order) nor the popcount-symmetric
        fallback could place this table, so the generator refused it.  The
        lookup construction has no placement problem to fail at.
        """
        table = "1010001000011000"
        program = boolean.ztoalc_l(table)
        for combo in range(16):
            bits = [str((combo >> (3 - i)) & 1) for i in range(4)]
            assert run_ztoalc(program, bits) == table[combo], f"inputs {bits}"

    def test_constant_table_skips_the_lookup(self) -> None:
        """A constant table prints its constant, still draining its inputs."""
        for n, bit in ((2, "0"), (3, "1")):
            table = bit * (2**n)
            program = boolean.ztoalc_l(table)
            assert "t = [" not in program
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_ztoalc(program, bits) == bit

    def test_zero_input_table_is_refused(self) -> None:
        """A single-entry table is a constant, not a function of any input."""
        for bit in ("0", "1"):
            with pytest.raises(ValueError, match="at least one input"):
                boolean.ztoalc_l(bit)

    def test_table_past_the_anchor_capacity_is_refused(self) -> None:
        """A table needing more slots than any committed anchor is refused."""

        module = importlib.import_module("esolangs.tools.ztoalc_l")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "ANCHORS", [(1, 2), (8, 6)])
            with pytest.raises(ValueError, match="committed anchors offer"):
                module.ztoalc_l("0110")

    def test_a_lower_line_ceiling_shrinks_the_capacity(self) -> None:
        """Tightening ``_MAX_LINES`` removes slots, not just lines.

        Capacity is the count of trajectory values at or below the
        ceiling, so the ceiling and the anchor table are one refusal, not
        two: at 8 lines even the longest anchor keeps only a handful of
        usable values.
        """

        module = importlib.import_module("esolangs.tools.ztoalc_l")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_MAX_LINES", 8)
            with pytest.raises(ValueError, match="at or below 8"):
                module.ztoalc_l("0110")

    def test_the_anchor_fits_a_length_landing_on_its_interval_end(self) -> None:
        """An interval bound is inclusive: ``length == end`` still fits.

        An off-by-one at the bound silently takes the next anchor -- a
        working program, but a needlessly larger one.  Row ``(7, 6)`` ends
        at seven, and a seven-input constant table emits eight commands, so
        both sides of the bound are real cases.
        """
        from esolangs.tools.ztoalc_l import _commands, _slots

        assert len(_commands("0" * 128, 7)) == 8
        assert _slots(7)[0] == 6
        assert _slots(8)[0] == 9
        # The smallest anchor, to show the lookup is not simply constant.
        assert _slots(1)[0] == 2

    def test_a_roomier_anchor_does_not_win_by_having_room(self) -> None:
        """Selection is by ``end``, not by the first anchor with the room.

        Start 9 holds 19 usable values, so a first-fit scan would answer
        every length up to 19 with it -- but at 13 commands start 18 ends
        on a lower line.  This is the whole point of ``end``: ignoring it
        cost up to 2.7x at ``n == 8`` and 1.8-2.3x at ``n == 9``.
        """
        from esolangs.tools.ztoalc_l import _MAX_LINES, _slots, _usable_values

        assert len(_usable_values(9, _MAX_LINES)) >= 13
        assert _slots(12)[0] == 9
        assert _slots(13)[0] == 18
        assert max(_slots(13)[1]) < max(sorted(_usable_values(9, _MAX_LINES))[:13])

    def test_the_refusal_names_the_length_and_the_capacity(self) -> None:
        """The refusal reports the request and the committed ceiling.

        Both numbers are what makes the message actionable -- how many
        slots the table needs, against how many the anchors keep under the
        line ceiling -- and a substring match on the wording checks
        neither, so they are compared whole.  ``_slots`` is exercised
        directly because no valid table lands just past the bound.
        """
        from esolangs.tools.ztoalc_l import (
            _MAX_LINES,
            _slots,
            _usable_values,
        )
        from esolangs.tools.ztoalc_starts import ANCHORS

        capacity = max(len(_usable_values(s, _MAX_LINES)) for _, s in ANCHORS)
        assert capacity == 386  # start 511935; the sieved record anywhere is 395
        with pytest.raises(ValueError, match="committed anchors offer") as caught:
            _slots(capacity + 1)
        assert str(caught.value) == (
            f"the ZTOALC L boolean generator needs {capacity + 1} command "
            f"lines at or below {_MAX_LINES}; the committed anchors offer "
            f"at most {capacity}"
        )

    def test_lines_off_the_slots_are_left_empty(self) -> None:
        """A line no command lands on is blank, not filler.

        ZTOALC L reads a blank line as a no-op, and anything else there
        would be executed, so the padding is required rather than
        cosmetic.  The trajectory's values *above* the last slot need no
        lines at all -- the interpreter reads past-the-end as blank -- and
        the emitted size is the largest slot, not the trajectory's peak.
        """
        from esolangs.tools.ztoalc_l import _commands, _slots

        table = "0110"
        program = boolean.ztoalc_l(table)
        lines = program.splitlines()
        _, slots = _slots(len(_commands(table, 2)))
        occupied = {v - 1 for v in slots} | {0}
        assert len(lines) == max(slots)
        assert [i for i, ln in enumerate(lines) if ln != ""] == sorted(occupied)
        assert all(lines[i] == "" for i in range(len(lines)) if i not in occupied)

    def test_the_arrays_are_declared_at_exactly_their_domains(self) -> None:
        """``t`` holds one slot per chunk and ``u`` one per code, no more.

        The chunk index runs to ``2**(n - 2) - 1`` and a four-row chunk's
        code to 15, so larger declarations are still *correct* -- they just
        reserve slots nothing can address.  Only the emitted text sees the
        size, which is why it is asserted here rather than left to the
        truth-table sweeps.
        """
        for table, n in (("0110", 2), ("00010111", 3), ("1010001000011000", 4)):
            program = boolean.ztoalc_l(table)
            assert f"t = [{2 ** (n - 2)}]" in program, table
            assert "u = [16]" in program, table

    def test_a_chunk_set_carries_four_rows_in_one_command(self) -> None:
        """The init block spends one command per nonzero chunk, not per row.

        This is what carries ten inputs: the old one-hot init cost one
        command per selected row (512 at ``n == 10``, more than any start
        under the line ceiling has usable values), where the chunk sets
        cost at most ``2**(n - 2)`` (256) plus a decode block capped at
        ``1 + 16 + 32``.
        """
        from esolangs.tools.ztoalc_l import _commands

        for n in (2, 3):
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                if len(set(table)) == 1:
                    continue
                cmds = _commands(table, n)
                chunks = [table[c * 4 : (c + 1) * 4] for c in range(2 ** (n - 2))]
                sets = [c for c in cmds if c.startswith("t[")]
                assert len(sets) == sum(1 for c in chunks if "1" in c), table
                assert len(sets) <= 2 ** (n - 2), table

    def test_the_decode_block_builds_each_code_once(self) -> None:
        """``u`` gets one entry per *distinct* chunk code, zero included.

        Parity's chunks are all ``0110`` or ``1001``, so its decode block
        is two entries however wide the table -- and a zero chunk needs
        ``u[0]`` to exist, because ``t``'s elements default to 0 and
        ``u[t[s]]`` must reach an array, not an int.
        """
        from esolangs.tools.ztoalc_l import _commands

        cmds = _commands("01101001", 3)  # parity: chunks 0110, 1001
        assert [c for c in cmds if c.startswith("u = ")] == ["u = [16]"]
        assert [c for c in cmds if c.startswith("u[") and "= [" in c] == [
            "u[6] = [4]",
            "u[9] = [4]",
        ]

        cmds = _commands("00000001", 3)  # a zero chunk forces u[0]
        assert "u[0] = [4]" in cmds
        assert [c for c in cmds if c.startswith("t[")] == ["t[1] = 1"]

    def test_ten_inputs_build_and_answer(self) -> None:
        """Parity at ten inputs builds and answers spot rows correctly.

        The old one-hot encoding needed 555 commands here against a sieved
        record of 395 usable values, so no placement could save it; the
        chunked lookup needs 287 (dense worst case 329) against the
        committed anchors' 386.  All 1024 rows of this table and of a
        dense pseudo-random one were verified once against the real
        interpreter (2s each); the sweep here is spot rows to keep the
        suite's budget.
        """
        table = "".join(str(bin(i).count("1") % 2) for i in range(1024))
        program = boolean.ztoalc_l(table)
        assert len(program.splitlines()) <= 2**22
        for combo in (0, 1, 5, 137, 512, 682, 1000, 1023):
            bits = [str((combo >> (9 - i)) & 1) for i in range(10)]
            assert run_ztoalc(program, bits) == table[combo], combo

    def test_wrong_length_rejected(self) -> None:
        """A truth table of the wrong length is malformed."""
        with pytest.raises(ValueError, match="entries"):
            boolean.ztoalc_l("011")

    def test_invalid_chars_rejected(self) -> None:
        """A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.ztoalc_l("02")
