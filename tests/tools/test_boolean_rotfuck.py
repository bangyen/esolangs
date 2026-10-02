"""rotfuck generator tests."""

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_rotfuck,
)


class TestRotfuck:
    """The ROTfuck boolean generator.

    ROTfuck rotates the program after every command, so a loop only works if
    its every pass reads the same commands: the generator pins each loop's
    cycle to 0 (mod 8) and reaches its back-jump target through a phantom
    that is never executed.  On that it builds a tape lookup -- the table in
    the even cells, a variable-distance pointer walk over the odd ones.
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
    @pytest.mark.medium
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

    @pytest.mark.parametrize("n", [6, 7, 8])
    def test_a_second_index_digit_still_selects_the_right_entry(self, n: int) -> None:
        """The arity where the index stops fitting in one walk.

        A cell is a byte, so the index is carried six bits at a time: one
        walk per digit, each read only once the walk before it has landed.
        Six inputs still fit in one digit and seven do not, so this brackets
        the boundary -- and it is not a boundary any smaller table can
        reach, which is why the truth-table sweeps above cannot see it.
        """
        table = "".join(str(bin(row).count("1") & 1) for row in range(2**n))
        program = boolean.rotfuck(table)
        for combo in (0, 1, 2**n - 1, 2**n - 2, 2 ** (n - 1), 2 ** (n - 1) - 1):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_rotfuck(program, [str(b) for b in bits])
            assert got == table[combo], f"n={n} inputs {bits}"

    def test_the_rotation_cycle_is_the_documented_one(self) -> None:
        """``+ -> - -> > -> < -> , -> . -> [ -> ] -> +``, and it is a cycle.

        Everything else here is arithmetic on this order: which commands a
        body may use at an offset, which character encodes a phantom ``]``,
        and how far a pad shifts the rest of a block.  A rotation that is
        off by one, or runs backwards, still emits a program -- one whose
        every command means something else.
        """
        from esolangs.tools.rotfuck import _ROTFUCK_CHAIN, _rotfuck_rot

        assert _ROTFUCK_CHAIN == "+-><,.[]"
        for i, char in enumerate(_ROTFUCK_CHAIN):
            forward = _ROTFUCK_CHAIN[(i + 1) % 8]
            assert _rotfuck_rot(char, 1) == forward, char
            assert _rotfuck_rot(forward, -1) == char, char
            assert _rotfuck_rot(char, 8) == char, char
            assert _rotfuck_rot(char, 0) == char, char

    def test_a_command_never_shows_as_a_bracket_inside_a_seek(self) -> None:
        """A command's rotation, seen from a seek's, must not be a bracket.

        A seek reads the whole program at one fixed rotation, so a command
        that executes ``d`` steps after that rotation shows there as
        ``rot^-d`` of itself.  Showing as a bracket moves the seek's depth
        count and pairs the loop with the wrong character, which leaves a
        program that still runs and computes something else.  The two
        offsets that matter most are 2 and 3, where only two of the four
        commands survive -- and they exclude *different* ones, which is what
        makes the padding necessary rather than cosmetic.
        """
        from esolangs.tools.rotfuck import _rotfuck_rot, _shows

        for seek in range(8):
            for rot in range(8):
                for cmd in "+-><":
                    assert _shows(cmd, seek, rot) == (
                        _rotfuck_rot(cmd, seek - rot) in "[]"
                    ), (cmd, seek, rot)
        assert [c for c in "+-><" if not _shows(c, 0, 2)] == [">", "<"]
        assert [c for c in "+-><" if not _shows(c, 0, 3)] == ["+", "<"]
        assert [c for c in "+-><" if not _shows(c, 0, 4)] == ["+", "-"]

    def test_every_pad_is_invisible_and_they_are_shortest_first(self) -> None:
        """Padding shifts the rotation without shifting anything else.

        A pad is what moves a command off a rotation where it would read as
        a bracket, so it has to leave every cell and the pointer where it
        found them -- and never step left of where it started, because
        ``<`` clamps at cell zero and a pad that reached past the caller's
        cell would not be neutral there.  Length runs shortest first, since
        padding is pure cost.
        """
        from esolangs.tools.rotfuck import _PADS

        assert _PADS[0] in ("+-", "-+", "><")
        assert list(_PADS) == sorted(_PADS, key=len)
        for pad in _PADS:
            cells: dict[int, int] = {}
            at = low = 0
            for char in pad:
                assert char in "+-><", pad
                at += (char == ">") - (char == "<")
                low = min(low, at)
                cells[at] = cells.get(at, 0) + (char == "+") - (char == "-")
            assert at == 0, pad
            assert low == 0, pad
            assert not any(cells.values()), pad

    @pytest.mark.parametrize("trips", range(7))
    def test_a_loop_leaves_the_rotation_where_it_found_it(self, trips: int) -> None:
        """The invariant every loop rests on, checked by running one.

        A loop's trip count is data, so the rotation it exits at must not
        depend on it -- otherwise every command after the loop means
        something else for a different input.  The generator gets that by
        padding each loop's cycle to 0 (mod 8).  Here a drain loop runs
        ``trips`` times and the *same* trailing ``+`` run and ``.`` follow
        it: if the exit rotation moved with the trip count, that tail would
        not still be a print of the right character.
        """
        from esolangs.tools.helpers import _ASCII_ZERO
        from esolangs.tools.rotfuck import _Builder

        out = _Builder()
        out.travel(2)
        out.emit("+" * trips)
        out.travel(4)
        out.drain("-<<+>>>>++")
        out.travel(0)
        out.emit("+" * _ASCII_ZERO)
        out.emit(".")
        assert run_rotfuck(out.text(), []) == str(trips)

    def test_the_program_is_only_command_characters(self) -> None:
        """Nothing but the eight commands is emitted.

        ROTfuck treats a character outside its alphabet as a comment that
        neither executes *nor advances the rotation*, so stray text is
        invisible to any behavioural check -- a program with padding
        between every command computes the same table.  The alphabet is
        therefore asserted directly rather than inferred from the answer.
        """
        for table in ("01", "0110", "11110000", "01101001"):
            assert set(boolean.rotfuck(table)) <= set("+-><,.[]"), table

    @pytest.mark.parametrize(
        ("table", "length"),
        [
            ("01", 224),
            ("10", 224),
            ("0001", 390),
            ("0110", 391),
            ("11110000", 228),
            ("01101001", 571),
        ],
    )
    def test_the_emitted_length_is_exact(self, table: str, length: int) -> None:
        """The layout is deterministic down to the character.

        Several ways of getting this wrong leave a *correct* program: a
        pad taken at four characters where two would have hidden, a cycle
        padded to 8 (mod 8) rather than 0 (which is the same rotation and
        so still runs), or a travel that walks the pointer home when it is
        already there.  None of them changes an answer, and a loose size
        bound only catches them by luck, so the lengths are pinned.

        ``11110000`` also carries dependency reduction: it lays out a
        two-entry table, 228 characters against ``01101001``'s 571.
        """
        assert len(boolean.rotfuck(table)) == length


def test_rotfuck_loop_does_not_swallow_an_invariant_failure() -> None:
    from esolangs.tools.rotfuck import _Builder

    def broken() -> None:
        raise AssertionError("broken body invariant")

    with pytest.raises(AssertionError, match="broken body invariant"):
        _Builder().loop(broken, lambda: None)
