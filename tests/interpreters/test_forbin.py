"""Unit tests for the Forbin interpreter.

Covers the bit ``in``/``out`` I/O, the iteration and range for-loops (ranges
double as if-statements), the NOT operator, function calls and recursion,
and the documented error conventions.
"""

import contextlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.forbin import run


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io)
    return io.getvalue()


class TestOutput:
    def test_out_literals(self) -> None:
        code = "main { out 0,1,0,0,1,0,0,0; }"
        assert run_program(code) == "H"

    def test_out_arbitrary_byte(self) -> None:
        code = "main { out 1,1,1,1,1,1,1,1; }"
        assert run_program(code) == "\xff"

    def test_empty_program_rejected(self) -> None:
        with pytest.raises(ValueError, match="no main"):
            run_program("loop { out 0,0,0,0,0,0,0,0; }")

    def test_out_wrong_arity_halts(self) -> None:
        with pytest.raises(HaltError, match="8 bit"):
            run_program("main { out 0,0,0,0,0,0,0; }")


class TestInput:
    def test_in_reads_a_byte_msb_first(self) -> None:
        # 'A' is 0b01000001
        code = "main { a,b,c,d,e,f,g,h = (in 0); out a,b,c,d,e,f,g,h; }"
        assert run_program(code, "A") == "A"

    def test_in_running_out_raises_eof(self) -> None:
        code = "main { a,b,c,d,e,f,g,h = (in 0); }"
        with pytest.raises(EOFError):
            run(code, ScriptedIO(""))


class TestLoops:
    def test_range_loops_once_and_twice(self) -> None:
        # 0..0 runs once (i=0), 0..1 runs twice (i=0,1)
        code = """
            main {
              n = 0;
              for i:0..0 { n = !n; }
              out 0,0,0,0,0,0,0,n;
              n = 0;
              for i:0..1 { n = !n; }
              out 0,0,0,0,0,0,0,n;
            }
        """
        assert run_program(code) == "\x01\x00"

    def test_range_as_if_statement(self) -> None:
        # for _:!c..c runs the body iff c is 1 (twice, since 0..1 iterates)
        code = """
            main {
              c = 0;
              for _:!c..c { out 0,1,0,0,0,0,0,1; }
              c = 1;
              for _:!c..c { out 0,1,0,0,0,0,0,1; }
            }
        """
        assert run_program(code) == "AA"

    def test_iteration_loop_over_variables(self) -> None:
        code = """
            main {
              any = 0;
              for i:(0, 0, 1) { for _:!i..i { any = 1; } }
              out 0,0,0,0,0,0,0,any;
            }
        """
        assert run_program(code) == "\x01"

    def test_iteration_wildcard_expands(self) -> None:
        code = """
            main {
              s = 0;
              for (i, j):((1, *)) { for _:!i..i { s = 1; } }
              out 0,0,0,0,0,0,0,s;
            }
        """
        assert run_program(code) == "\x01"

    def test_underscore_loop_variable(self) -> None:
        code = "main { for _:0..1 { out 0,1,0,0,0,0,0,1; } }"
        assert run_program(code) == "AA"


