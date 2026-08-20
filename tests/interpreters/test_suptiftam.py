"""Unit tests for the Suptiftam interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.suptiftam import run

HELLO_WORLD = "\n".join(
    [
        "term='H'",
        "right(:term:)",
        "term='e'",
        "right(:term:)",
        "term='l'",
        "right(:term:)",
        "term='l'",
        "right(:term:)",
        "term='o'",
        "right(:term:)",
        "term=','",
        "right(:term:)",
        "term=%-['a']'A'%",  # 'a' - 'A' = 32, a space
        "right(:term:)",
        "term='w'",
        "right(:term:)",
        "term='o'",
        "right(:term:)",
        "term='r'",
        "right(:term:)",
        "term='l'",
        "right(:term:)",
        "term='d'",
        "right(:term:)",
        "term='!'",
    ]
)

TRUTH_MACHINE = "\n".join(
    [
        "fd tmach x:",
        "term=x",
        "right(:term:)",
        "tmach(:x:)if(x)",
        "fi",
        "tmach(:%-[read]22%:)",  # the wiki's 48 parses as 100; 22 parses as 48
    ]
)

CAT = "\n".join(
    [
        "fd cat :x",
        "term=read",
        "right(:term:)",
        "right(:read:)",
        "cat(:x:)if(:read:)",
        "fi",
        "cat(:read:)",
    ]
)


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class TestHelloWorld:
    def test_wiki_example(self) -> None:
        """The wiki's Hello World (with its byte-math space) prints the text."""
        assert run_program(HELLO_WORLD) == "Hello, world!"


class TestLiterals:
    def test_integer_literals_are_base23_parsed(self) -> None:
        """Base-14-written literals are parsed in base 23."""
        assert run_program("term=10") == "23"  # 1*23 + 0
        assert run_program("term=1D") == "36"  # 1*23 + 13
        assert run_program("term=22") == "48"  # 2*23 + 2, the ASCII '0'
        assert run_program("term=48") == "100"  # 4*23 + 8

    def test_single_letter_literals(self) -> None:
        """A bare letter that is no variable is a base-23 literal digit."""
        assert run_program("term=A") == "10"
        assert run_program("term=D") == "13"

    def test_integers_with_no_digits(self) -> None:
        """A name that later becomes a variable is read as a literal first."""
        program = "\n".join(["x=A", "A=7", "y=A", "term=y"])
        assert run_program(program) == "7"

    def test_byte_literals(self) -> None:
        assert run_program("term='A'") == "A"
        assert run_program("term=' '") == " "  # a space is a valid byte literal

    def test_multi_digit_integer_output(self) -> None:
        assert run_program("term=48") == "100"


class TestMath:
    def test_byte_math_stays_a_byte(self) -> None:
        """Two byte operands keep the byte type, so the result is a character."""
        assert run_program("term=%-['a']'A'%") == " "

    def test_mixed_math_is_an_integer(self) -> None:
        """A byte with an integer operand widens to an integer result."""
        assert run_program("term=%+['A']1%") == "66"

    def test_addition_and_subtraction(self) -> None:
        assert run_program("term=%+[A]B%") == "21"  # 10 + 11
        assert run_program("term=%-[A]B%") == "-1"  # 10 - 11

    def test_division_truncates_toward_zero(self) -> None:
        assert run_program("term=%/[6]3%") == "2"
        assert run_program("x=%-[0]6%\nterm=%/[x]3%") == "-2"
        assert run_program("term=%/[6]4%") == "1"

    def test_division_by_zero_halts(self) -> None:
        with pytest.raises(HaltError, match="division by zero"):
            run_program("term=%/[3]0%")

    def test_math_uses_tape_cells(self) -> None:
        """A tape operand in math reads the value under its head."""
        assert run_program("term=%-[read]22%", stdin="1\n") == "1"  # 49 - 48


