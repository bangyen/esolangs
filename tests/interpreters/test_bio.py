"""Unit tests for BIO (Binary IO) interpreter.

Tests cover all BIO commands, edge cases, and example programs from esolangs.org.
"""

import io
from contextlib import redirect_stdout

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.bio import run
from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.raises import raises_message


class TestBIOBasicCommands:
    """Test basic BIO command functionality."""

    def test_increment_commands(self) -> None:
        """Test 0O[xyz] increment commands."""
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
        """Test 1O[xyz] decrement commands."""
        with redirect_stdout(io.StringIO()) as f:
            run("1ox;1ix;", io=IO())
        assert f.getvalue() == "\xff"

        with redirect_stdout(io.StringIO()) as f:
            run("0ox;1ox;1ix;", io=IO())
        assert f.getvalue() == "\x00"

    def test_output_commands(self) -> None:
        """Test 1I[xyz] output commands."""
        with redirect_stdout(io.StringIO()) as f:
            run("1ix;", io=IO())
        assert f.getvalue() == "\x00"

        with redirect_stdout(io.StringIO()) as f:
            run("0oy;1iy;", io=IO())
        assert f.getvalue() == "\x01"

        with redirect_stdout(io.StringIO()) as f:
            run("0oz;" * 10 + "1iz;", io=IO())  # 10 increments = ASCII 10 (newline)
        assert f.getvalue() == "\n"

    def test_case_insensitive_commands(self) -> None:
        """Test that BIO commands are case-insensitive."""
        with redirect_stdout(io.StringIO()) as f:
            run("0OX;1IX;", io=IO())
        assert f.getvalue() == "\x01"

        with redirect_stdout(io.StringIO()) as f:
            run("0oY;1Iy;", io=IO())
        assert f.getvalue() == "\x01"

    def test_register_independence(self) -> None:
        """Test that registers x, y, z are independent."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;0oy;0oz;1ix;1iy;1iz;", io=IO())
        assert f.getvalue() == "\x01\x01\x01"


class TestBIOWhileLoops:
    """Test BIO while loop functionality (0I[xyz] commands)."""

    def test_simple_while_loop(self) -> None:
        """Test a simple while loop that executes once."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;0ix{0oy;1ox;};1iy;", io=IO())
        assert f.getvalue() == "\x01"

    def test_while_loop_skip_when_zero(self) -> None:
        """Test that while loop is skipped when register is zero."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ix{0oy;};1iy;", io=IO())
        assert f.getvalue() == "\x00"

    def test_nested_while_loops(self) -> None:
        """Test nested while loops."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;0ix{0oy;0iy{0oz;1oy;};1ox;};1iz;", io=IO())
        assert f.getvalue() == "\x01"

    def test_while_loop_with_output(self) -> None:
        """Test while loop that outputs characters."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;0ox;0ix{1ix;1ox;};", io=IO())
        assert f.getvalue() == "\x02\x01"


class TestBIOMathematicalOperations:
    """Test BIO mathematical operations from esolangs.org examples."""

    def test_addition(self) -> None:
        """Test addition: 0ox; 0oy; 0ix{ 1ox; 0oy; }; 1iy;"""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;0oy;0ix{1ox;0oy;};1iy;", io=IO())
        assert f.getvalue() == "\x02"  # 1 + 1 = 2

    def test_subtraction(self) -> None:
        """Test subtraction: 0ox; 0ox; 0oy; 0iy{ 0ox; 1oy; }; 1ix;"""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;" * 2 + "0oy;0iy{0ox;1oy;};1ix;", io=IO())
        assert (
            f.getvalue() == "\x03"
        )  # 2 + 1 = 3 (this is actually addition, not subtraction)

    def test_multiplication(self) -> None:
        """Test multiplication: 0ox; 0ox; 0ox; 0ox; 0ox;
        0ix{ 1ox; 0oy; 0oy; 0oy; 0oy; 0oy; }; 1iy;"""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;" * 5 + "0ix{1ox;" + "0oy;" * 5 + "};1iy;", io=IO())
        assert f.getvalue() == "\x19"  # 5 * 5 = 25

    def test_complex_calculation(self) -> None:
        """Test a more complex calculation."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;" * 3 + "0ix{1ox;0oy;0oy;};1iy;", io=IO())
        assert f.getvalue() == "\x06"