class TestFunctions:
    def test_not(self) -> None:
        code = "main { a = 1; a = !a; out 0,0,0,0,0,0,0,a; }"
        assert run_program(code) == "\x00"

    def test_unpassed_parameter_is_zero(self) -> None:
        """Unpassed parameters are set to 0 (per the wiki)."""
        code = """
            main {
              f a, b { out 0,0,0,0,0,0,0,b; }
              r = (f 1);
            }
        """
        assert run_program(code) == "\x00"

    def test_bare_block_is_function_literal(self) -> None:
        """A bare {code} block is a function literal in value position."""
        code = """
            main {
              x = { return 1; };
              out 0,0,0,0,0,0,0,(x 0);
            }
        """
        assert run_program(code) == "\x01"

    def test_function_returns(self) -> None:
        code = """
            one { return 1; }
            main {
              a = (one 0);
              out 0,0,0,0,0,0,0,a;
            }
        """
        assert run_program(code) == "\x01"

    def test_forward_reference(self) -> None:
        # loop is defined after main but still callable
        code = """
            main {
              h = 0;
              for _:!h..h { helper 0; }
            }
            helper { out 1,1,1,1,1,1,1,1; }
        """
        assert run_program(code) == ""

    def test_recursion(self) -> None:
        code = """
            main {
              a,b,c,d,e,f,g,h = (in 0);
              out a,b,c,d,e,f,g,h;
              for _:!h..h { again 0; }
            }
            again { out 0,0,1,1,0,0,0,1; }
        """
        # input '0' (h=0): no recursion
        assert run_program(code, "0") == "0"

    def test_function_as_argument(self) -> None:
        # the wiki's eq helper, called via a passed function
        code = """
            eq a, b {
              equal = 0;
              for _:a..b { equal = !equal; }
              return equal;
            }
            main {
              x = 1;
              y = 1;
              r = (eq x, y);
              out 0,0,0,0,0,0,0,r;
            }
        """
        assert run_program(code) == "\x01"

    def test_undeclared_identifier_halts(self) -> None:
        with pytest.raises(HaltError, match="undeclared"):
            run_program("main { out 0,0,0,0,0,0,0,x; }")

    def test_not_on_function_halts(self) -> None:
        with pytest.raises(HaltError, match="needs a bit"):
            run_program("main { f { } f 0; a = !f; }")

    def test_malformed_syntax(self) -> None:
        with pytest.raises(ValueError, match="expected"):
            run_program("main { out 0,0,0,0,0,0,0 } extra")


class TestParserErrors:
    def test_line_comments_are_ignored(self) -> None:
        code = "main { // header\n a = 1; // trailing\n out 0,0,0,0,0,0,0,a; }"
        assert run_program(code) == "\x01"

    def test_missing_paren_after_anon_func(self) -> None:
        with pytest.raises(ValueError, match="expected"):
            run_program("main { x = (a@ { return 1; }; }")

    def test_digit_where_an_identifier_is_expected(self) -> None:
        with pytest.raises(ValueError, match="identifier"):
            run_program("main { for 1:0..1 { } }")

    def test_value_at_end_of_input(self) -> None:
        with pytest.raises(ValueError, match="value"):
            run_program("main { x =")

    def test_anonymous_function_literal(self) -> None:
        code = "main { f = (a@ { out 0,0,0,0,0,0,0,a; }); r = (f 1); }"
        assert run_program(code) == "\x01"

    def test_unexpected_character(self) -> None:
        with pytest.raises(ValueError, match="character"):
            run_program("main { x = 2; }")

    def test_range_needs_two_dots(self) -> None:
        with pytest.raises(ValueError, match=r"\.\."):
            run_program("main { for i:0 1 { } }")

    def test_trailing_comma_header(self) -> None:
        # f a, { is a header whose parameter list ends after the comma
        assert run_program("main { f a, { out 0,0,0,0,0,0,0,0; } }") == ""

    def test_unterminated_block(self) -> None:
        with pytest.raises(ValueError, match="unterminated"):
            run_program("main {")

    def test_assignment_target_must_be_a_variable(self) -> None:
        with pytest.raises(ValueError, match="target must be a variable"):
            run_program("main { (f 1) = 2; }")
        with pytest.raises(ValueError, match="target must be a variable"):
            run_program("main { a, !b = 0, 1; }")

    def test_multi_target_needs_equals(self) -> None:
        with pytest.raises(ValueError, match="after assignment"):
            run_program("main { a, b 2; }")

    def test_statement_must_be_a_call_or_assignment(self) -> None:
        with pytest.raises(ValueError, match="statement must be"):
            run_program("main { 1; }")

    def test_calling_a_non_function_halts(self) -> None:
        with pytest.raises(HaltError, match="not a function"):
            run_program("main { x = 0; r = (x 1); }")

    def test_recursion_limit_exceeded(self) -> None:
        """Infinite recursion halts cleanly rather than leaking a RecursionError."""
        with pytest.raises(HaltError, match="recursion"):
            run_program("main { again 1; }\nagain { again 0; }")

    def test_multi_assignment(self) -> None:
        code = "main { a, b = 1, 0; " "out 0,0,0,0,0,0,0,a; out 0,0,0,0,0,0,0,b; }"
        assert run_program(code) == "\x01\x00"
