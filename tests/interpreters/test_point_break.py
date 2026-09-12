r"""Unit tests for the Point Break interpreter."""

import re

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.point_break import _Machine, run
from esolangs.vm import run_until_halt_or_cycle

TRUTH_MACHINE = """\
LET n:=?
LET one:=1
POINT truth
POINT check
IF n BREAK check
IF one BREAK truth
END truth"""

WHILE_LOOP = """\
LET n:=?
LET constantone:=1
POINT while
POINT check
IF n BREAK check
IF constantone BREAK while
END check
LET n:=n-1
END while"""


def assert_halts(program: str, stdin: str = "") -> None:
    r"""Assert ``program`` halts, via deterministic cycle detection."""
    machine = _Machine(program, ScriptedIO(stdin))
    assert run_until_halt_or_cycle(machine) is True


def assert_loops(program: str, stdin: str = "") -> None:
    r"""Assert ``program`` loops forever, via deterministic cycle detection."""
    machine = _Machine(program, ScriptedIO(stdin))
    assert run_until_halt_or_cycle(machine) is False


def run_and_capture(program: str, stdin: str = "") -> str:
    r"""Run ``program`` through :func:`run` and return what it wrote."""
    io = ScriptedIO(stdin)
    run(program, io)
    return io.getvalue()


class TestTheVariableDump:
    r"""The end-of-run dump: what it prints, when, and exactly once."""

    def test_the_dump_prints_the_variables_in_name_order(self) -> None:
        assert run_and_capture("LET b:=2\nLET a:=1") == "1 2"

    def test_the_dump_separates_variables_with_a_space(self) -> None:
        assert run_and_capture("LET a:=1\nLET b:=2") == "1 2"

    def test_a_program_with_one_variable_dumps_just_it(self) -> None:
        assert run_and_capture("LET zero:=0") == "0"

    def test_the_dump_fires_once_however_often_a_halted_machine_is_stepped(
        self,
    ) -> None:
        io = ScriptedIO("")
        machine = _Machine("LET a:=1\nLET b:=2", io)
        while not machine.halted:
            machine.step()
        assert io.getvalue() == ""  # the dump is the next step's.
        machine.step()
        assert io.getvalue() == "1 2"
        machine.step()
        machine.step()
        assert io.getvalue() == "1 2"  # and not once more.


class TestWikiExamples:
    r"""The three examples from the wiki page behave as their names say."""

    def test_infinite_loop(self) -> None:
        program = """\
LET zero:=0
POINT loop
IF zero BREAK loop
END loop"""
        assert_loops(program)

    def test_truth_machine_zero_halts(self) -> None:
        assert_halts(TRUTH_MACHINE, "0")

    def test_truth_machine_nonzero_loops(self) -> None:
        for value in ("1", "42", "-1"):
            assert_loops(TRUTH_MACHINE, value)

    def test_while_loop_halts_when_counter_hits_zero(self) -> None:
        for value in ("0", "1", "2", "3"):
            assert_halts(WHILE_LOOP, value)


class TestBreakSemantics:
    r"""The implicit-close reading documented in the module docstring."""

    def test_break_of_implicit_child_resumes_at_parent_end(self) -> None:
        r"""Breaking a child closed by an ancestor's END loops back."""
        program = """\
LET n:=?
POINT outer
POINT inner
IF n BREAK inner
LET n:=n+1
END outer"""
        assert_loops(program, "0")

    def test_break_after_explicit_end_skips_the_rest_of_the_body(self) -> None:
        r"""Breaking an explicitly closed loop resumes after its END."""
        program = """\
LET n:=?
LET one:=1
POINT outer
POINT inner
IF n BREAK inner
LET n:=n+1
END inner
IF one BREAK outer
END outer"""
        assert_halts(program, "1")

    def test_one_end_closes_every_loop_below_it(self) -> None:
        r"""An ``END`` records a close for each descendant, not just one."""
        program = """\
LET n:=?
POINT a
POINT b
POINT c
IF n BREAK b
END a"""
        assert_loops(program, "1")


class TestArithmetic:
    r"""Arithmetic is observed through the loop-iff-zero pattern."""

    @staticmethod
    def loop_iff(expr: str, zero_when: int) -> str:
        r"""A program that loops forever iff ``expr`` evaluates to zero."""
        return (
            f"LET x:={expr}\n"
            f"LET d:=x-{zero_when}\n"
            "POINT loop\n"
            "IF d BREAK loop\n"
            "END loop"
        )

    def test_precedence(self) -> None:
        assert_loops(self.loop_iff("2+3*4", 14))

    def test_left_associativity(self) -> None:
        assert_loops(self.loop_iff("10-4-3", 3))

    def test_division(self) -> None:
        assert_loops(self.loop_iff("10/2", 5))

    def test_division_is_floor(self) -> None:
        assert_loops(self.loop_iff("9/2", 4))

    def test_signed_literal(self) -> None:
        assert_loops(self.loop_iff("-5+3", -2))

    def test_signed_literal_in_process(self) -> None:
        r"""A signed literal is also exercised by an in-process halting run."""
        program = "LET x:=-5+3\nPOINT loop\nIF x BREAK loop\nEND loop"
        assert_halts(program)

    def test_floor_division_in_process(self) -> None:
        r"""Floor division is also exercised by an in-process halting run."""
        program = "LET x:=9/2\nPOINT loop\nIF x BREAK loop\nEND loop"
        assert_halts(program)

    def test_input_in_expression(self) -> None:
        assert_loops(
            "LET x:=?*2\nLET d:=x-8\nPOINT loop\nIF d BREAK loop\nEND loop", "4"
        )

    def test_different_value_halts(self) -> None:
        assert_halts(self.loop_iff("2+3*4", 20))


