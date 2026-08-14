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
