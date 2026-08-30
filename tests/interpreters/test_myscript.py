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
from esolangs.interpreters.register_based.myscript import run
from tests.interpreters.contract import SnapshotContract


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
        code = (
            'check ask?\n  if "1",\n    while yes,\n      say "1"\n  else,\n    say "0"'
        )
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
            '  say concat "obj.prop: " itemat obj 0\n'
            'var myObject is MyClass "Hello!"\n'
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

    def test_missing_operands_are_rejected(self) -> None:
        """A prefix call that ends before its arity is malformed text."""
        for code in ("say", "add", "add 1", "not", "itemat"):
            with pytest.raises(ValueError, match="ended before its operands"):
                run_and_capture(code)

    def test_incomplete_var_declaration_is_rejected(self) -> None:
        """The ``var`` form is checked before its parts are read."""
        for code in ("var", "var b0", "var b0 "):
            with pytest.raises(ValueError, match="malformed var declaration"):
                run_and_capture(code)

    def test_assign_to_undefined_halts(self) -> None:
        with pytest.raises(HaltError):
            run_and_capture("x is 5")

    def test_itemat_out_of_range_halts(self) -> None:
        with pytest.raises(HaltError):
            run_and_capture("var a is [1, 2]\nsay itemat a 5")

    def test_if_outside_check_halts(self) -> None:
        with pytest.raises(HaltError):
            run_and_capture('if no,\n  say "x"')

    def test_input_running_out_raises_eof(self) -> None:
        from esolangs.interpreters.io import ScriptedIO

        with pytest.raises(EOFError):
            run("say ask", ScriptedIO(""))

    def test_lines_without_tokens_are_ignored(self) -> None:
        """A line with no tokenizable content is skipped, not crashed on."""
        assert run_and_capture("-}`\n") == ""

    def test_truthiness_coercion(self) -> None:
        # int/str/list/function values coerce in while conditions
        assert run_and_capture("var a is []\nwhile a,\n  say x") == ""
        assert run_and_capture('while "",\n  say x') == ""
        assert run_and_capture("while 0,\n  say x") == ""
        assert run_and_capture('var f is func\n  say "x"\nsay not f') == "xno"

    def test_float_print_omits_the_point(self) -> None:
        assert run_and_capture("var a is 5.0\nsay a") == "5"

    def test_expected_a_number_halts(self) -> None:
        with pytest.raises(HaltError):
            run_and_capture('say add "x" 1')

    def test_expected_an_array_halts(self) -> None:
        with pytest.raises(HaltError):
            run_and_capture("say arrlen 5")

    def test_function_assigns_to_an_outer_variable(self) -> None:
        code = "var a is 1\nvar f is func\n  a is 2\n  say a\nsay f\nsay a"
        assert run_and_capture(code) == "2None2"

    def test_bare_return_in_a_function(self) -> None:
        assert run_and_capture("var f is func\n  return\nsay f") == "None"

    def test_while_loop_runs(self) -> None:
        code = "var i is 3\nwhile less 0 i,\n  say i\n  var i is subtract i 1"
        assert run_and_capture(code) == "321"

    def test_while_loop_with_condition_recheck(self) -> None:
        # the condition is re-evaluated after each pass through the body
        code = "var i is 1\nvar f is func\n  var i is 2\nwhile i,\n  var i is 0\nsay i"
        assert run_and_capture(code) == "0"

    def test_while_loop_inside_a_function_body(self) -> None:
        # a while loop nested in a function body runs through _run_statement's
        # own while handling, not the top-level frame stack's
        code = (
            "var f is func\n"
            "  var i is 2\n"
            "  while i,\n"
            "    say i\n"
            "    var i is subtract i 1\n"
            "say f"
        )
        assert run_and_capture(code) == "21None"

    def test_top_level_return_ends_the_program(self) -> None:
        assert run_and_capture("say 1\nreturn\nsay 2") == "1"


class TestStepMachine:
    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.register_based.myscript import _Machine

        machine = _Machine("", IO())
        while not machine.halted:
            machine.step()
        machine.step()  # stepping a halted machine is a no-op
        assert machine.halted

    def test_malformed_var_declaration_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="malformed"):
            run_and_capture("var x 5")

    def test_malformed_check_case_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="malformed"):
            run_and_capture('check 5,\n  whatever,\n    say "y"')

    def test_check_with_no_matching_case(self) -> None:
        assert run_and_capture('check 5,\n  if 1,\n    say "a"') == ""

    def test_is_head_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="malformed"):
            run_and_capture("is 5")

    def test_top_level_assignment(self) -> None:
        assert run_and_capture("var a is 1\na is 2\nsay a") == "2"


class TestGenerator:
    def test_round_trip(self) -> None:
        from esolangs.tools import text as gen

        for text in ["Hi", "Hello, World!", "a\tb\nc", 'quote"and\\slash']:
            assert run_and_capture(gen.myscript(text)) == text

    def test_unrepresentable_rejected(self) -> None:
        from esolangs.tools import text as gen

        with pytest.raises(ValueError, match="representable"):
            gen.myscript("\x07")


class TestSnapshot:
    def test_check_runs_the_first_matching_case(self) -> None:
        """A matching case runs its block and stops the check."""
        code = 'check 5,\n  if 5,\n    say "hit"\n  if 5,\n    say "again"'
        assert run_and_capture(code) == "hit"

    def test_snapshot_captures_a_nested_scope_chain(self) -> None:
        """A function frame's scope chain is folded into the snapshot key."""
        from esolangs.interpreters.register_based.myscript import _Machine

        code = "var f is func x\n  return add x 1\nsay f 1"
        machine = _Machine(code, IO())
        seen = set()
        while not machine.halted:
            seen.add(machine.snapshot())
            machine.step()
        assert len(seen) > 1


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.register_based.myscript import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "var a is 1\nsay a"
