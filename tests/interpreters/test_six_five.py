import importlib

from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.interpreters.runner import run_program

sixfive = importlib.import_module("esolangs.interpreters.tape_based.six_five")


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    return run_program(sixfive.run, code, "".join(f"{line}\n" for line in inputs or []))


HELLO_WORLD = "\n".join(
    [
        "666666666666A C",
        "66665A C",
        "662AA C",
        "626262A C",
        "9999999999995A C",
        "99A C",
        "55555555555A C",
        "6666A C",
        "626262A C",
        "9A C",
        "95959A C",
    ]
)


class TestSixFive:
    def test_add_six(self) -> None:
        assert run_and_capture("66666666A0") == "0"

    def test_input_echo(self) -> None:
        assert run_and_capture("BA0", inputs=["X"]) == "X"

    def test_hello_world(self) -> None:
        assert run_and_capture(HELLO_WORLD) == "Hello, World"

    def test_right_move_reuses_an_already_allocated_tape(self) -> None:
        """Moving right need not grow a tape that a prior state already grew."""
        state = sixfive._advance((0, 0, (0, 0, 0)), ["1"])  # noqa: SLF001
        assert state == (1, 2, (0, 0, 0))

    def test_the_conditional_skip_only_fires_on_a_match(self) -> None:
        """``7n`` skips the next instruction when the cell holds ``n``."""
        assert run_and_capture("70A0") == ""
        assert run_and_capture("6666666671A0") == "0"

    def test_a_jump_to_a_missing_label_falls_through(self) -> None:
        """``8n`` scans for the nth ``4``; with none there, nothing happens."""
        assert run_and_capture("8166666666A0") == "0"
        assert run_and_capture("66666666A0") == "0"

    def test_the_two_moves_are_different_sizes(self) -> None:
        """``1`` goes right by two, ``3`` left by one, and the tape follows."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.six_five import _Machine

        # 1 lands on cell 2, growing the tape to three; 3 steps back to 1
        machine = _Machine("166666666A366666666A0", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == "00"
        assert (machine.cell, machine.tape) == (1, (0, 48, 48))

        # two moves right compound rather than landing on a fixed cell
        twice = _Machine("11", ScriptedIO())
        while not twice.halted:
            twice.step()
        assert (twice.cell, len(twice.tape)) == (4, 5)

    def test_zero_halts_before_the_rest_of_the_program(self) -> None:
        """``0`` halts, so nothing after it runs."""
        assert run_and_capture("066666666A0") == ""

    def test_negative_cell_output_halts(self) -> None:
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture("2A")

    def test_the_printable_range_ends_at_the_last_codepoint(self) -> None:
        """Both ends of the ``A`` guard, at the value that separates them."""
        import pytest

        from esolangs.exceptions import HaltError

        assert run_and_capture("BA0", inputs=["\U0010ffff"]) == "\U0010ffff"
        with pytest.raises(HaltError):
            # 6 then 5 lands one past the last codepoint
            run_and_capture("B62A", inputs=["\U0010ffff"])

    def test_the_left_move_is_relative_to_where_the_pointer_is(self) -> None:
        """``3`` steps back one, rather than landing on a fixed cell."""
        assert run_and_capture("1366666666113A0") == "\x00"

    def test_left_of_cell_zero_is_a_fresh_zero_cell(self) -> None:
        """``3`` at cell 0 grows the tape left; ``1`` then lands past start."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.six_five import _Machine

        # 8 on the start cell, then 3 grows a zero cell and prints it
        assert run_and_capture("66666666366666666A0") == "0"
        # 3 3 grows two cells; 1 moves two right, back onto the start cell
        machine = _Machine("66666666331A0", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == "0"
        assert (machine.cell, machine.tape) == (2, (0, 0, 48))

    def test_a_marker_jump_with_no_operand_does_nothing(self) -> None:
        """A trailing ``8`` has no operand, so its target count is zero."""
        assert run_and_capture("4A8") == "\x00"

    def test_the_marker_index_is_the_scan_taken_once(self) -> None:
        """``8n`` lands where a scan for the n-th ``4`` would, from the index."""
        from esolangs.interpreters.io import ScriptedIO

        machine = sixfive._Machine("4A82A40", ScriptedIO(""))  # noqa: SLF001
        assert machine.markers == (0, 4)
        toks = machine.toks
        jumped = sixfive._advance((2, 0, (0,)), toks)  # noqa: SLF001
        assert jumped == sixfive._advance((2, 0, (0,)), toks, None, machine.markers)  # noqa: SLF001
        assert jumped[0] == 5
        assert sixfive._marker(machine.markers, 3) is None  # noqa: SLF001
        assert sixfive._marker(machine.markers, 0) is None  # noqa: SLF001

    def test_a_conditional_skip_with_no_operand_does_nothing(self) -> None:
        """The same for a trailing ``7``: no operand, so nothing to read."""
        assert run_and_capture("A7") == "\x00"


class TestComments:
    """``C`` starts a comment, unless it is the operand of a ``7`` or ``8``."""

    def test_a_comment_hides_the_rest_of_its_line(self) -> None:
        # without the strip, the commented-out program would run and print
        assert run_and_capture("6C66666666A0") == ""
        assert run_and_capture("66666666A0C66666666A0") == "0"

    def test_a_comment_ends_at_the_newline(self) -> None:
        assert run_and_capture("6C hidden\n66666666A0") == "6"

    def test_a_comment_on_the_first_line(self) -> None:
        """The ``C`` may be the program's first character."""
        from esolangs.interpreters.tape_based.six_five import _tokens

        assert _tokens("C hidden") == []
        assert run_and_capture("C66666666A0\n66666666A0") == "0"

    def test_c_after_a_skip_is_its_operand(self) -> None:
        """A ``C`` following ``7``/``8`` is the value 12, not a comment."""
        assert run_and_capture("667C66666666A0") == "6"

    def test_the_tokenizer_pairs_an_operand_with_its_skip(self) -> None:
        """Directly, because the pairing is invisible in the output."""
        from esolangs.interpreters.tape_based.six_five import _tokens

        assert _tokens("7C") == ["7C"]
        assert _tokens("78") == ["78"]
        assert _tokens("7") == ["7"]
        assert _tokens("8") == ["8"]
        assert _tokens("7C1") == ["7C", "1"]
        assert _tokens("6C hidden") == ["6"]
        # Only 7 and 8 take an operand; a non-instruction is no token at all.
        assert _tokens("X6") == ["6"]
        assert run_and_capture("X66666666A0") == "0"

    def test_a_skip_passes_over_blanks_to_the_next_instruction(self) -> None:
        """``7n`` "skips the next instruction"; a blank or comment is none."""
        assert run_and_capture("70 6A") == "\x00"
        assert run_and_capture("70C note\n6A") == "\x00"
        assert run_and_capture("70X6A") == "\x00"


class TestStepMachine:
    def test_step_tracks_tape_cell_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.six_five import _Machine

        machine = _Machine("55A", ScriptedIO())
        assert (machine.ind, machine.cell, machine.tape) == (0, 0, (0,))
        machine.step()  # 5 adds 5 to the cell
        assert machine.tape == (5,)
        machine.step()  # 5 adds 5 more
        assert machine.tape == (10,)
        machine.step()  # A prints the cell
        assert machine.io.getvalue() == "\n"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 3

    def test_an_operandless_skip_still_moves_the_cursor_past_one_token(
        self,
    ) -> None:
        """A bare ``7`` compares against zero and skips on a match."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.six_five import _Machine

        machine = _Machine("7", ScriptedIO())
        machine.step()
        assert (machine.ind, machine.halted) == (2, True)

    def test_a_marker_jump_lands_past_the_marker_it_found(self) -> None:
        """``8n`` leaves the cursor after the ``4``, not on it."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.six_five import _Machine

        machine = _Machine("81A4A0", ScriptedIO())
        machine.step()  # 81 jumps to just after the first 4
        assert machine.ind == 3


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.six_five import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "55A"
    halting_program = "55A"
    looping_program = "481"


def test_a_comment_after_a_seven_eight_pair_is_still_a_comment() -> None:
    """Pins operand-adjacent comments: in ``78C`` the 8 is 7's operand, so
    the ``C`` starts a comment and the trailing ``A`` never prints twice."""
    assert run_and_capture("666666666666A78CA\n") == "H"
