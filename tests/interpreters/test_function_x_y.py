"""Unit tests for the function x(y) interpreter.

Covers every example on the language's wiki page, the expression forms
(arithmetic precedence, comparison, the spacing that separates a ternary
from a comparison, variables and compound assignment), the documented
spec-gap decisions, and the error conventions.

The wiki examples are the ground truth here, so they are pinned by their
*output* rather than by inspection of the parse.
"""

import contextlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.function_x_y import _Machine, run
from tests.interpreters.contract import CycleContract, EmptyProgramContract


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io)
    return io.getvalue()


def machine(code: str) -> _Machine:
    return _Machine(code, ScriptedIO(""))


# -- the wiki's own examples -------------------------------------------

# Reproduced from https://esolangs.org/wiki/Function_x(y) verbatim, except
# where a note says otherwise.
HELLO = 'function helloWorld()\n["Hello, World!"]'
CAT = "function cat()\n[[~]]"
ABS = "function abs(n)\n-> (n < 0)<0 - n, n>"
FACTORIAL = "function factorial(n)\n-> (n < 2)<1, n * {n - 1}>"
FIB = "function fib(acc | 0, num | 1)\n[num]\n-> fib(num, num + acc)"

# The wiki's FizzBuzz line 2 is ``(n != 100)<((fizz(n) + buzz(n)) == "")<[n],
# printAndRecurse(n)>`` -- two ``<`` openers against one ``>``, and the outer
# ternary has no false arm.  It cannot be parsed as written (pinned below by
# ``test_the_wiki_fizzbuzz_line_is_unbalanced``); this is the minimal repair,
# adding the missing ``>`` and a ``, 0`` false arm.
FIZZBUZZ = """function fizzbuzz(n | 0)
(n != 100)<((fizz(n) + buzz(n)) == "")<[n], printAndRecurse(n)>, 0>

function fizz(n)
-> ((n // 3) * 3 == n)<"Fizz", "">

function buzz(n)
-> ((n // 5) * 5 == n)<"Buzz", "">

function printAndRecurse(n)
[fizz(n) + buzz(n)]
fizzbuzz(n + 1)
"""


class TestWikiExamples:
    def test_hello_world(self) -> None:
        assert run_program(HELLO) == "Hello, World!\n"

    def test_cat(self) -> None:
        """``[[~]]`` is ``[expr]`` over the ``[~]`` line read."""
        assert run_program(CAT, "meow\n") == "meow\n"

    @pytest.mark.parametrize(("arg", "want"), [(-5, "5"), (7, "7"), (0, "0")])
    def test_absolute_value(self, arg: int, want: str) -> None:
        """The wiki's ``abs`` only returns, so a caller prints the result."""
        code = f"function main()\n[abs({arg})]\n\n{ABS}"
        assert run_program(code) == f"{want}\n"

    @pytest.mark.parametrize(
        ("arg", "want"), [(0, "1"), (1, "1"), (2, "2"), (5, "120"), (7, "5040")]
    )
    def test_factorial(self, arg: int, want: str) -> None:
        """``{n - 1}`` re-calls the current function -- the namesake."""
        code = f"function main()\n[factorial({arg})]\n\n{FACTORIAL}"
        assert run_program(code) == f"{want}\n"

    def test_fibonacci_streams_the_sequence(self) -> None:
        """``fib`` recurses forever by design, so it is stepped, not run."""
        m = machine(FIB)
        io = m.io
        for _ in range(400):
            if m.halted:
                break
            m.step()
        assert not m.halted, "the wiki's fib is an infinite stream"
        assert isinstance(io, ScriptedIO)
        printed = io.getvalue().split()
        assert printed[:9] == ["1", "1", "2", "3", "5", "8", "13", "21", "34"]

    def test_fizzbuzz_repaired(self) -> None:
        """The repaired FizzBuzz halts after two lines -- a wiki logic bug.

        Beyond the syntax typo the example never recurses from its ``[n]``
        arm, so it prints ``FizzBuzz`` for 0, then ``1``, and stops.  That
        is what the example *says*; do not "fix" this expectation.  It still
        exercises the lazy arms, string ``+``/``==``, ``//`` and the mutual
        named calls, which is what FizzBuzz is here to cover.
        """
        assert run_program(FIZZBUZZ) == "FizzBuzz\n1\n"

    def test_the_wiki_fizzbuzz_line_is_unbalanced(self) -> None:
        """The verbatim wiki line has two ``<`` against one ``>``."""
        verbatim = FIZZBUZZ.replace(
            "<[n], printAndRecurse(n)>, 0>", "<[n], printAndRecurse(n)>"
        )
        with pytest.raises(ValueError, match="ternary"):
            run(verbatim, ScriptedIO(""))


