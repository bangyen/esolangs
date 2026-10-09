"""rotfuck generator tests."""

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_rotfuck,
)
from tests.witness_tables import row_bits


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
            bits = row_bits(combo, n)
            got = run_rotfuck(program, [str(b) for b in bits])
            assert got == table[combo], f"n={n} inputs {bits}"

    def test_the_rotation_cycle_is_the_interpreters_default(self) -> None:
        """The prose's ``+-><,.[]`` turned backward, and it is a cycle."""
        from esolangs.interpreters.tape_based.rotfuck import CYCLES
        from esolangs.tools.rotfuck import _ROTFUCK_CHAIN, _rotfuck_rot

        assert _ROTFUCK_CHAIN == "+][.,<>-" == CYCLES["backward"]
        assert "+" + "+-><,.[]"[:0:-1] == _ROTFUCK_CHAIN
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
        assert [c for c in "+-><" if not _shows(c, 0, 4)] == ["+", "-"]
        assert [c for c in "+-><" if not _shows(c, 0, 5)] == ["+", "<"]
        assert [c for c in "+-><" if not _shows(c, 0, 6)] == [">", "<"]

    def test_every_pad_is_invisible_and_they_are_shortest_first(self) -> None:
        """Padding shifts the rotation without shifting anything else."""
        from esolangs.tools.rotfuck import _PADS

        assert _PADS[:4] == ("+-", "-+", "><", "<>")
        assert list(_PADS) == sorted(_PADS, key=len)
        for pad in _PADS:
            cells: dict[int, int] = {}
            at = 0
            for char in pad:
                assert char in "+-><", pad
                at += (char == ">") - (char == "<")
                cells[at] = cells.get(at, 0) + (char == "+") - (char == "-")
            assert at == 0, pad
            assert not any(cells.values()), pad

    @pytest.mark.parametrize("trips", range(7))
    def test_a_loop_leaves_the_rotation_where_it_found_it(self, trips: int) -> None:
        """The invariant every loop rests on, checked by running one."""
        from esolangs.tools.helpers import _ASCII_ZERO
        from esolangs.tools.rotfuck import _Builder, _parse

        out = _Builder()
        out.emit(_parse("+" * trips + "[->+<]>" + "+" * _ASCII_ZERO + "."))
        assert run_rotfuck(out.text(), []) == str(trips)

    @pytest.mark.parametrize("body", ["-", "-+-", ">+<-", "[-]"])
    def test_a_body_of_either_parity_closes_at_its_phase(self, body: str) -> None:
        """An even body opens with a ``[`` that cannot fire; an odd one does not."""
        from esolangs.tools.helpers import _ASCII_ZERO
        from esolangs.tools.rotfuck import _Builder, _parse

        out = _Builder()
        out.emit(_parse(f"+++[{body}]" + "+" * _ASCII_ZERO + "."))
        assert run_rotfuck(out.text(), []) == "0"

    def test_the_program_is_only_command_characters(self) -> None:
        """Nothing but the eight commands is emitted."""
        for table in ("01", "0110", "11110000", "01101001"):
            assert set(boolean.rotfuck(table)) <= set("+-><,.[]"), table

    def test_only_the_default_rotation_is_targeted(self) -> None:
        assert boolean.rotfuck("01", rotation="backward") == boolean.rotfuck("01")
        with pytest.raises(ValueError, match="backward"):
            boolean.rotfuck("01", rotation="forward")

    @pytest.mark.parametrize(
        ("table", "length"),
        [
            ("01", 128),
            ("10", 128),
            ("0001", 211),
            ("0110", 212),
            ("11110000", 134),
            ("01101001", 301),
        ],
    )
    def test_the_emitted_length_is_exact(self, table: str, length: int) -> None:
        """The layout is deterministic down to the character."""
        assert len(boolean.rotfuck(table)) == length

    def test_a_long_run_of_zero_entries_is_skipped_by_a_walk_and_runs(self) -> None:
        """A zero upper half is one carried count, not 2 * 128 steps."""
        half = "".join(str(bin(row * 37 % 256).count("1") & 1) for row in range(128))
        table = half + "0" * 128
        program = boolean.rotfuck(table)
        assert len(program) < len(boolean.rotfuck(half + half[::-1]))
        for combo in (0, 1, 127, 128, 200, 255):
            bits = [(combo >> (7 - i)) & 1 for i in range(8)]
            assert run_rotfuck(program, [str(b) for b in bits]) == table[combo]


def test_rotation_is_checked():
    with pytest.raises(ValueError, match="rotation"):
        boolean.rotfuck("01", rotation="sideways")


@pytest.mark.medium
@pytest.mark.parametrize("bit", "01")
def test_every_constant_row_within_written_state_bound(bit: str) -> None:
    from esolangs import generate
    from esolangs.tools.rotfuck import _program
    from tests.generator_support import assert_shared_program

    language = "ROTfuck"
    table = bit * 256
    plain = _program(table, keep_constant_input=True)
    commands = len(generate(language, table))

    def workspace(p):
        return (
            2 * 256
            + 5 * 8
            + 35
            + (2080 * len(p)).bit_length()
            + (518).bit_length()
            + len(p).bit_length()
            + 4
        )

    assert_shared_program(language, table, plain, commands, workspace)


@pytest.mark.parametrize("n", [1, 2, 3, 5, 8, 11])
@pytest.mark.parametrize("bit", "01")
def test_balancing_retains_legacy_constant_shape(n: int, bit: str) -> None:
    from esolangs.tools.rotfuck import _program
    from tests.generator_support import assert_constant_balanced_shape

    table = bit * (1 << n)
    assert_constant_balanced_shape(
        "ROTfuck", "rotfuck", table, _program(table, keep_constant_input=True)
    )
