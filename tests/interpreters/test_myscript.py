"""Unit tests for the MyScript interpreter.

MyScript is a JavaScript-inspired prefix language: prefix function calls
(``add a b``), line-based statements, and indented ``while``/``check``
blocks and function bodies.  These tests pin the wiki's examples and the
edge cases (undefined variables, out-of-range indexing, mismatched calls).
"""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.other.myscript import run


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestExamples:
    def test_hello_world(self) -> None:
        assert run_and_capture('say "Hello, World!"') == "Hello, World!"

    def test_cat(self) -> None:
        assert run_and_capture("say ask", inputs=["hi"]) == "hi"

    def test_truth_machine_zero(self) -> None:
        code = "check ask?\n  if \"1\",\n    while yes,\n      say \"1\"\n  else,\n    say \"0\""
        assert run_and_capture(code, inputs=["0"]) == "0"

    def test_math_and_variables(self) -> None:
        code = "var a is 5\nvar b is 3\nsay add a b\nsay multiply a b"
        assert run_and_capture(code) == "815"

    def test_user_function(self) -> None:
        code = "var add2 is func x y\n  return add x y\nsay add2 3 4"
        assert run_and_capture(code) == "7"

    def test_simple_class(self) -> None:
        code = (
            "var MyClass is func prop\n"
            "  return [prop]\n"
            "var MyClass_myMethod is func obj\n"
            "  say concat \"obj.prop: \" itemat obj 0\n"
            "var myObject is MyClass \"Hello!\"\n"
            "MyClass_myMethod myObject"
        )
        assert run_and_capture(code) == "obj.prop: Hello!"

    def test_string_escapes(self) -> None:
        assert run_and_capture(r'say "a\nb"') == "a\nb"
        assert run_and_capture(r'say "a\tb"') == "a\tb"
        assert run_and_capture(r'say "a\\b"') == "a\\b"
        assert run_and_capture(r'say "a\"b"') == 'a"b'


class TestBuiltins:
    def test_arithmetic(self) -> None:
        assert run_and_capture("say divide 7 2") == "3.5"
        assert run_and_capture("say subtract 9 4") == "5"

    def test_comparisons(self) -> None:
        code = "say equals 3 3\nsay equals 3 4\nsay less 2 3\nsay not no"
        assert run_and_capture(code) == "yesnoyesyes"

    def test_arrays(self) -> None:
        code = "var a is [1, 2, 3]\nsay arrlen a\nsay itemat a 1"
        assert run_and_capture(code) == "32"

    def test_while_loop(self) -> None:
        code = "var i is 3\nwhile less i 0,\n  say i\n  var i is subtract i 1"
        assert run_and_capture(code) == ""


class TestErrors:
    def test_undefined_variable_halts(self) -> None:
        with pytest.raises(HaltError):
            run_and_capture("say missing")

    def test_assign_to_undefined_halts(self) -> None:
        with pytest.raises(HaltError):
            run_and_capture("x is 5")

    def test_itemat_out_of_range_halts(self) -> None:
        with pytest.raises(HaltError):
            run_and_capture("var a is [1, 2]\nsay itemat a 5")

    def test_if_outside_check_halts(self) -> None:
        with pytest.raises(HaltError):
            run_and_capture("if no,\n  say \"x\"")

    def test_input_running_out_raises_eof(self) -> None:
        from esolangs.interpreters.io import ScriptedIO

        with pytest.raises(EOFError):
            run("say ask", ScriptedIO(""))


class TestGenerator:
    def test_round_trip(self) -> None:
        from esolangs.tools import generate as gen

        for text in ["Hi", "Hello, World!", "a\tb\nc", "quote\"and\\slash"]:
            assert run_and_capture(gen.myscript(text)) == text

    def test_unrepresentable_rejected(self) -> None:
        from esolangs.tools import generate as gen

        with pytest.raises(ValueError, match="representable"):
            gen.myscript("\x07")