class TestVariables:
    def test_implicit_declaration(self) -> None:
        """Assigning an undeclared name declares it with the value's type."""
        assert run_program("x=5\nterm=x") == "5"

    def test_tilde_declaration(self) -> None:
        assert run_program("x~5\nterm=x") == "5"

    def test_byte_wraps(self) -> None:
        """A byte variable wraps modulo 256 on assignment."""
        program = "\n".join(
            [
                "x='" + chr(255) + "'",
                "x=%+[x]'" + chr(1) + "'%",
                "term=x",
            ]
        )
        assert run_program(program) == "\x00"  # 255 + 1 wraps to 0

    def test_type_mismatch_prints_a_digit(self) -> None:
        """A mismatched assignment leaves the variable and prints '0' to term."""
        program = "\n".join(["x=0", "term=x", "x='A'", "term=x"])
        assert run_program(program) == "0"

    def test_undeclared_identifier_halts(self) -> None:
        with pytest.raises(HaltError, match="undeclared identifier"):
            run_program("term=zzz")


class TestCalls:
    def test_call_tokens_in_any_order(self) -> None:
        program = "fd f :x\nterm=x\nfi\nx=A\nf:A:()"
        assert run_program(program) == "10"
        assert run_program(program.replace("f:A:()", ")f(:A:")) == "10"
        assert run_program(program.replace("f:A:()", "():x:f")) == "10"

    def test_conditional_call(self) -> None:
        program = "\n".join(["fd f :x", "term='y'", "fi", "term='a'", "f(:0:)if(0)"])
        assert run_program(program) == "a"  # 0 is false, so f never runs
        program = "\n".join(["fd f :x", "term='y'", "fi", "term='a'", "f(:0:)if(1)"])
        assert run_program(program) == "y"  # 1 is true, so f overwrites

    def test_conditional_call_on_a_tape(self) -> None:
        program = "\n".join(
            ["fd f :x", "term='y'", "fi", "term='a'", "f(:0:)if(:read:)"]
        )
        assert run_program(program, stdin="1\n") == "y"  # nonzero cell fires
        assert run_program(program, stdin="") == "a"  # an EOF cell is zero

    def test_recursion_counts_down(self) -> None:
        program = "\n".join(
            [
                "total=0",
                "fd count :n",
                "total=%+[total]n%",
                "n=%-[n]1%",
                "count(:n:)if(n)",
                "fi",
                "count(:A:)",  # A = 10
                "term=total",
            ]
        )
        assert run_program(program) == "55"  # 10 + ... + 1

    def test_deep_recursion_no_longer_capped(self) -> None:
        """A correct, terminating recursion past the old 250-level cap completes."""
        program = "\n".join(
            [
                "total=0",
                "fd count :n",
                "total=%+[total]n%",
                "n=%-[n]1%",
                "count(:n:)if(n)",
                "fi",
                "count(:0D1:)",  # 0D1 = 300 in base 23
                "term=total",
            ]
        )
        assert run_program(program) == "45150"  # 300 + ... + 1

    def test_undefined_function_halts(self) -> None:
        with pytest.raises(HaltError, match="undefined function"):
            run_program("f(:1:)")

    def test_function_extension_appends_bodies(self) -> None:
        program = "\n".join(
            [
                "fd f :x",
                "term='a'",
                "fi",
                "fd f :x",
                "right(:term:)",
                "term='b'",
                "fi",
                "f(:1:)",
            ]
        )
        assert run_program(program) == "ab"

    def test_global_scope_wins_over_argument(self) -> None:
        program = "\n".join(["x=5", "fd f :x", "term=x", "fi", "f(:7:)"])
        assert run_program(program) == "5"

    def test_nested_definition_is_hoisted(self) -> None:
        program = "\n".join(
            ["fd a :x", "fd b :y", "term='z'", "fi", "b(:1:)", "fi", "a(:1:)"]
        )
        assert run_program(program) == "z"


