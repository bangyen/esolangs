"""Unit tests for the Suptiftam interpreter."""

from typing import ClassVar

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.suptiftam import run
from tests.interpreters.contract import SnapshotContract

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


class TestWikiPrograms:
    def test_cat(self) -> None:
        """The cat program echoes its input back."""
        assert run_program(CAT, "hi") == "hi"

    def test_truth_machine_zero(self) -> None:
        """A 0 input prints 0 and halts.

        The 1 branch loops forever by definition, so only the terminating
        branch is exercised.
        """
        assert run_program(TRUTH_MACHINE, "0") == "0"


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

    def test_a_non_value_token_halts(self) -> None:
        """Only the value tokens stand where a value is expected.

        ``_Value`` is the subset of ``_Token`` a declaration or argument
        accepts, and the parsers check for it before evaluating -- so this
        guard answers for a token that lexed fine but is not one, which is
        reached by handing the evaluator one directly.
        """
        from esolangs.interpreters.other.suptiftam import _eval_value, _State

        state = _State(ScriptedIO(""))
        with pytest.raises(HaltError, match="expected a value, got 'if'"):
            _eval_value(("if", ("num", 1)), state, None)


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
            with pytest.raises(ValueError):
                run_program(code)

    # Each malformed program above paired with the message it must raise.
    # The list alone only proves *something* was rejected: its ``match=``
    # named every message the parser can emit, so a check firing in the
    # wrong place -- or one message swapped for another -- still passed.
    # The positions matter too, and were never asserted at all.
    REJECTIONS: ClassVar[list[tuple[str, str]]] = [
        ("fi", "fi without a matching fd"),
        ("fd f :x\nterm='a'", "function 'f' is missing its fi"),
        ("fd a b c:", "fd header needs a function name"),
        ("fd x", "fd header needs a colon"),
        ("fd 5 :x", "fd header needs a function name"),
        ("fd x 5:", "the fd argument must be an identifier"),
        ("f(:x:g)", "a call has exactly one function name"),
        ("f(:x)", "a call needs its argument between two colons"),
        ("f(:x:)5", "unexpected token ('num', 5) in a call"),
        ("f(:x:)if(1)if(2)", "a call has at most one if"),
        ("(:x:)", "a call needs a function name and parentheses"),
        ("f(:if(1):)", "a call's argument must be a value"),
        ("f(:'a)", "malformed byte literal at position 3"),
        ("term='a", "malformed byte literal at position 5"),
        ("term=%x[1]2%", "malformed math at position 5"),
        ("term=%+1]2%", "malformed math at position 5"),
        ("term=%+[1 2%", "malformed math at position 5"),
        ("term=%+[1]2", "malformed math at position 5"),
        ("term=%+[1]", "expected a value"),
        ("term=%+[%+[1]2%]3%", "math cannot be nested at position 5"),
        ("term=%/[1]%+[1]2%%", "math cannot be nested at position 5"),
        ("term=%+[1]#%", "expected a value at position 10"),
        ("term=%+['a]2%", "malformed byte literal"),
        ("t[]", "malformed tape declaration at position 1"),
        ("t[xyz]", "unknown tape type 'xyz'"),
        ("t[integer", "malformed tape declaration at position 1"),
        ("t[integer] extra", "malformed tape declaration"),
        ("[integer]", "malformed tape declaration at position 0"),
        ("x~", "malformed ~ statement"),
        ("x~)", "malformed ~ statement"),
        ("x=", "malformed = statement"),
        ("xyz", "malformed statement: 'xyz'"),
        ("term=!", "unexpected character '!' at position 5"),
    ]

    @pytest.mark.parametrize(("code", "message"), REJECTIONS)
    def test_each_rejection_says_its_own_thing(self, code: str, message: str) -> None:
        """Every malformed program is paired with the message it raises."""
        with pytest.raises(ValueError) as caught:
            run_program(code)
        assert str(caught.value) == message

    def test_local_assignment_uses_the_frame_scope(self) -> None:
        """A new name inside a function is local, not global."""
        program = "\n".join(["fd f :x", "y=1", "term=y", "fi", "f(:1:)"])
        assert run_program(program) == "1"

    def test_a_parameter_does_not_survive_its_call(self) -> None:
        """The frame's names are gone once the call returns.

        Output cannot show this: the function prints the same byte whether
        its parameter was bound in the frame or in the globals, so a
        binding written to the wrong scope leaves no trace in what the
        program says.  Reading the global scope afterwards does show it --
        only the two tapes the language starts with should be there.
        """
        from esolangs.interpreters.other.suptiftam import _Machine

        program = "\n".join(["fd f :x", "x=%+[x]1%", "term=x", "fi", "f(:1:)"])
        io = ScriptedIO("")
        machine = _Machine(program, io)
        while not machine.halted:
            machine.step()
        assert io.getvalue() == "2"
        assert sorted(machine.state.globals) == ["read", "term"]

    def test_if_malformed_raises(self) -> None:
        for code in ("f(:0:)if(1", "f(:0:)if(:x"):
            with pytest.raises(ValueError, match="malformed if"):
                run_program(code)

    def test_an_if_without_its_paren_is_refused(self) -> None:
        """``_scan_if`` checks for the ``(`` it was told would be there.

        The statement dispatcher only calls it after matching ``if(``, so a
        whole program cannot reach this -- it is refused as a malformed
        statement first.  The check is the parser's own precondition, and
        testing it directly is what keeps the two spellings of "malformed
        if" agreeing about what counts as one.
        """
        from esolangs.interpreters.other.suptiftam import _scan_if

        for line in ("if", "if x", "ifx"):
            with pytest.raises(ValueError, match="malformed if"):
                _scan_if(line, 2)


class TestMachine:
    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.other.suptiftam import _Machine

        machine = _Machine("term='H'", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.state.io.getvalue() == "H"
        machine.step()  # stepping a halted machine is a no-op
        assert machine.state.io.getvalue() == "H"

    def test_a_program_that_never_writes_the_term_prints_nothing(self) -> None:
        """An unwritten term has no cells, so the end-of-run render is empty."""
        io = ScriptedIO()
        run("var~1", io)
        assert io.getvalue() == ""


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.other.suptiftam import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "term='H'\nright(:term:)"
