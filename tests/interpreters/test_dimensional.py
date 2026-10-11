"""Unit tests for the Dimensional v3.0 interpreter."""

import importlib

import pytest

from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.tape_based.dimensional import _Machine as Dimensional
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.contract import SnapshotContract
from tests.interpreters.runner import run_lines
from tests.support.raises import assert_rejected_with_hint, raises_message

dim = importlib.import_module("esolangs.interpreters.tape_based.dimensional")


run_and_capture = run_lines(dim.run)


class TestDimensional:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            pytest.param("+" * 65 + ".", "A", id="output_character"),
            pytest.param(":A.", "A", id="char_literal"),
            pytest.param("+" * 256 + ".", "\x00", id="cell_wraps_at_256"),
            # the default axis-2 pointer is a linear byte tape
            pytest.param("+>0+<0.>0.", "\x01\x01", id="linear_tape"),
            pytest.param("+[.-]", "\x01", id="bracket_loop"),
            # one iteration cannot show how many the loop takes
            pytest.param(
                "=03[.-]", "\x03\x02\x01", id="a_loop_runs_its_body_once_per_count"
            ),
            # everything between two *s is ignored
            pytest.param("*=[.<]*+.+.+.", "\x01\x02\x03", id="comment_mode"),
            # commands after the closing * run
            pytest.param(
                "*xyz*+.+.", "\x01\x02", id="a_comment_closes_at_its_second_star"
            ),
            # ! on a coordinate that was never set is a no-op, not an error
            pytest.param("!0?0.", "\x00", id="clearing_a_dimension_never_moved_along"),
            pytest.param(">~1+?~1.", "\x01", id="negative_dimension"),
            # <~1 steps back, so the coordinate wraps to -1 rather than 1
            pytest.param(
                "<~1?~1.", "\xff", id="moving_the_other_way_along_a_negative_dimension"
            ),
            # !~1 names the same dimension >~1 moved along
            pytest.param(">~1!~1?~1.", "\x00", id="clearing_a_negative_dimension"),
            pytest.param("+>+.", "\x01", id="bare_move_uses_value_as_dimension"),
            # {d loops while the axis pointer's dimension-d coordinate is nonzero
            pytest.param(">0>0{0<0?0.}?0.", "\x01\x00\x00", id="axis_loop"),
            # $AXIS moves a higher pointer; ? reads its coordinate
            pytest.param("$3>0?0.", "\x01", id="axis_selection"),
            # with no $AXIS the moves act on pointer 2, addressing bytes
            pytest.param(
                "=41.>0=42.<0.", "ABA", id="the_axis_starts_at_the_byte_pointer"
            ),
            # a level-3 move lands on an untouched level-2 slot
            pytest.param(
                "=41.$3>0.<0.",
                "A\x00A",
                id="moving_a_higher_pointer_selects_a_fresh_byte",
            ),
            # =NN. loads a hex byte and prints it, once per character
            pytest.param("=48.=69.", "Hi", id="hex_literals_print_their_bytes"),
            # Pins the bracket scan skipping ``:CHAR`` data: ``:[`` sets 0x5B.
            pytest.param(":[.", "[", id="a_char_literal_payload_is_not_a_bracket"),
        ],
    )
    def test_prints(self, code: str, expected: str) -> None:
        assert run_and_capture(code) == expected

    def test_hex_literal(self) -> None:
        assert run_and_capture("=41.") == "A"
        assert run_and_capture("=4a.") == "J"

    def test_read_input(self) -> None:
        assert run_and_capture(",.", ["A"]) == "A"

    def test_decimal_and_hex_input(self) -> None:
        assert run_and_capture("d.", ["65"]) == "A"
        assert run_and_capture("x.", ["41"]) == "A"

    def test_an_unbalanced_bracket_inside_a_comment_is_ignored(self) -> None:
        """The bracket scan skips comment regions, so these are not errors."""
        assert run_and_capture("*]*+.") == "\x01"
        assert run_and_capture("*[*+.") == "\x01"
        assert run_and_capture("*[[[*+.") == "\x01"
        assert run_and_capture("*}{*+.") == "\x01"

    def test_a_bracket_after_a_comment_is_still_matched(self) -> None:
        """The *bracket scan* has to leave comment mode too, not just the run."""
        with pytest.raises(ValueError, match="unmatched"):
            dim.run("*xyz*]", IO())
        with pytest.raises(ValueError, match="unmatched"):
            dim.run("*xyz*[", IO())
        # and a balanced pair past the comment still loops
        assert run_and_capture("*xyz*=03[.-]") == "\x03\x02\x01"

    def test_coordinate_read_clear(self) -> None:
        assert run_and_capture(">0>0?0.") == "\x02"
        assert run_and_capture(">0!0?0.") == "\x00"

    def test_a_parameterless_command_takes_the_value_as_its_argument(self) -> None:
        """A bare ``>`` or ``$`` reads the current cell, not the next token."""
        assert run_and_capture(">$3?0.") == "\x00"
        assert run_and_capture("$>0?0.") == "\x01"

    def test_a_hex_literal_stops_at_the_command_after_it(self) -> None:
        """The rejected text is the literal alone, not the rest of the line."""
        with raises_message(ValueError, "invalid hex literal 'g0'"):
            run_and_capture("=g0.")

    def test_trailing_parameterized_command(self) -> None:
        """A > or $ at the very end needs no following number."""
        assert run_and_capture(">") == ""
        assert run_and_capture("$") == ""

    def test_the_selected_axis_is_the_one_asked_for(self) -> None:
        """``$AXIS`` sets the axis to exactly ``AXIS``, clamped below at 2."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.dimensional import _Machine

        def axis_after(program: str) -> int:
            machine = _Machine(program, ScriptedIO(""))
            while not machine.halted:
                machine.step()
            return machine.tape.axis

        assert axis_after("+.") == 2  # the default, with no $AXIS at all
        assert axis_after("$2+.") == 2
        assert axis_after("$3+.") == 3
        assert axis_after("$9+.") == 9
        # values below 2 clamp: there is no 1-pointer (a documented choice)
        assert axis_after("$1+.") == 2
        assert axis_after("$0+.") == 2

    def test_higher_axis_preserves_origin(self) -> None:
        """Moving a higher pointer away and back to the origin restores the tape."""
        program = ", $3>0$2, $3<0$2."
        assert run_and_capture(program, ["A", "B"]) == "A"

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


def test_a_hex_literal_rejects_a_sign() -> None:
    """Pins ``=HEX`` as two hex digits; ``int`` used to accept ``+1``."""
    with pytest.raises(ValueError, match="invalid hex literal"):
        run_and_capture("=+1.")


def test_a_malformed_literal_rejects_the_program_before_it_runs() -> None:
    """``=HEX`` is two hex digits; a skipped ``[=0-]`` used to halt quietly."""
    with pytest.raises(ValueError, match="invalid hex literal '0-'"):
        run_and_capture("[=0-]")
    with pytest.raises(ValueError, match="two hex digits"):
        _machine(".=")


def test_reading_memory_does_not_allocate_a_slot() -> None:
    """Pins ``memory`` as a pure view: an unvisited slot reads 0 and the
    snapshot (which freezes the tape tree) does not change."""
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.dimensional import _Machine

    machine = _Machine(">1.", ScriptedIO(""))
    machine.step()
    before = machine.snapshot()
    assert machine.memory == [0]
    assert machine.snapshot() == before


def test_memory_view_follows_a_raised_tape() -> None:
    """On a 3-level tape an unvisited slot reads 0; a written one reads back."""
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.dimensional import _Machine

    machine = _Machine("$3>1+", ScriptedIO(""))
    machine.step()
    machine.step()
    assert machine.memory == [0]
    machine.step()
    assert machine.memory == [1]


@pytest.mark.medium
def test_hints_for_bad_programs_and_input():
    assert_rejected_with_hint("Dimensional", "x", "base-16 integer", stdin="oops")


def test_dimensional_looping_run_is_detected_as_a_cycle() -> None:
    # cell starts nonzero and the loop body never changes it
    machine = Dimensional("+[]", ScriptedIO())
    assert run_until_halt_or_cycle(machine) is False