# -- expressions --------------------------------------------------------


class TestExpressions:
    @pytest.mark.parametrize(
        ("expr", "want"),
        [
            ("1 + 2", "3"),
            ("2 * 3 + 1", "7"),
            ("1 + 2 * 3", "7"),  # BDMAS: * binds tighter than +
            ("(1 + 2) * 3", "9"),
            ("7 - 2 - 1", "4"),  # left associative
            ("7 / 2", "3"),  # integer division
            ("7 // 2", "3"),  # the FizzBuzz spelling of the same op
            ("-6 / 2", "-3"),
            ("0 - 7 / 2", "-3"),
        ],
    )
    def test_arithmetic(self, expr: str, want: str) -> None:
        assert run_program(f"function f()\n[{expr}]") == f"{want}\n"

    @pytest.mark.parametrize(
        ("expr", "want"),
        [
            ("1 < 2", "1"),
            ("2 < 1", "0"),
            ("2 > 1", "1"),
            ("1 <= 1", "1"),
            ("1 => 1", "1"),  # the wiki spells it ``=>``, not ``>=``
            ("2 => 3", "0"),
            ("1 == 1", "1"),
            ("1 != 1", "0"),
        ],
    )
    def test_comparison_yields_one_or_zero(self, expr: str, want: str) -> None:
        assert run_program(f"function f()\n[{expr}]") == f"{want}\n"

    def test_spacing_separates_a_ternary_from_a_comparison(self) -> None:
        """``a < b`` is a comparison; ``)<(`` opens a ternary.

        The spacing is the only thing telling the two apart, so it is
        load-bearing rather than cosmetic.
        """
        assert run_program('function f()\n[(1 < 2)<"y", "n">]') == "y\n"
        assert run_program('function f()\n[(2 < 1)<"y", "n">]') == "n\n"

    def test_a_ternary_evaluates_exactly_one_arm(self) -> None:
        """Lazily: an arm that prints must not fire when unselected."""
        assert run_program("function f()\n(1 == 1)<[9], [8]>") == "9\n"
        assert run_program("function f()\n(1 == 0)<[9], [8]>") == "8\n"

    def test_ternary_arms_may_contain_calls_with_commas(self) -> None:
        """The arm split is the *top-level* comma, so a call survives it."""
        code = "function f()\n[(1 == 1)<g(1, 2), 0>]\n\nfunction g(a, b)\n-> a + b"
        assert run_program(code) == "3\n"

    def test_string_concatenation_and_equality(self) -> None:
        assert run_program('function f()\n["a" + "b"]') == "ab\n"
        assert run_program('function f()\n["" == ""]') == "1\n"
        assert run_program('function f()\n[1 + "x"]') == "1x\n"

    def test_print_with_and_without_a_newline(self) -> None:
        assert run_program('function f()\n["a"]\n["b"]') == "a\nb\n"
        assert run_program('function f()\n`"a"\n`"b"') == "ab"

    def test_negative_literal(self) -> None:
        assert run_program("function f()\n[-456]") == "-456\n"

    def test_comment_to_end_of_line(self) -> None:
        assert run_program('function f() # header\n["a"] # trailing') == "a\n"

    def test_a_hash_inside_a_string_is_not_a_comment(self) -> None:
        assert run_program('function f()\n["a#b"]') == "a#b\n"