class TestBIOHelloWorld:
    """Test BIO Hello World program from esolangs.org."""

    def test_hello_world_program(self) -> None:
        """Test the complete Hello World program from esolangs.org."""
        # This is a simplified version of the Hello World program
        # The full program is very long, so we test the pattern for generating 'H'
        hello_world_code = (
            "0ox;" * 9
            + "0ix{"
            + "0oy;" * 8
            + "1ox;};"
            + "1iy;"
            + "0iy{1oy;};"
            + "0ox;" * 10
            + "0ix{"
            + "0oy;" * 10
            + "1ox;};"
            + "0oy;1iy;"
            + "0iy{1oy;};"
        )

        with redirect_stdout(io.StringIO()) as f:
            run(hello_world_code, io=IO())
        assert f.getvalue() == "He"

    def test_character_generation_pattern(self) -> None:
        """Test the pattern for generating specific ASCII characters."""
        # Generate 'A' (ASCII 65)
        # 65 = 8*8 + 1, so we need 8 increments, then 8*8 in loop, then 1 more
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;" * 8 + "0ix{" + "0oy;" * 8 + "1ox;};0oy;1iy;", io=IO())
        assert f.getvalue() == "A"


class TestBIOEdgeCases:
    """Test BIO edge cases and error conditions."""

    def test_empty_program(self) -> None:
        """Test that empty program produces no output."""
        with redirect_stdout(io.StringIO()) as f:
            run("", io=IO())
        assert f.getvalue() == ""

    def test_whitespace_only(self) -> None:
        """Test that whitespace-only program produces no output."""
        with redirect_stdout(io.StringIO()) as f:
            run("   \n\t  ", io=IO())
        assert f.getvalue() == ""

    def test_invalid_commands_rejected(self) -> None:
        """Text that is not a command is a load error, not something skipped.

        The interpreter used to keep the regex's matches and drop whatever
        else was there, so a typo ran as a different program.  BIO defines
        no comment syntax but ``//``, so anything else must be rejected.
        """
        with pytest.raises(ValueError, match="not a command"):
            run("0ox;invalid;1ix;", io=IO())

    def test_line_comments_are_stripped(self) -> None:
        """``//`` runs to the end of its line, as the wiki writes it."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox; //increment x\n1ix; //print it\n", io=IO())
        assert f.getvalue() == "\x01"

    def test_loop_without_its_brace_is_rejected(self) -> None:
        """``0i?`` is only a command with the ``{`` that opens its body."""
        with pytest.raises(ValueError, match="not a command"):
            run("0ox;0ix1ox;}", io=IO())

    def test_stray_closing_brace_is_rejected(self) -> None:
        """A ``}`` with no loop to close is malformed."""
        with pytest.raises(ValueError, match="closes no loop"):
            run("0ox;};1ix;", io=IO())

    def test_load_error_messages_are_exact(self) -> None:
        """Each of the three load errors says exactly what it says.

        Every case above uses ``match=``, which is a substring search, so
        the wording around the matched fragment was free -- the language
        prefix could be dropped or recased and nothing would notice.  All
        three messages come from ``parse``, so they are pinned together.
        """
        for code, message in (
            ("0ox;invalid;1ix;", "BIO: not a command"),
            ("0ox;};1ix;", "BIO: '}' closes no loop"),
            ("0iy{0ox;", "BIO: unmatched '{'"),
        ):
            with raises_message(ValueError, message):
                run(code, io=IO())

    def test_negative_register_values(self) -> None:
        """Test handling of negative register values."""
        with redirect_stdout(io.StringIO()) as f:
            run("1ox;1ix;", io=IO())
        assert f.getvalue() == "\xff"

    def test_large_register_values(self) -> None:
        """Test handling of large register values."""
        large_code = "0ox;" * 300 + "1ix;"  # 300 increments
        with redirect_stdout(io.StringIO()) as f:
            run(large_code, io=IO())
        assert f.getvalue() == chr(300 % 256)

    def test_unmatched_while_loop(self) -> None:
        """A loop without its closing brace is a malformed program."""
        import pytest

        with pytest.raises(ValueError, match="unmatched"):
            run("0iy{0ox;", io=IO())  # Missing closing brace

    def test_empty_while_loop(self) -> None:
        """Test empty while loop that doesn't execute."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ix{};1ix;", io=IO())
        assert f.getvalue() == "\x00"

    def test_unclosed_loop_skipped(self) -> None:
        """A loop skipped when its register is zero with no closer is malformed."""
        import pytest

        with pytest.raises(ValueError, match="unmatched"):
            run("0iy{0ox;", io=IO())

    def test_while_loop_with_zero_register(self) -> None:
        """Test while loop when register is already zero."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ix{0oy;};1iy;", io=IO())
        assert f.getvalue() == "\x00"


class TestBIOIntegration:
    """Integration tests for BIO interpreter."""

    def test_complex_program(self) -> None:
        """Test a complex BIO program with multiple operations."""
        complex_code = (
            "0ox;" * 3  # x = 3
            + "0oy;" * 2  # y = 2
            + "0ix{"  # while x > 0
            + "0oz;"  # increment z
            + "1ox;"  # decrement x
            + "};"
            + "1iz;"  # output z (should be 3)
        )

        with redirect_stdout(io.StringIO()) as f:
            run(complex_code, io=IO())
        assert f.getvalue() == "\x03"

    def test_register_reset_pattern(self) -> None:
        """Test the common pattern of resetting registers to zero."""
        with redirect_stdout(io.StringIO()) as f:
            run("0oy;" * 3 + "0iy{1oy;};1iy;", io=IO())
        assert f.getvalue() == "\x00"

    def test_character_arithmetic(self) -> None:
        """Test character arithmetic operations."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;" * 66 + "1ix;", io=IO())  # 66 = 'B'
        assert f.getvalue() == "B"


