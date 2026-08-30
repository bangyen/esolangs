"""Unit tests for the Dimensional v3.0 interpreter."""

import importlib
import io
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from esolangs.interpreters.io import IO
from esolangs.tools.boolean.tape import dimensional as bool_gen
from esolangs.tools.text.other import dimensional as text_gen
from tests.interpreters.contract import SnapshotContract

dim = importlib.import_module("esolangs.interpreters.tape_based.dimensional")


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        dim.run(code, IO())
    return buffer.getvalue()


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

    def test_comment_mode(self) -> None:
        """Everything between two *s is ignored."""
        assert run_and_capture("*=[.<]*+.+.+.") == "\x01\x02\x03"

    def test_coordinate_read_clear(self) -> None:
        assert run_and_capture(">0>0?0.") == "\x02"
        assert run_and_capture(">0!0?0.") == "\x00"

    def test_negative_dimension(self) -> None:
        assert run_and_capture(">~1+?~1.") == "\x01"

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