class TestVariables:
    def test_declare_and_access(self) -> None:
        assert run_program("function f()\nvar v: 5\n[v]") == "5\n"

    def test_assignment(self) -> None:
        assert run_program("function f()\nvar v: 5\nv; 9\n[v]") == "9\n"

    @pytest.mark.parametrize(
        ("op", "want"), [("+&", "7"), ("-&", "3"), ("*&", "10"), ("/&", "2")]
    )
    def test_compound_assignment(self, op: str, want: str) -> None:
        assert run_program(f"function f()\nvar v: 5\nv {op} 2\n[v]") == f"{want}\n"

    def test_an_undefined_variable_is_an_invalid_operation(self) -> None:
        with pytest.raises(HaltError, match="undefined variable"):
            run("function f()\n[nope]", ScriptedIO(""))


class TestFunctions:
    def test_execution_starts_at_the_first_function(self) -> None:
        code = 'function first()\n["first"]\n\nfunction second()\n["second"]'
        assert run_program(code) == "first\n"

    def test_default_return_value_is_zero(self) -> None:
        """The wiki: "default return value is 0"."""
        code = 'function f()\n[g()]\n\nfunction g()\n`""'
        assert run_program(code) == "0\n"

    def test_a_default_parameter_applies_when_no_argument_is_passed(self) -> None:
        code = "function f()\n[g(1)]\n\nfunction g(a, b | 10)\n-> a + b"
        assert run_program(code) == "11\n"

    def test_an_argument_overrides_the_default(self) -> None:
        code = "function f()\n[g(1, 2)]\n\nfunction g(a, b | 10)\n-> a + b"
        assert run_program(code) == "3\n"

    def test_mutual_recursion_resolves_after_parsing(self) -> None:
        """``a`` calls ``b``, declared later, so names bind after the parse."""
        code = "function a()\n[b(3)]\n\nfunction b(n)\n-> (n < 1)<0, b(n - 1) + 1>"
        assert run_program(code) == "3\n"

    def test_too_many_arguments_is_an_invalid_operation(self) -> None:
        with pytest.raises(HaltError, match="takes 0 arguments"):
            run("function f()\n[g(1)]\n\nfunction g()\n-> 1", ScriptedIO(""))

    def test_a_missing_argument_without_a_default_is_an_invalid_operation(
        self,
    ) -> None:
        with pytest.raises(HaltError, match="missing argument"):
            run("function f()\n[g()]\n\nfunction g(a)\n-> a", ScriptedIO(""))

    def test_an_unknown_function_is_an_invalid_operation(self) -> None:
        with pytest.raises(HaltError, match="unknown function"):
            run("function f()\n[nope()]", ScriptedIO(""))


class TestInput:
    def test_line_input(self) -> None:
        assert run_program("function f()\n[[~]]", "hello\n") == "hello\n"

    def test_character_input(self) -> None:
        assert run_program("function f()\n[`~]", "abc\n") == "a\n"

    def test_an_empty_line_is_legal_for_character_input(self) -> None:
        """A bare Enter reads as 0 rather than raising an IndexError."""
        assert run_program("function f()\n[`~]", "\n") == "\x00\n"

    def test_exhausted_input_raises_eof(self) -> None:
        with pytest.raises(EOFError):
            run("function f()\n[[~]]", ScriptedIO(""))


