"""rotfuck generator tests."""

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_rotfuck,
)


class TestRotfuck:
    """The ROTfuck boolean generator."""

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
        """The arity where the index stops fitting in one walk."""
        table = "".join(str(bin(row).count("1") & 1) for row in range(2**n))
        program = boolean.rotfuck(table)
        for combo in (0, 1, 2**n - 1, 2**n - 2, 2 ** (n - 1), 2 ** (n - 1) - 1):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_rotfuck(program, [str(b) for b in bits])
            assert got == table[combo], f"n={n} inputs {bits}"

    def test_the_rotation_cycle_is_the_documented_one(self) -> None:
        """``+ -> - -> > -> < -> , -> . -> [ -> ] -> +``, and it is a cycle."""
        from esolangs.tools.rotfuck import _ROTFUCK_CHAIN, _rotfuck_rot

        assert _ROTFUCK_CHAIN == "+-><,.[]"
        for i, char in enumerate(_ROTFUCK_CHAIN):
            forward = _ROTFUCK_CHAIN[(i + 1) % 8]
            assert _rotfuck_rot(char, 1) == forward, char
            assert _rotfuck_rot(forward, -1) == char, char
            assert _rotfuck_rot(char, 8) == char, char
            assert _rotfuck_rot(char, 0) == char, char

    def test_a_command_never_shows_as_a_bracket_inside_a_seek(self) -> None:
        """A command's rotation, seen from a seek's, must not be a bracket."""
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
        """Padding shifts the rotation without shifting anything else."""
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
        """The invariant every loop rests on, checked by running one."""
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
        """Nothing but the eight commands is emitted."""
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
        """The layout is deterministic down to the character."""
        assert len(boolean.rotfuck(table)) == length


def test_rotfuck_loop_does_not_swallow_an_invariant_failure() -> None:
    from esolangs.tools.rotfuck import _Builder

    def broken() -> None:
        raise AssertionError("broken body invariant")

    with pytest.raises(AssertionError, match="broken body invariant"):
        _Builder().loop(broken, lambda: None)
