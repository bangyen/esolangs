"""Unit tests for Qoibl interpreter.

Tests cover all Qoibl operations including printing, assignment, conditionals,
math operations, loops, and binary number parsing. Includes timeout protection
to prevent hanging tests from infinite loops.
"""

import io
import signal
from collections.abc import Callable
from contextlib import redirect_stdout
from typing import Any
from unittest.mock import patch

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.qoibl import run, tokenize


class _TestTimeoutError(Exception):
    """Custom timeout exception for test protection."""


def timeout_handler(_signum: int, _frame: Any) -> None:
    """Signal handler for timeout protection."""
    raise _TestTimeoutError("Test timed out")


def run_with_timeout(func: Callable[..., Any], timeout_seconds: int = 2) -> Any:
    """Run a function with timeout protection.

    Args:
        func: Function to execute
        timeout_seconds: Maximum execution time in seconds

    Returns:
        Result of function execution

    Raises:
        _TestTimeoutError: If function exceeds timeout

    """
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)
    try:
        result = func()
    except _TestTimeoutError:
        raise
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
    return result


class TestQoiblBasicOperations:
    """Test basic Qoibl operations."""

    def test_print_character(self) -> None:
        """Test tt instruction for printing characters."""
        code: list[str] = ["tt yeeyeee tt"]  # 'H' in binary
        with redirect_stdout(io.StringIO()) as f:
            run(code, IO())
        assert f.getvalue() == "H"

    def test_print_hello_world(self) -> None:
        """Test printing 'Hello, worl' using multiple print statements."""
        hello_world_code: list[str] = [
            "tt yeeyeee tt",  # H
            "tt yyeeyey tt",  # e
            "tt yyeyyee tt",  # l
            "tt yyeyyee tt",  # l
            "tt yyeyyyy tt",  # o
            "tt yeyyee tt",  # ,
            "tt yeeeee tt",  # (space)
            "tt yyyeyyy tt",  # w
            "tt yyeyyyy tt",  # o
            "tt yyyeeye tt",  # r
            "tt yyeyyee tt",  # l
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(hello_world_code, io=IO())
        assert f.getvalue() == "Hello, worl"

    def test_assignment_and_access(self) -> None:
        """Test we (assignment) and qe (access) instructions."""
        code: list[str] = [
            "we y we yyeeee we",  # var[1] = 48
            "tt qe y qe tt",  # print var[1]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code, IO())
        assert f.getvalue() == chr(48)  # '0'

    def test_input_operation(self) -> None:
        """Test et (input) instruction."""
        code: list[str] = [
            "we y we et we",
            "tt qe y qe tt",
        ]  # input -> var[1], print var[1]
        with (
            patch("builtins.input", return_value="A"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(code, IO())
        assert f.getvalue() == "A"


class TestQoiblBinaryNumbers:
    """Test binary number parsing."""

    def test_binary_zero(self) -> None:
        """Test binary number 'e' (0)."""
        code: list[str] = ["tt e tt"]
        with redirect_stdout(io.StringIO()) as f:
            run(code, IO())
        assert f.getvalue() == chr(0)

    def test_binary_one(self) -> None:
        """Test binary number 'y' (1)."""
        code: list[str] = ["tt y tt"]
        with redirect_stdout(io.StringIO()) as f:
            run(code, IO())
        assert f.getvalue() == chr(1)

    def test_binary_numbers(self) -> None:
        """Test various binary numbers."""
        test_cases = [
            ("ee", 0),
            ("ey", 1),
            ("ye", 2),
            ("yy", 3),
            ("eee", 0),
            ("eey", 1),
            ("eye", 2),
            ("eyy", 3),
            ("yee", 4),
            ("yey", 5),
            ("yye", 6),
            ("yyy", 7),
        ]

        for binary_str, expected in test_cases:
            code: list[str] = [f"tt {binary_str} tt"]
            with redirect_stdout(io.StringIO()) as f:
                run(code, IO())
            assert f.getvalue() == chr(expected), f"Failed for {binary_str}"


class TestQoiblConditionals:
    """Test conditional operations (yr instruction)."""

    def test_equality_condition(self) -> None:
        """Test ee (equality) operator."""
        code: list[str] = [
            "we y we yy we",  # var[1] = 3
            "we ye we yy we",  # var[2] = 3
            "tt qe y qe yr ee yr qe ye qe tt",  # print var[1] == var[2]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code, IO())
        assert f.getvalue() == chr(1)  # True

    def test_greater_than_condition(self) -> None:
        """Test ey (greater than) operator."""
        code: list[str] = [
            "we y we yyy we",  # var[1] = 7
            "we ye we yy we",  # var[2] = 3
            "tt qe y qe yr ey yr qe ye qe tt",  # print var[1] > var[2]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code, IO())
        assert f.getvalue() == chr(1)  # True

    def test_less_than_condition(self) -> None:
        """Test ye (less than) operator."""
        code: list[str] = [
            "we y we y we",  # var[1] = 1
            "we ye we yy we",  # var[2] = 3
            "tt qe y qe yr ye yr qe ye qe tt",  # print var[1] < var[2]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code, IO())
        assert f.getvalue() == chr(1)  # True

    def test_the_orderings_are_strict(self) -> None:
        """``ye`` and ``ey`` are false when the two operands are equal.

        Every case above compares a smaller value with a larger one, so
        both orderings could be non-strict without a test noticing.
        Equal operands are what separates ``<`` from ``<=``.
        """
        for op in ("ye", "ey"):
            code: list[str] = [
                "we y we yy we",  # var[1] = 3
                "we ye we yy we",  # var[2] = 3
                f"tt qe y qe yr {op} yr qe ye qe tt",
            ]
            with redirect_stdout(io.StringIO()) as f:
                run(code, IO())
            assert f.getvalue() == chr(0), op

    def test_not_equal_condition(self) -> None:
        """Test yy (not equal) operator."""
        code: list[str] = [
            "we y we y we",  # var[1] = 1
            "we ye we yy we",  # var[2] = 3
            "tt qe y qe yr yy yr qe ye qe tt",  # print var[1] != var[2]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code, IO())
        assert f.getvalue() == chr(1)  # True


class TestQoiblMathOperations:
    """Test math operations (ry instruction)."""

    def test_addition(self) -> None:
        """Test ee (addition) operator."""
        code: list[str] = [
            "we y we yy we",  # var[1] = 3
            "we ye we yy we",  # var[2] = 3
            "tt qe y qe ry ee ry qe ye qe tt",  # print var[1] + var[2]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code, IO())
        assert f.getvalue() == chr(6)

    def test_subtraction(self) -> None:
        """Test ey (subtraction) operator."""
        code: list[str] = [
            "we y we yyy we",  # var[1] = 7
            "we ye we yy we",  # var[2] = 3
            "tt qe y qe ry ey ry qe ye qe tt",  # print var[1] - var[2]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code, IO())
        assert f.getvalue() == chr(4)

    def test_multiplication(self) -> None:
        """Test ye (multiplication) operator."""
        code: list[str] = [
            "we y we yy we",  # var[1] = 3
            "we ye we yy we",  # var[2] = 3
            "tt qe y qe ry ye ry qe ye qe tt",  # print var[1] * var[2]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code, IO())
        assert f.getvalue() == chr(9)

    def test_division(self) -> None:
        """Test yy (division) operator."""
        code: list[str] = [
            "we y we yyy we",  # var[1] = 7
            "we ye we yy we",  # var[2] = 3
            "tt qe y qe ry yy ry qe ye qe tt",  # print var[1] // var[2]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code, IO())
        assert f.getvalue() == chr(2)  # 7 // 3 = 2


class TestQoiblExamples:
    """Test example programs from the esolangs wiki."""

    def test_one_digit_adder(self) -> None:
        """Test the one digit adder example (up to 4+5)."""
        code: list[str] = [
            "we e we yyeeee we",  # var[0] = 2
            "we y we et ry ey ry qe e qe we",  # var[1] = input - 2
            "we ye we et ry ey ry qe e qe we",  # var[2] = input - 2
            "we y we qe y qe ry ee ry qe ye qe we",  # var[1] = var[1] + var[2]
            "we y we qe y qe ry ee ry qe e qe we",  # var[1] = var[1] + 2
            "tt qe y qe tt",  # print var[1]
        ]

        # Test 2 + 3 = 5
        def run_adder() -> str:
            with (
                patch("builtins.input", side_effect=["2", "3"]),
                redirect_stdout(io.StringIO()) as f,
            ):
                run(code, IO())
            return f.getvalue()

        result = run_with_timeout(run_adder, timeout_seconds=2)
        assert result == "5"  # Should print 5

    def test_while_loop(self) -> None:
        """Test the rr while loop: decrement var[1] until it is not > 1."""
        code: list[str] = [
            "we y we yy we",  # var[1] = 3
            "rr qe y qe yr ey yr y rr we y we qe y qe ry ey ry y we rr",
            "tt qe y qe tt",  # print var[1]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code, IO())
        assert f.getvalue() == chr(1)  # decremented 3 -> 1


class TestQoiblEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_program(self) -> None:
        """Test running an empty program."""
        code: list[str] = []
        with redirect_stdout(io.StringIO()) as f:
            run(code, IO())
        assert f.getvalue() == ""

    def test_blank_lines_are_ignored(self) -> None:
        """Blank and whitespace-only lines are skipped, not crashed on."""
        with redirect_stdout(io.StringIO()) as f:
            run(["\n", "\t \t", ""], IO())
        assert f.getvalue() == ""

    def test_undefined_variable_access(self) -> None:
        """Test accessing undefined variables (should return 0)."""
        code: list[str] = ["tt qe yyy qe tt"]  # print var[7] (undefined)
        with redirect_stdout(io.StringIO()) as f:
            run(code, IO())
        assert f.getvalue() == chr(0)

    def test_division_by_zero(self) -> None:
        """Test division by zero behavior."""
        from esolangs.exceptions import HaltError

        code: list[str] = [
            "we y we yyy we",  # var[1] = 7
            "we ye we e we",  # var[2] = 0
            "tt qe y qe ry yy ry qe ye qe tt",  # print var[1] // var[2]
        ]
        with pytest.raises(HaltError):
            run(code, IO())

    def test_unrecognized_operator_rejected(self) -> None:
        """An unrecognized arithmetic operator is a malformed program."""
        code: list[str] = ["tt y ry qe y y tt"]
        with pytest.raises(ValueError, match="operator"):
            run(code, IO())

    def test_unrecognized_comparison_rejected(self) -> None:
        """An unrecognized comparison operator is a malformed program."""
        code: list[str] = ["tt y yr qe y y tt"]
        with pytest.raises(ValueError, match="operator"):
            run(code, IO())

    def test_truncated_operator_rejected(self) -> None:
        """A comparison or arithmetic operator with no operand is malformed."""
        with pytest.raises(ValueError, match="comparison"):
            run(["yr"], IO())
        with pytest.raises(ValueError, match="arithmetic"):
            run(["ry"], IO())

    def test_empty_expression_rejected(self) -> None:
        with pytest.raises(ValueError, match="expression"):
            run(["tt  "], IO())

    def test_nested_expressions(self) -> None:
        """Test nested expressions and complex operations."""
        code: list[str] = [
            "we y we yy we",  # var[1] = 3
            "we ye we yy we",  # var[2] = 3
            "we yyy we qe y qe ry ee ry qe ye qe we",  # var[3] = var[1] + var[2]
            "tt qe yyy qe tt",  # print var[3]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code, IO())
        assert f.getvalue() == chr(6)


WIKI_PROGRAMS = {
    "adder": (
        "we e we yyeeee we\n"
        "we y we et ry ey ry qe e qe we\n"
        "we ye we et ry ey ry qe e qe we\n"
        "we y we qe y qe ry ee ry qe ye qe we\n"
        "we y we qe y qe ry ee ry qe e qe we\n"
        "tt qe y qe tt"
    ),
    "truth": (
        "we e we et we\nrr qe e qe yr ee yr yyeeey rr tt yyeeey tt rr\ntt yyeeee tt"
    ),
    "cat": "rr e yr ee yr e rr tt et tt rr",
    "hello": (
        "tt yeeyeee tt\ntt yyeeyey tt\ntt yyeyyee tt\ntt yyeyyee tt\n"
        "tt yyeyyyy tt\ntt yeyyee tt\ntt yeeeee tt\ntt yyyeyyy tt\n"
        "tt yyeyyyy tt\ntt yyyeeye tt\ntt yyeyyee tt\ntt yyeeyee tt\n"
        "tt yeeeey tt\ntt yeye tt"
    ),
}


class TestQoiblTokenizer:
    """The wiki calls spaces ignorable, so a program may omit them entirely."""

    @pytest.mark.parametrize("name", sorted(WIKI_PROGRAMS))
    def test_spacing_does_not_change_statements(self, name: str) -> None:
        """Spaced, space-free, and single-stream sources tokenize alike."""
        source = WIKI_PROGRAMS[name]
        expected = [line.split() for line in source.splitlines()]
        squeezed = source.replace(" ", "")
        assert tokenize(source) == expected
        assert tokenize(squeezed) == expected
        assert tokenize(squeezed.replace("\n", "")) == expected

    def test_output_matches_without_spaces(self) -> None:
        """A program run as one unbroken string prints what the spaced one does."""
        source = WIKI_PROGRAMS["hello"]
        stream = source.replace(" ", "").replace("\n", "")
        with redirect_stdout(io.StringIO()) as spaced:
            run(source, IO())
        with redirect_stdout(io.StringIO()) as fused:
            run(stream, IO())
        assert spaced.getvalue() == fused.getvalue() == "Hello, world!\n"

    def test_input_instruction_reclaims_its_character(self) -> None:
        """An odd run of `t` spells `et`, which claims the preceding `e`."""
        assert tokenize("rrttetttrr")[0] == ["rr", "tt", "et", "tt", "rr"]

    def test_comparison_marker_closes_its_pair(self) -> None:
        """`yr ee yr` must not read as `yr eey ry`, which strands the operand."""
        assert tokenize("qeeqeyreeyryyeeey")[0] == [
            "qe",
            "e",
            "qe",
            "yr",
            "ee",
            "yr",
            "yyeeey",
        ]

    def test_ignores_characters_outside_the_alphabet(self) -> None:
        """The spec ignores anything that is not part of an instruction."""
        assert tokenize("tt! yeeyeee? tt") == [["tt", "yeeyeee", "tt"]]

    def test_statements_need_no_line_breaks(self) -> None:
        """Two complete statements on one line stay two statements."""
        assert tokenize("tt yeeyeee tt tt yyeeyey tt") == [
            ["tt", "yeeyeee", "tt"],
            ["tt", "yyeeyey", "tt"],
        ]


class TestQoiblCycleDetection:
    def test_a_terminating_program_is_reported_as_halting(self) -> None:
        """``snapshot`` is the cycle detector's hook into the interpreter.

        It reports the whole of what a step can change -- the cursor, the
        variables, and how far input has been read -- so two identical
        snapshots really do mean the program is going nowhere.  Nothing
        exercised it before, because ``run`` drives the machine itself.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.qoibl import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        state = _Machine("we y we yyeeee we\ntt qe y qe tt", ScriptedIO(""))
        assert run_until_halt_or_cycle(state) is True

    def test_the_snapshot_moves_when_a_statement_runs(self) -> None:
        """A step that assigns changes the snapshot, so it is not a cycle."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.qoibl import _Machine

        state = _Machine("we y we yyeeee we\ntt qe y qe tt", ScriptedIO(""))
        before = state.snapshot()
        state.step()
        assert state.snapshot() != before


class TestQoiblIncompleteTokens:
    def test_a_lone_prefix_yields_an_empty_statement(self) -> None:
        """``w`` and ``q`` only mean something before ``e``.

        A prefix with nothing to pair with contributes no token, so the
        statement it sits in comes out empty -- which ``step`` then has to
        skip rather than try to evaluate.
        """
        assert tokenize("w") == [[]]
        assert tokenize("q") == [[]]

    def test_stepping_an_empty_statement_advances_the_cursor(self) -> None:
        """An empty statement is a no-op, not a parse of nothing."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.qoibl import _Machine

        state = _Machine("w", ScriptedIO(""))
        assert state.code == ([],)
        state.step()
        assert state.halted


class TestQoiblParserGuards:
    """The three conditions a mutation survived, each pinned by behaviour.

    Mutation testing (mutmut against a ``bundle_one`` build of this module)
    reported these as changeable without any test noticing: the tokenizer's
    give-back guard, its empty-input guard, and the closing-marker check in
    ``_wellformed``.  Each is a rejection, and a rejection that stops
    rejecting is invisible until something malformed is accepted.
    """

    def test_steal_declines_a_literal_without_the_character(self) -> None:
        """Nothing is given back unless the literal actually ends in it.

        The mutant that reads this guard with ``and`` instead of ``or``
        returned the literal shortened anyway, inventing a token split the
        source never spelled.
        """
        from esolangs.interpreters.register_based.qoibl import _steal

        assert _steal(["yy"], "e") is None  # no trailing 'e' to give back
        assert _steal(["e"], "e") == []  # a one-character literal vanishes
        assert _steal(["ye"], "e") == ["y"]  # a longer one is shortened

    def test_steal_declines_an_empty_token_list(self) -> None:
        """The emptiness check has to come first, or indexing raises.

        ``tokens[-1]`` is evaluated the moment the guard stops short-
        circuiting, so a mutant that reorders it crashes with IndexError
        rather than returning None.
        """
        from esolangs.interpreters.register_based.qoibl import _steal

        assert _steal([], "e") is None

    def test_a_binary_operator_needs_its_closing_marker(self) -> None:
        """``yr``/``ry`` wrap an operator, and both ends must be the same one.

        Only the matched form parses; a mismatched closing marker or none at
        all is malformed.  Without this check both were accepted, so a
        program that never spelled a complete operation would still run.
        """
        from esolangs.interpreters.register_based.qoibl import _wellformed

        assert _wellformed(["e", "yr", "ee", "yr", "y"]) is True
        assert _wellformed(["e", "yr", "ee", "ry", "y"]) is False  # wrong close
        assert _wellformed(["e", "yr", "ee"]) is False  # no close at all

    def test_an_unrecognised_token_evaluates_to_zero(self) -> None:
        """The evaluator's last arm answers a token no keyword claims.

        ``tokenize`` only accepts a split under which every statement
        parses, so this is unreachable from source; it is the fallback for
        a hand-built expression list, and it must leave the variables it
        was handed alone rather than inventing an entry.
        """
        from esolangs.interpreters.register_based.qoibl import _eval

        value, var = _eval(["zz"], {"e": 1}, lambda: 0, lambda _s: None)
        assert value == 0
        assert var == {"e": 1}
