"""Unit tests for BIO (Binary IO) interpreter."""

import io
from contextlib import redirect_stdout

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.bio import run
from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.raises import raises_message


class TestBIOBasicCommands:
    def test_increment_commands(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;1ix;", io=IO())
        assert f.getvalue() == "\x01"

        with redirect_stdout(io.StringIO()) as f:
            run("0oy;0oy;0oy;1iy;", io=IO())
        assert f.getvalue() == "\x03"

        with redirect_stdout(io.StringIO()) as f:
            run("0oz;1iz;", io=IO())
        assert f.getvalue() == "\x01"

    def test_decrement_commands(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("1ox;1ix;", io=IO())
        assert f.getvalue() == "\xff"

        with redirect_stdout(io.StringIO()) as f:
            run("0ox;1ox;1ix;", io=IO())
        assert f.getvalue() == "\x00"

    def test_case_insensitive_commands(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("0OX;1IX;", io=IO())
        assert f.getvalue() == "\x01"

        with redirect_stdout(io.StringIO()) as f:
            run("0oY;1Iy;", io=IO())
        assert f.getvalue() == "\x01"


class TestBIOWhileLoops:
    def test_simple_while_loop(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;0ix{0oy;1ox;};1iy;", io=IO())
        assert f.getvalue() == "\x01"

    def test_while_loop_skip_when_zero(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("0ix{0oy;};1iy;", io=IO())
        assert f.getvalue() == "\x00"

    def test_nested_while_loops(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;0ix{0oy;0iy{0oz;1oy;};1ox;};1iz;", io=IO())
        assert f.getvalue() == "\x01"

    def test_while_loop_with_output(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;0ox;0ix{1ix;1ox;};", io=IO())
        assert f.getvalue() == "\x02\x01"


class TestBIOEdgeCases:
    def test_line_comments_are_stripped(self) -> None:
        """``//`` runs to the end of its line, as the wiki writes it."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox; //increment x\n1ix; //print it\n", io=IO())
        assert f.getvalue() == "\x01"

    def test_loop_without_its_brace_is_rejected(self) -> None:
        """``0i?`` is only a command with the ``{`` that opens its body."""
        with pytest.raises(ValueError, match="not a command"):
            run("0ox;0ix1ox;}", io=IO())

    @pytest.mark.parametrize(
        "code",
        [
            "0ix;",  # a guard terminated by `;` instead of its `{`
            "0Iy;",  # the same, uppercase
            "0ox;0iz;",  # a guard alone, after a valid command
            "0ox{};",  # `{` on an increment, which opens nothing
            "1ix{};",  # `{` on an output command
        ],
    )
    def test_terminator_must_match_the_opcode(self, code: str) -> None:
        """Only ``0i`` takes ``{``; every other opcode takes ``;``."""
        with pytest.raises(ValueError, match="not a command"):
            run(code, io=IO())

    def test_load_error_messages_are_exact(self) -> None:
        """Each of the three load errors says exactly what it says."""
        for code, message in (
            ("0ox;invalid;1ix;", "BIO: not a command"),
            ("0ox;};1ix;", "BIO: '}' closes no loop"),
            ("0iy{0ox;", "BIO: unmatched '{'"),
        ):
            with raises_message(ValueError, message):
                run(code, io=IO())

    def test_empty_while_loop(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("0ix{};1ix;", io=IO())
        assert f.getvalue() == "\x00"


class TestBIOIntegration:
    """Integration tests for BIO interpreter."""


class TestStepMachine:
    def test_step_tracks_registers_stack_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.bio import _Machine

        machine = _Machine("0ox;0ix{1ox;};", ScriptedIO())
        assert (machine.reg, machine.stk, machine.ind) == ((0, 0, 0), (), 0)
        machine.step()  # 0ox sets x to 1
        assert machine.reg == (1, 0, 0)
        machine.step()  # 0ix sees x nonzero and pushes the loop
        assert machine.stk == (1,)
        machine.step()  # 1ox decrements x
        assert machine.reg == (0, 0, 0)
        machine.step()  # } pops the loop and lands back on the 0ix
        assert machine.stk == ()
        assert machine.ind == 1
        machine.step()  # 0ix sees x zero and skips the body
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 4

    def test_nonterminating_loop_is_detected_as_a_cycle(self) -> None:
        """A loop whose body never changes a register revisits a snapshot."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.bio import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert (
            run_until_halt_or_cycle(_Machine("0ox;0ix{0ix{};};", ScriptedIO())) is False
        )


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.register_based.bio import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "0ox;"
    halting_program = "0ox;1ix;"
    looping_program = "0ox;0ix{0ix{};};"


if __name__ == "__main__":
    pytest.main([__file__])


class TestWikiExamples:
    """The programs on the BIO wiki page, run exactly as they are written."""

    def test_hello_world(self) -> None:
        """The wiki's Hello World prints what the page says it prints."""
        program = (
            "0ox;\n" * 9
            + "0ix{                   //While block x is not 0\n"
            + "  0oy;                 //Increment the block y by 1 8 times\n" * 8
            + "  1ox;                 //Decrement block x by 1\n"
            + "};\n"
            + "1iy;                   //Output block y (H)\n"
            + "0iy{                   //Reset block y to 0\n"
            + "  1oy;\n"
            + "};\n"
            + "0ox;\n" * 10
            + "0ix{\n"
            + "  0oy;\n" * 10
            + "  1ox;\n"
            + "};\n"
            + "0oy;\n"
            + "1iy;                   //Output block y (e)\n"
        )
        with redirect_stdout(io.StringIO()) as f:
            run(program, io=IO())
        assert f.getvalue() == "He"

    def test_addition(self) -> None:
        """``0ox; 0oy; 0ix{ 1ox; 0oy; }; 1iy;`` computes 1 + 1."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox; 0oy;\n0ix{ 1ox; 0oy; };\n1iy;", io=IO())
        assert f.getvalue() == chr(2)

    def test_multiplication(self) -> None:
        """The wiki's multiplication example computes 5 * 5."""
        program = (
            "0ox; 0ox; 0ox; 0ox; 0ox;\n0ix{ 1ox; 0oy; 0oy; 0oy; 0oy; 0oy; };\n1iy;"
        )
        with redirect_stdout(io.StringIO()) as f:
            run(program, io=IO())
        assert f.getvalue() == chr(25)

    def test_subtraction_example_is_wrong_on_the_wiki(self) -> None:
        """The wiki's subtraction example adds instead of subtracting."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox; 0ox; 0oy;\n0iy{ 0ox; 1oy; };\n1ix;", io=IO())
        assert f.getvalue() == chr(3)
