"""Unit tests for the Point Break interpreter.

Point Break has no output, so behavior is asserted through the
halt-vs-loop convention.  The looping side is decided deterministically by
state-cycle detection: the interpreter is step-capable, and a run that
revisits its complete internal state has looped forever, so ``assert_loops``
needs no wall-clock bound at all.
"""

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.point_break import _Machine
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


def run_until_halt(program: str, stdin: str = "") -> str:
    """Run ``program``; the timeout backstop only fires if it loops."""
    return esolangs.run("Point Break", program, stdin=stdin, timeout=5)


def assert_loops(program: str, stdin: str = "") -> None:
    """Assert ``program`` loops forever, via deterministic cycle detection."""
    machine = _Machine(program, ScriptedIO(stdin))
    assert run_until_halt_or_cycle(machine) is False


class TestWikiExamples:
    """The three examples from the wiki page behave as their names say."""

    def test_infinite_loop(self) -> None:
        program = """\
LET zero:=0
POINT loop
IF zero BREAK loop
END loop"""
        assert_loops(program)

    def test_truth_machine_zero_halts(self) -> None:
        assert run_until_halt(TRUTH_MACHINE, "0") == ""

    def test_truth_machine_nonzero_loops(self) -> None:
        for value in ("1", "42", "-1"):
            assert_loops(TRUTH_MACHINE, value)

    def test_while_loop_halts_when_counter_hits_zero(self) -> None:
        for value in ("0", "1", "2", "3"):
            assert run_until_halt(WHILE_LOOP, value) == ""


class TestBreakSemantics:
    """The implicit-close reading documented in the module docstring."""

    def test_break_of_implicit_child_resumes_at_parent_end(self) -> None:
        """Breaking a child closed by an ancestor's END loops back.

        The inner loop breaks when ``n`` is nonzero, so ``n`` keeps
        growing and the outer loop never exits.
        """
        program = """\
LET n:=?
POINT outer
POINT inner
IF n BREAK inner
LET n:=n+1
END outer"""
        assert_loops(program, "0")

    def test_break_after_explicit_end_skips_the_rest_of_the_body(self) -> None:
        """Breaking an explicitly closed loop resumes after its END."""
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
        assert run_until_halt(program, "1") == ""


class TestArithmetic:
    """Arithmetic is observed through the loop-iff-zero pattern."""

    @staticmethod
    def loop_iff(expr: str, zero_when: int) -> str:
        """A program that loops forever iff ``expr`` evaluates to zero."""
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
        """A signed literal is also exercised by an in-process halting run."""
        program = "LET x:=-5+3\nPOINT loop\nIF x BREAK loop\nEND loop"
        assert run_until_halt(program) == ""

    def test_floor_division_in_process(self) -> None:
        """Floor division is also exercised by an in-process halting run."""
        program = "LET x:=9/2\nPOINT loop\nIF x BREAK loop\nEND loop"
        assert run_until_halt(program) == ""

    def test_input_in_expression(self) -> None:
        assert_loops(
            "LET x:=?*2\nLET d:=x-8\nPOINT loop\nIF d BREAK loop\nEND loop", "4"
        )

    def test_different_value_halts(self) -> None:
        assert run_until_halt(self.loop_iff("2+3*4", 20)) == ""


class TestErrors:
    def test_undefined_variable_in_let(self) -> None:
        with pytest.raises(HaltError, match="undefined variable"):
            esolangs.run("Point Break", "LET x:=y")

    def test_undefined_variable_in_if(self) -> None:
        with pytest.raises(HaltError, match="undefined variable"):
            esolangs.run("Point Break", "POINT loop\nIF x BREAK loop\nEND loop")

    def test_division_by_zero(self) -> None:
        with pytest.raises(HaltError, match="division by zero"):
            esolangs.run("Point Break", "LET x:=1/0")

    def test_exhausted_input(self) -> None:
        with pytest.raises(EOFError):
            esolangs.run("Point Break", "LET x:=?")

    @pytest.mark.parametrize(
        "program",
        [
            "LET x=1",  # single = instead of :=
            "LET x:",  # unterminated assignment
            "LET x:=",  # missing expression
            "LET x:=1+",  # trailing operator
            "LET x:=1 2",  # two operands in a row
            "LET x:=1**2",  # two operators in a row
            "LET x:=-",  # lone sign
            "LET 5:=1",  # numeric variable name
            "LET x:=5!",  # stray character
            "LET X:=1",  # uppercase variable
            "POINT",  # missing label
            "POINT 5",  # numeric label
            "IF x BREAK",  # missing label
            "IF x GOTO loop",  # unknown keyword
            "BREAK x",  # not a statement
            "END loop",  # END with no open loop
            "POINT a\nPOINT a\nEND a\nEND a",  # duplicate label
            "POINT a\nEND b",  # END for an unopened loop
            "POINT a\nIF x BREAK b\nEND a",  # BREAK outside its loop
            "POINT a\nEND a\nPOINT b",  # unclosed loop
        ],
    )
    def test_malformed_program(self, program: str) -> None:
        with pytest.raises(
            ValueError,
            match=r"malformed|duplicate|unclosed|unknown|unexpected|outside|open loop",
        ):
            esolangs.run("Point Break", program)


class TestComments:
    def test_comment_only_program_halts(self) -> None:
        assert run_until_halt("# nothing but comments") == ""

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
        assert run_until_halt("") == ""

    def test_blank_lines_are_ignored(self) -> None:
        assert run_until_halt("\n\nLET zero:=0\n\n") == ""

    def test_program_as_string_and_lines(self) -> None:
        """A program is accepted as one string or as a list of lines, and
        the two forms reach the same final state -- otherwise the split is
        doing something the joined form is not."""
        joined = _Machine("LET zero:=0\nLET one:=1", ScriptedIO())
        split = _Machine(["LET zero:=0", "LET one:=1"], ScriptedIO())

        assert run_until_halt_or_cycle(joined) is True
        assert run_until_halt_or_cycle(split) is True
        assert joined.snapshot() == split.snapshot()