class TestTokens:
    r"""Where one token stops and the next begins."""

    @staticmethod
    def loop_on(program: str) -> str:
        r"""Append a loop that runs forever iff ``x`` is zero."""
        return f"{program}\nPOINT loop\nIF x BREAK loop\nEND loop"

    @pytest.mark.parametrize("literal", ["+0", "+9", "-50", "-59", "-1", "-123"])
    def test_signed_literal_digit_ends(self, literal: str) -> None:
        r"""A signed literal scans every digit, ``0`` and ``9`` included."""
        value = int(literal)
        assert_loops(self.loop_on(f"LET x:={literal}\nLET x:=x-{value}"))

    def test_keyword_run_stops_at_the_first_lowercase_letter(self) -> None:
        r"""A keyword needs no space before the name that follows it."""
        assert_halts(self.loop_on("LETx:=1"))

    def test_variable_name_spans_the_whole_lowercase_range(self) -> None:
        r"""``a`` and ``z`` are names, not unexpected characters."""
        assert_halts(self.loop_on("LET a:=1\nLET z:=1\nLET x:=a*z"))


class TestErrors:
    r"""Rejections, asserted by their exact text."""

    def test_undefined_variable_in_let(self) -> None:
        with pytest.raises(HaltError) as caught:
            run("LET x:=y", ScriptedIO())
        assert str(caught.value) == "undefined variable 'y'"

    def test_undefined_variable_in_if(self) -> None:
        with pytest.raises(HaltError) as caught:
            run("POINT loop\nIF x BREAK loop\nEND loop", ScriptedIO())
        assert str(caught.value) == "undefined variable 'x'"

    def test_division_by_zero(self) -> None:
        with pytest.raises(HaltError) as caught:
            run("LET x:=1/0", ScriptedIO())
        assert str(caught.value) == "division by zero"

    def test_exhausted_input(self) -> None:
        with pytest.raises(EOFError):
            run("LET x:=?", ScriptedIO())

    @pytest.mark.parametrize(
        ("program", "message"),
        [
            ("LET x=1", "unexpected character '='"),  # single = instead of :=.
            ("LET x:", "malformed assignment operator (expected ':=')"),
            ("LET x:=", "malformed statement"),  # missing expression.
            ("LET x:=1+", "malformed expression"),  # trailing operator.
            ("LET x:=1 2", "malformed expression"),  # two operands in a row.
            ("LET x:=1**2", "malformed expression"),  # two operators in a row.
            ("LET x:=-", "malformed expression"),  # lone sign.
            ("LET 5:=1", "malformed statement"),  # numeric variable name.
            ("LET x:=5!", "unexpected character '!'"),  # stray character.
            ("LET X:=1", "unknown keyword 'X'"),  # uppercase variable.
            ("LET Z:=1", "unknown keyword 'Z'"),  # the last uppercase letter.
            ("A", "unknown keyword 'A'"),  # the first uppercase letter.
            ("LET x:=1A", "unknown keyword 'A'"),  # a letter glued to a number.
            ("LET aZ:=1", "unknown keyword 'Z'"),  # a letter glued to a name.
            ("LET x:=-1A", "unknown keyword 'A'"),  # a letter glued to a sign.
            ("LET x:=[", "unexpected character '['"),  # between 'Z' and 'a'.
            ("LET x:=_", "unexpected character '_'"),  # likewise.
            ("LET x:=`", "unexpected character '`'"),  # and just below 'a'.
            ("x y", "malformed statement"),  # two names, no keyword.
            ("POINT", "malformed statement"),  # missing label.
            ("POINT 5", "malformed statement"),  # numeric label.
            ("IF x BREAK", "malformed statement"),  # missing label.
            ("IF x GOTO loop", "unknown keyword 'GOTO'"),
            ("BREAK x", "malformed statement"),  # not a statement.
            ("END loop", "no open loop 'loop'"),  # END with no open loop.
            ("POINT a\nPOINT a\nEND a\nEND a", "duplicate loop label 'a'"),
            ("POINT a\nEND b", "no open loop 'b'"),  # END for an unopened loop.
            ("POINT a\nIF x BREAK b\nEND a", "BREAK b outside its loop"),
            ("POINT a\nEND a\nPOINT b", "unclosed loop 'b'"),  # unclosed loop.
        ],
    )
    def test_malformed_program(self, program: str, message: str) -> None:
        with pytest.raises(ValueError, match=re.escape(message)) as caught:
            run(program, ScriptedIO())
        assert str(caught.value) == message


class TestComments:
    def test_comment_only_program_halts(self) -> None:
        assert_halts("# nothing but comments")

    def test_inline_comment(self) -> None:
        program = (
            "LET zero:=0 # trailing comment\nPOINT loop\nIF zero BREAK loop\nEND loop"
        )
        assert_loops(program)

    def test_comment_within_loop(self) -> None:
        program = (
            "LET zero:=0\nPOINT loop\nIF zero BREAK loop\n# a comment line\nEND loop"
        )
        assert_loops(program)


class TestProgramShape:
    def test_empty_program_halts(self) -> None:
        assert_halts("")

    def test_blank_lines_are_ignored(self) -> None:
        assert_halts("\n\nLET zero:=0\n\n")

    def test_program_as_string_and_lines(self) -> None:
        r"""A program is accepted as one string or as a list of lines, and the."""
        joined = _Machine("LET zero:=0\nLET one:=1", ScriptedIO())
        split = _Machine(["LET zero:=0", "LET one:=1"], ScriptedIO())

        assert run_until_halt_or_cycle(joined) is True
        assert run_until_halt_or_cycle(split) is True
        assert joined.snapshot() == split.snapshot()
