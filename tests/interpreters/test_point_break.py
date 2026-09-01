"""Unit tests for the Point Break interpreter.

Point Break has no output, so behavior is asserted through the
halt-vs-loop convention.  Both sides are decided deterministically by
state-cycle detection: the interpreter is step-capable, and a run that
revisits its complete internal state has looped forever, so neither
``assert_halts`` nor ``assert_loops`` needs a wall-clock bound at all.
"""

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
    """Assert ``program`` halts, via deterministic cycle detection."""
    machine = _Machine(program, ScriptedIO(stdin))
    assert run_until_halt_or_cycle(machine) is True


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
        assert_halts(TRUTH_MACHINE, "0")

    def test_truth_machine_nonzero_loops(self) -> None:
        for value in ("1", "42", "-1"):
            assert_loops(TRUTH_MACHINE, value)

    def test_while_loop_halts_when_counter_hits_zero(self) -> None:
        for value in ("0", "1", "2", "3"):
            assert_halts(WHILE_LOOP, value)


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
        assert_halts(program, "1")

    def test_one_end_closes_every_loop_below_it(self) -> None:
        """An ``END`` records a close for each descendant, not just one.

        Three loops are open when ``END a`` arrives, so it has to close
        ``b`` and ``c`` as well as ``a``.  A walk that starts one frame too
        early or too late leaves a descendant with no recorded ``END``, and
        breaking to it then finds nothing to resume at.
        """
        program = """\
LET n:=?
POINT a
POINT b
POINT c
IF n BREAK b
END a"""
        assert_loops(program, "1")


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
        assert_halts(program)

    def test_floor_division_in_process(self) -> None:
        """Floor division is also exercised by an in-process halting run."""
        program = "LET x:=9/2\nPOINT loop\nIF x BREAK loop\nEND loop"
        assert_halts(program)

    def test_input_in_expression(self) -> None:
        assert_loops(
            "LET x:=?*2\nLET d:=x-8\nPOINT loop\nIF d BREAK loop\nEND loop", "4"
        )

    def test_different_value_halts(self) -> None:
        assert_halts(self.loop_iff("2+3*4", 20))


class TestTokens:
    """Where one token stops and the next begins.

    Every scan in the tokenizer is a character range, and a range whose
    endpoint moves by one letter or digit is not a wrong answer but a
    differently-shaped token stream -- a name that becomes an unexpected
    character, a keyword that swallows the name after it, a signed literal
    that splits into a stray operator and a number.  Those endpoints are
    what these programs stand on.
    """

    @staticmethod
    def loop_on(program: str) -> str:
        """Append a loop that runs forever iff ``x`` is zero."""
        return f"{program}\nPOINT loop\nIF x BREAK loop\nEND loop"

    @pytest.mark.parametrize("literal", ["+0", "+9", "-50", "-59", "-1", "-123"])
    def test_signed_literal_digit_ends(self, literal: str) -> None:
        """A signed literal scans every digit, ``0`` and ``9`` included.

        Two separate ranges are involved -- the one deciding a sign
        *starts* a literal, and the one consuming the digits after it -- so
        each endpoint appears both as a first digit and as a later one.  A
        bound that excludes one splits the literal into a stray operator
        and a number, which is a malformed expression rather than a wrong
        value.
        """
        value = int(literal)
        assert_loops(self.loop_on(f"LET x:={literal}\nLET x:=x-{value}"))

    def test_keyword_run_stops_at_the_first_lowercase_letter(self) -> None:
        """A keyword needs no space before the name that follows it.

        The uppercase scan is bounded above by ``Z``; raised to ``z`` it
        swallows the name too, and ``LETx`` becomes one unknown keyword
        rather than ``LET`` followed by ``x``.
        """
        assert_halts(self.loop_on("LETx:=1"))

    def test_variable_name_spans_the_whole_lowercase_range(self) -> None:
        """``a`` and ``z`` are names, not unexpected characters.

        The name scan is bounded at both ends, and either bound moving in
        by one letter turns a name into a character the tokenizer has no
        rule for -- so the endpoints are used as whole names here rather
        than only in the middle of one.
        """
        assert_halts(self.loop_on("LET a:=1\nLET z:=1\nLET x:=a*z"))


class TestErrors:
    """Rejections, asserted by their exact text.

    ``pytest.raises(match=...)`` is a substring search, which is too weak
    for a language whose rejections differ only in *which* one fires: a
    tokenizer whose uppercase range stops one letter short turns "unknown
    keyword 'Z'" into "unexpected character 'Z'", and a structure check
    that loses its label set turns "duplicate loop label 'a'" into "no open
    loop 'a'".  Both still match a regex naming every message, so the
    programs below pin the whole string instead.
    """

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
            ("LET x=1", "unexpected character '='"),  # single = instead of :=
            ("LET x:", "malformed assignment operator (expected ':=')"),
            ("LET x:=", "malformed statement"),  # missing expression
            ("LET x:=1+", "malformed expression"),  # trailing operator
            ("LET x:=1 2", "malformed expression"),  # two operands in a row
            ("LET x:=1**2", "malformed expression"),  # two operators in a row
            ("LET x:=-", "malformed expression"),  # lone sign
            ("LET 5:=1", "malformed statement"),  # numeric variable name
            ("LET x:=5!", "unexpected character '!'"),  # stray character
            ("LET X:=1", "unknown keyword 'X'"),  # uppercase variable
            ("LET Z:=1", "unknown keyword 'Z'"),  # the last uppercase letter
            ("A", "unknown keyword 'A'"),  # the first uppercase letter
            ("LET x:=1A", "unknown keyword 'A'"),  # a letter glued to a number
            ("LET aZ:=1", "unknown keyword 'Z'"),  # a letter glued to a name
            ("LET x:=-1A", "unknown keyword 'A'"),  # a letter glued to a sign
            ("LET x:=[", "unexpected character '['"),  # between 'Z' and 'a'
            ("LET x:=_", "unexpected character '_'"),  # likewise
            ("LET x:=`", "unexpected character '`'"),  # and just below 'a'
            ("x y", "malformed statement"),  # two names, no keyword
            ("POINT", "malformed statement"),  # missing label
            ("POINT 5", "malformed statement"),  # numeric label
            ("IF x BREAK", "malformed statement"),  # missing label
            ("IF x GOTO loop", "unknown keyword 'GOTO'"),
            ("BREAK x", "malformed statement"),  # not a statement
            ("END loop", "no open loop 'loop'"),  # END with no open loop
            ("POINT a\nPOINT a\nEND a\nEND a", "duplicate loop label 'a'"),
            ("POINT a\nEND b", "no open loop 'b'"),  # END for an unopened loop
            ("POINT a\nIF x BREAK b\nEND a", "BREAK b outside its loop"),
            ("POINT a\nEND a\nPOINT b", "unclosed loop 'b'"),  # unclosed loop
        ],
    )
    def test_malformed_program(self, program: str, message: str) -> None:
        with pytest.raises(ValueError) as caught:
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
        """A program is accepted as one string or as a list of lines, and
        the two forms reach the same final state -- otherwise the split is
        doing something the joined form is not."""
        joined = _Machine("LET zero:=0\nLET one:=1", ScriptedIO())
        split = _Machine(["LET zero:=0", "LET one:=1"], ScriptedIO())

        assert run_until_halt_or_cycle(joined) is True
        assert run_until_halt_or_cycle(split) is True
        assert joined.snapshot() == split.snapshot()
