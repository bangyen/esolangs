"""Unit tests for the Dimensional v3.0 interpreter."""

import importlib

import pytest

from esolangs.interpreters.io import IO
from esolangs.tools.boolean.tape import dimensional as bool_gen
from esolangs.tools.text.other import dimensional as text_gen
from tests.interpreters.contract import SnapshotContract
from tests.interpreters.runner import run_program
from tests.raises import raises_message

dim = importlib.import_module("esolangs.interpreters.tape_based.dimensional")


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    return run_program(dim.run, code, "".join(f"{line}\n" for line in inputs or []))


class TestDimensional:
    def test_output_character(self) -> None:
        assert run_and_capture("+" * 65 + ".") == "A"

    def test_hex_literal(self) -> None:
        assert run_and_capture("=41.") == "A"
        assert run_and_capture("=4a.") == "J"

    def test_char_literal(self) -> None:
        assert run_and_capture(":A.") == "A"

    def test_cell_wraps_at_256(self) -> None:
        assert run_and_capture("+" * 256 + ".") == "\x00"

    def test_linear_tape(self) -> None:
        """The default axis-2 pointer is a linear byte tape."""
        assert run_and_capture("+>0+<0.>0.") == "\x01\x01"

    def test_read_input(self) -> None:
        assert run_and_capture(",.", ["A"]) == "A"

    def test_decimal_and_hex_input(self) -> None:
        assert run_and_capture("d.", ["65"]) == "A"
        assert run_and_capture("x.", ["41"]) == "A"

    def test_bracket_loop(self) -> None:
        assert run_and_capture("+[.-]") == "\x01"

    def test_a_loop_runs_its_body_once_per_count(self) -> None:
        """One iteration cannot show how many the loop takes.

        ``+[.-]`` prints once whether the body runs once, or the jump lands
        somewhere that happens to end the run -- the output is the same
        length either way.  Counting down from three separates them: the
        body has to run exactly three times, and each pass prints the value
        it is standing on.
        """
        assert run_and_capture("=03[.-]") == "\x03\x02\x01"

    def test_comment_mode(self) -> None:
        """Everything between two *s is ignored."""
        assert run_and_capture("*=[.<]*+.+.+.") == "\x01\x02\x03"

    def test_coordinate_read_clear(self) -> None:
        assert run_and_capture(">0>0?0.") == "\x02"
        assert run_and_capture(">0!0?0.") == "\x00"

    def test_clearing_a_dimension_never_moved_along(self) -> None:
        """``!`` on a coordinate that was never set is a no-op, not an error.

        The clear above always follows a move, so the coordinate it removes
        is always present -- a clear that insisted on finding one would
        never notice.  At the origin nothing has been recorded, and the
        clear has to leave it that way.
        """
        assert run_and_capture("!0?0.") == "\x00"

    def test_negative_dimension(self) -> None:
        assert run_and_capture(">~1+?~1.") == "\x01"

    def test_moving_the_other_way_along_a_negative_dimension(self) -> None:
        """``<~1`` steps back, so the coordinate wraps to -1 rather than 1.

        The one negative-dimension case moves right, where the ``~`` and
        the sign it applies both push the same way -- reading the
        coordinate back as 1 whether the minus is honoured or dropped.
        Moving left makes the sign visible: the coordinate is -1, which
        prints as 0xff.
        """
        assert run_and_capture("<~1?~1.") == "\xff"

    def test_clearing_a_negative_dimension(self) -> None:
        """``!~1`` names the same dimension ``>~1`` moved along."""
        assert run_and_capture(">~1!~1?~1.") == "\x00"

    def test_a_parameterless_command_takes_the_value_as_its_argument(self) -> None:
        """A bare ``>`` or ``$`` reads the current cell, not the next token.

        ``>$3?0.`` is the discriminating shape: the ``>`` has no number of
        its own, so it uses the value (0) as its dimension, and the ``$3``
        that follows is a separate command rather than its argument.  A
        parser that consumed the ``$`` as the move's operand would move
        along dimension 3 and read a different coordinate.
        """
        assert run_and_capture(">$3?0.") == "\x00"
        assert run_and_capture("$>0?0.") == "\x01"

    def test_a_hex_literal_stops_at_the_command_after_it(self) -> None:
        """The rejected text is the literal alone, not the rest of the line.

        ``=`` takes two hex digits, so a bad one has to report just those
        -- a scan that ran on would quote the following command too, and
        the message is the only place that shows.
        """
        with raises_message(ValueError, "invalid hex literal 'g0'"):
            run_and_capture("=g0.")

    def test_bare_move_uses_value_as_dimension(self) -> None:
        assert run_and_capture("+>+.") == "\x01"

    def test_trailing_parameterized_command(self) -> None:
        """A > or $ at the very end needs no following number."""
        assert run_and_capture(">") == ""
        assert run_and_capture("$") == ""

    def test_axis_loop(self) -> None:
        """{d loops while the axis pointer's dimension-d coordinate is nonzero."""
        assert run_and_capture(">0>0{0<0?0.}?0.") == "\x01\x00\x00"

    def test_axis_selection(self) -> None:
        """$AXIS moves a higher pointer; ? reads its coordinate."""
        assert run_and_capture("$3>0?0.") == "\x01"

    def test_higher_axis_preserves_origin(self) -> None:
        """Moving a higher pointer away and back to the origin restores the tape."""
        program = ", $3>0$2, $3<0$2."
        assert run_and_capture(program, ["A", "B"]) == "A"

    def test_the_axis_starts_at_the_byte_pointer(self) -> None:
        """With no ``$AXIS`` the moves act on pointer 2, addressing bytes.

        Every axis test names its pointer explicitly, so the default was
        never the thing under test -- a tape that started one level up
        would still pass them all.  Here nothing selects an axis: a bare
        move has to walk the byte tape, so the two cells hold their own
        values and moving back finds the first again.
        """
        assert run_and_capture("=41.>0=42.<0.") == "ABA"

    def test_moving_a_higher_pointer_selects_a_fresh_byte(self) -> None:
        """A level-3 move lands on an untouched level-2 slot.

        This is what makes the hierarchy a hierarchy rather than a second
        linear tape, and it reads the default axis from the other side:
        the ``$3`` move must leave the byte behind, and dropping back to
        the default must find it again.
        """
        assert run_and_capture("=41.$3>0.<0.") == "A\x00A"

    def test_text_generator_round_trips(self) -> None:
        for text in ("Hi", "Hello, World!", "\x00\x7f\xff"):
            assert run_and_capture(text_gen(text)) == text

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111100000000", 4),
        ],
    )
    def test_boolean_generator(self, table: str, n: int) -> None:
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_and_capture(bool_gen(table), bits) == table[combo], bits

    def test_rejects_unmatched_brackets(self) -> None:
        with pytest.raises(ValueError, match="unmatched"):
            dim.run("[", IO())
        with pytest.raises(ValueError, match="unmatched"):
            dim.run("]", IO())
        with pytest.raises(ValueError, match="unmatched"):
            dim.run("{", IO())
        with pytest.raises(ValueError, match="unmatched"):
            dim.run("}", IO())

    def test_rejects_bad_literals(self) -> None:
        with pytest.raises(ValueError, match="hex"):
            dim.run("=zz.", IO())
        with pytest.raises(ValueError, match="hex"):
            dim.run("=4", IO())
        with pytest.raises(ValueError, match="character"):
            dim.run(":", IO())


class TestStepMachine:
    def test_snapshot_freezes_a_higher_dimensional_tape(self) -> None:
        """A tape raised past 2D nests levels, each frozen into the key."""
        from esolangs.interpreters.tape_based.dimensional import _Machine

        machine = _Machine("^^>+.", IO())
        seen = set()
        for _ in range(50):
            if machine.halted:
                break
            seen.add(machine.snapshot())
            machine.step()
        assert len(seen) > 1


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.tape_based.dimensional import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "+" * 3 + "."