class TestTapes:
    def test_head_movement(self) -> None:
        assert run_program("term='a'\nright(:term:)\nterm='b'") == "ab"
        assert run_program("term='a'\nleft(:term:)\nterm='b'") == "ba"
        assert run_program("term='a'\nup(:term:)\nterm='b'") == "b\na"
        assert run_program("term='a'\ndown(:term:)\nterm='b'") == "a\nb"

    def test_unwritten_cells_render_as_nul(self) -> None:
        program = "\n".join(["term='a'", "right(:term:)", "right(:term:)", "term='c'"])
        assert run_program(program) == "a\x00c"

    def test_user_tape_declarations(self) -> None:
        # [integer] declares a byte tape
        assert run_program("t[integer]\nt='A'\nterm=t") == "A"
        # [byte] declares an integer tape; a byte mismatch prints the digit
        assert run_program("t[byte]\nt=1\nterm=t") == "1"
        assert run_program("t[byte]\nt='A'\nterm=t") == "\x00"  # mismatch

    def test_redeclaring_a_tape_is_a_noop(self) -> None:
        program = "t[integer]\nt[integer]\nt='A'\nterm=t"
        assert run_program(program) == "A"

    def test_assigning_a_tape_uses_its_cell(self) -> None:
        assert run_program("term=read", stdin="hi\n") == "h"

    def test_reading_past_input_yields_zero(self) -> None:
        program = "\n".join(
            [
                "fd r :x",
                "term=read",
                "fi",
                "r(:read:)",
                "right(:read:)",
                "right(:read:)",
                "term=read",
            ]
        )
        assert run_program(program, stdin="hi\n") == "\x00"  # past the row's end


class TestBuiltins:
    def test_include_is_unsupported(self) -> None:
        with pytest.raises(HaltError, match="include is not supported"):
            run_program("include(:read:)")

    def test_moves_need_a_tape(self) -> None:
        with pytest.raises(HaltError, match="needs a tape"):
            run_program("right(:1:)")


class TestRobustness:
    def test_empty_program_prints_nothing(self) -> None:
        assert run_program("") == ""

    def test_comment_lines_are_skipped(self) -> None:
        program = "term='a'\tthis is a comment\nterm='b'"
        assert run_program(program) == "b"

    def test_malformed_programs_raise_value_error(self) -> None:
        for code in (
            "fi",  # stray end marker
            "fd f :x\nterm='a'",  # missing fi
            "fd a b c:",  # too many names
            "fd x",  # missing colon
            "fd 5 :x",  # non-identifier function name
            "fd x 5:",  # non-identifier argument
            "f(:x:g)",  # two names in a call
            "f(:x)",  # one colon
            "f(:x:)5",  # stray token
            "f(:x:)if(1)if(2)",  # two conditions
            "(:x:)",  # no function name
            "f(:if(1):)",  # non-value argument
            "f(:'a)",  # malformed byte literal argument
            "term='a",  # unterminated byte literal
            "term=%x[1]2%",  # bad operator
            "term=%+1]2%",  # missing bracket
            "term=%+[1 2%",  # missing closing bracket
            "term=%+[1]2",  # missing closing percent
            "term=%+[1]",  # missing second operand
            "term=%+[%+[1]2%]3%",  # nested math
            "term=%/[1]%+[1]2%%",  # nested math in the second operand
            "term=%+[1]#%",  # bad second operand
            "term=%+['a]2%",  # malformed byte operand
            "t[]",  # empty tape declaration
            "t[xyz]",  # unknown tape type
            "t[integer",  # missing closing bracket
            "t[integer] extra",  # trailing tokens
            "[integer]",  # declaration with no name
            "x~",  # declaration with no value
            "x~)",  # declaration with a non-value
            "x=",  # assignment with no value
            "xyz",  # bare identifier statement
            "term=!",  # unexpected character
        ):
            with pytest.raises(
                ValueError,
                match=(
                    r"malformed|unexpected|needs|missing|without|must be|"
                    r"cannot|unknown|expected|function|at most"
                ),
            ):
                run_program(code)

    def test_local_assignment_uses_the_frame_scope(self) -> None:
        """A new name inside a function is local, not global."""
        program = "\n".join(["fd f :x", "y=1", "term=y", "fi", "f(:1:)"])
        assert run_program(program) == "1"

    def test_if_malformed_raises(self) -> None:
        for code in ("f(:0:)if(1", "f(:0:)if(:x"):
            with pytest.raises(ValueError, match="malformed if"):
                run_program(code)