class TestErrors:
    @pytest.mark.parametrize(
        ("code", "reason"),
        [
            ("[1]", "statement outside any function"),
            ("function f(", "malformed function header"),
            ("function f()\n-> (1", r"unbalanced \(\)"),
            ('function f()\n["oops]', "unterminated string"),
            ("function f()\n-> 1<2>", "ternary needs exactly two arms"),
            ("function f()\n-> @@@", "unexpected character in expression"),
            ("function f(n)\n-> n", "needs a default"),
            ("function f()\n-> " + "(" * 60 + "1" + ")" * 60, "nests deeper"),
        ],
    )
    def test_a_malformed_program_raises_value_error(
        self, code: str, reason: str
    ) -> None:
        """The reason is pinned: "any ValueError" would also pass a parser
        that had started refusing every program.
        """
        with pytest.raises(ValueError, match=reason):
            run(code, ScriptedIO(""))

    def test_division_by_zero_is_an_invalid_operation(self) -> None:
        with pytest.raises(HaltError, match="division by zero"):
            run("function f()\n[1 / 0]", ScriptedIO(""))

    def test_arithmetic_on_a_string_is_an_invalid_operation(self) -> None:
        with pytest.raises(HaltError, match="cannot apply"):
            run('function f()\n["a" - 1]', ScriptedIO(""))

    def test_deep_source_nesting_is_refused_rather_than_overflowing(self) -> None:
        """A ``RecursionError`` escaping the parser would be a crash.

        The parser recurses over the source, so the fuzz suite's random text
        could overflow Python's stack: 300 nested parentheses did.  The cap
        turns that into the ``ValueError`` a malformed program owes.
        """
        deep = "function f()\n-> " + "(" * 3000 + "1" + ")" * 3000
        with pytest.raises(ValueError, match="nests deeper"):
            run(deep, ScriptedIO(""))


class TestRunawayRecursion:
    """Unbounded recursion must not crash the process.

    The interpreter keeps its own evaluation-frame stack rather than using
    Python's, so there is no depth ceiling and nothing raises: a runaway
    program simply keeps stepping.  That is the property under test -- the
    machine steps far past Python's own recursion limit without an
    exception and without halting.  A program recursing through ever-new
    states never repeats a snapshot, so the cycle detector cannot stop it
    either; ``esolangs.run``'s wall-clock timeout is the backstop.
    """

    @pytest.mark.parametrize(
        "code",
        [
            # The guard counts the wrong way, so it never fires.
            "function f(n | 3)\n-> (n < 2)<1, n * {n + 1}>",
            # Mutual recursion through named calls.
            "function a(n | 0)\n-> b(n)\n\nfunction b(n)\n-> a(n)",
        ],
    )
    def test_runaway_recursion_steps_cleanly(self, code: str) -> None:
        import sys

        m = machine(code)
        for _ in range(20000):
            if m.halted:
                break
            m.step()
        assert not m.halted, "this program does not terminate"
        # Far past Python's own limit: the frames are the machine's, not
        # the interpreter's C stack.
        assert len(m.frames) > sys.getrecursionlimit()


class TestMachine:
    def test_snapshot_is_hashable_and_complete(self) -> None:
        """The frame stack is tuples throughout, so a snapshot hashes."""
        m = machine(FACTORIAL.replace("(n)", "(n | 5)"))
        seen = {m.snapshot()}
        for _ in range(20):
            m.step()
            seen.add(hash(m.snapshot()) and m.snapshot())
        assert len(seen) > 1

    def test_snapshot_tracks_the_input_cursor(self) -> None:
        """A repeat that ignores consumed input is not a real cycle."""
        io = ScriptedIO("a\nb\n")
        m = _Machine("function f()\n[[~]]\n[[~]]", io)
        before = m.snapshot()
        while not m.halted:
            m.step()
        assert m.snapshot() != before
        assert io.position() == 2


class TestEmptyProgram(EmptyProgramContract):
    run = staticmethod(run_program)
    empty_raises = "program declares no function"


class TestCycle(CycleContract):
    machine = staticmethod(machine)
    halting_program = HELLO
    # ``fib`` and the runaway programs above all grow their state forever, so
    # none of them ever repeats a snapshot; a program that loops on a
    # *repeated* state needs a fixed point, and every loop this language can
    # write recurses with a changing frame stack.  Left as the contract's
    # documented skip rather than filled with a guess.
    looping_program = None