class TestStepMachine:
    def test_step_tracks_registers_stack_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.bio import _Machine

        machine = _Machine("0ox;0ix{1ox;};", ScriptedIO())
        assert (machine.reg, machine.stk, machine.ind) == ([0, 0, 0], [], 0)
        machine.step()  # 0ox sets x to 1
        assert machine.reg == [1, 0, 0]
        machine.step()  # 0ix sees x nonzero and pushes the loop
        assert machine.stk == [1]
        machine.step()  # 1ox decrements x
        assert machine.reg == [0, 0, 0]
        machine.step()  # } pops the loop and lands back on the 0ix
        assert machine.stk == []
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
    """The programs on the BIO wiki page, run exactly as they are written.

    These are the language's ground truth: each is copied verbatim from
    esolangs.org, comments and ``;`` terminators and all, so a change to
    what the interpreter accepts has to keep them running.  The interpreter
    used to drop everything its regex did not match, which meant it ran
    these programs by ignoring most of their punctuation rather than by
    understanding it.
    """

    def test_hello_world(self) -> None:
        """The wiki's Hello World prints what the page says it prints.

        Abridged to the first two letters -- the full program is 290 lines
        of the same three shapes, and the sync-tested generator covers the
        long form.  The reset loop between letters is the part worth
        keeping: it is where a mis-parsed brace would show up.
        """
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
        """The wiki's subtraction example adds instead of subtracting.

        ``0ox; 0ox; 0oy; 0iy{ 0ox; 1oy; }; 1ix;`` drains ``y`` into ``x``,
        so it prints ``2 + 1`` rather than the ``2 - 1`` its heading
        claims.  The page invites corrections, so this is an error in the
        example and not in the interpreter -- recorded here so the 3 is
        not mistaken for a regression later.
        """
        with redirect_stdout(io.StringIO()) as f:
            run("0ox; 0ox; 0oy;\n0iy{ 0ox; 1oy; };\n1ix;", io=IO())
        assert f.getvalue() == chr(3)
