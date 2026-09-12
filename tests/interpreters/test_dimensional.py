r"""Unit tests for the Dimensional v3.0 interpreter."""

import importlib

import pytest

from esolangs.interpreters.io import IO
from esolangs.tools.boolean.tape import dimensional as bool_gen
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
        r"""The default axis-2 pointer is a linear byte tape."""
        assert run_and_capture("+>0+<0.>0.") == "\x01\x01"

    def test_read_input(self) -> None:
        assert run_and_capture(",.", ["A"]) == "A"

    def test_decimal_and_hex_input(self) -> None:
        assert run_and_capture("d.", ["65"]) == "A"
        assert run_and_capture("x.", ["41"]) == "A"

    def test_bracket_loop(self) -> None:
        assert run_and_capture("+[.-]") == "\x01"

    def test_a_loop_runs_its_body_once_per_count(self) -> None:
        r"""One iteration cannot show how many the loop takes."""
        assert run_and_capture("=03[.-]") == "\x03\x02\x01"

    def test_comment_mode(self) -> None:
        r"""Everything between two *s is ignored."""
        assert run_and_capture("*=[.<]*+.+.+.") == "\x01\x02\x03"

    def test_an_unbalanced_bracket_inside_a_comment_is_ignored(self) -> None:
        r"""The bracket scan skips comment regions, so these are not errors."""
        assert run_and_capture("*]*+.") == "\x01"
        assert run_and_capture("*[*+.") == "\x01"
        assert run_and_capture("*[[[*+.") == "\x01"
        assert run_and_capture("*}{*+.") == "\x01"

    def test_a_comment_closes_at_its_second_star(self) -> None:
        r"""Commands after the closing ``*`` run."""
        assert run_and_capture("*xyz*+.+.") == "\x01\x02"

    def test_a_bracket_after_a_comment_is_still_matched(self) -> None:
        r"""The *bracket scan* has to leave comment mode too, not just the run."""
        with pytest.raises(ValueError, match="unmatched"):
            dim.run("*xyz*]", IO())
        with pytest.raises(ValueError, match="unmatched"):
            dim.run("*xyz*[", IO())
        # and a balanced pair past the.
        assert run_and_capture("*xyz*=03[.-]") == "\x03\x02\x01"

    def test_coordinate_read_clear(self) -> None:
        assert run_and_capture(">0>0?0.") == "\x02"
        assert run_and_capture(">0!0?0.") == "\x00"

    def test_clearing_a_dimension_never_moved_along(self) -> None:
        r"""``!`` on a coordinate that was never set is a no-op, not an error."""
        assert run_and_capture("!0?0.") == "\x00"

    def test_negative_dimension(self) -> None:
        assert run_and_capture(">~1+?~1.") == "\x01"

    def test_moving_the_other_way_along_a_negative_dimension(self) -> None:
        r"""``<~1`` steps back, so the coordinate wraps to -1 rather than 1."""
        assert run_and_capture("<~1?~1.") == "\xff"

    def test_clearing_a_negative_dimension(self) -> None:
        r"""``!~1`` names the same dimension ``>~1`` moved along."""
        assert run_and_capture(">~1!~1?~1.") == "\x00"

    def test_a_parameterless_command_takes_the_value_as_its_argument(self) -> None:
        r"""A bare ``>`` or ``$`` reads the current cell, not the next token."""
        assert run_and_capture(">$3?0.") == "\x00"
        assert run_and_capture("$>0?0.") == "\x01"

    def test_a_hex_literal_stops_at_the_command_after_it(self) -> None:
        r"""The rejected text is the literal alone, not the rest of the line."""
        with raises_message(ValueError, "invalid hex literal 'g0'"):
            run_and_capture("=g0.")

    def test_bare_move_uses_value_as_dimension(self) -> None:
        assert run_and_capture("+>+.") == "\x01"

    def test_trailing_parameterized_command(self) -> None:
        r"""A > or $ at the very end needs no following number."""
        assert run_and_capture(">") == ""
        assert run_and_capture("$") == ""

    def test_axis_loop(self) -> None:
        r"""{d loops while the axis pointer's dimension-d coordinate is nonzero."""
        assert run_and_capture(">0>0{0<0?0.}?0.") == "\x01\x00\x00"

    def test_axis_selection(self) -> None:
        r"""$AXIS moves a higher pointer; ."""
        assert run_and_capture("$3>0?0.") == "\x01"

    def test_the_selected_axis_is_the_one_asked_for(self) -> None:
        r"""``$AXIS`` sets the axis to exactly ``AXIS``, clamped below at 2."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.dimensional import _Machine

        def axis_after(program: str) -> int:
            machine = _Machine(program, ScriptedIO(""))
            while not machine.halted:
                machine.step()
            return machine.tape.axis

        assert axis_after("+.") == 2  # the default, with no $AXIS at.
        assert axis_after("$2+.") == 2
        assert axis_after("$3+.") == 3
        assert axis_after("$9+.") == 9
        # values below 2 clamp: there.
        assert axis_after("$1+.") == 2
        assert axis_after("$0+.") == 2

    def test_higher_axis_preserves_origin(self) -> None:
        r"""Moving a higher pointer away and back to the origin restores the."""
        program = ", $3>0$2, $3<0$2."
        assert run_and_capture(program, ["A", "B"]) == "A"

    def test_the_axis_starts_at_the_byte_pointer(self) -> None:
        r"""With no ``$AXIS`` the moves act on pointer 2, addressing bytes."""
        assert run_and_capture("=41.>0=42.<0.") == "ABA"

    def test_moving_a_higher_pointer_selects_a_fresh_byte(self) -> None:
        r"""A level-3 move lands on an untouched level-2 slot."""
        assert run_and_capture("=41.$3>0.<0.") == "A\x00A"

    def test_hex_literals_print_their_bytes(self) -> None:
        r"""``=NN.`` loads a hex byte and prints it, once per character."""
        assert run_and_capture("=48.=69.") == "Hi"

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # NOT.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
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
        r"""A tape raised past 2D nests levels, each frozen into the key."""
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
    r"""The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "+" * 3 + "."
