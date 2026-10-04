"""Alight diagnostics, size constraints and public integration."""

from typing import ClassVar

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.alight import _Machine, run
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.alight import alight
from tests.interpreters.contract import EmptyProgramContract
from tests.interpreters.runner import run_program


def _run(code: list[str], stdin: str = "") -> str:
    return run_program(run, code, stdin)


def _machine(code: list[str]) -> _Machine:
    return _Machine(code, ScriptedIO("a\nb\n"))


class TestErrors:
    """Malformed programs against invalid operations: ValueError vs HaltError."""

    def test_a_program_without_begin_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="no 'begin'"):
            run(["var c;end;"], ScriptedIO())

    def test_a_reversed_end_does_not_halt(self) -> None:
        with pytest.raises(ValueError, match="unknown command 'dne'"):
            run(["begin;;dne;"], ScriptedIO())
        assert _run(["begin;;end;"]) == ""

    def test_walking_off_the_grid_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError, match="walked off the grid"):
            run(["begin;;;"], ScriptedIO())

    def test_naming_an_undeclared_variable_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError, match="no such variable: 'c'"):
            run(["begin;out c;end;"], ScriptedIO("1\n"))
        with pytest.raises(HaltError, match="no such variable: 'c'"):
            run(["begin;inp c;end;"], ScriptedIO("1\n"))

    def test_an_unknown_command_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="unknown command"):
            run(["begin;frobnicate x;end;"], ScriptedIO())

    def test_an_undeclared_variable_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError, match="no such variable"):
            run(["begin;set q 1;end;"], ScriptedIO())

    def test_a_redeclared_variable_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError, match="already exists"):
            run(["begin;var q;var q;end;"], ScriptedIO())

    def test_a_non_boolean_guard_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError, match="guard is not a boolean"):
            run(["begin;var v;set v 1;turn v;end;"], ScriptedIO())

    def test_outputting_a_non_character_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError, match="cannot output"):
            run(["begin;var v;out v;end;"], ScriptedIO())

    def test_a_reserved_word_is_not_a_variable_name(self) -> None:
        with pytest.raises(ValueError, match="bad variable name"):
            run(["begin;var end;end;"], ScriptedIO())


class TestFunctions:
    def test_an_unknown_function_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError, match="no such function"):
            run(["begin;var v;set v nope{1};end;"], ScriptedIO())

    def test_wrong_argument_count_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError, match="takes 1 arguments"):
            run(
                ["begin;var v;set v one{1, 2};end;", "func one{a};end a;"], ScriptedIO()
            )

    @pytest.mark.parametrize(
        "program",
        [
            ["begin;var v;set v loop{1};end;", "func loop{a};end loop{a};"],
            ["begin;var v;set v f{1};end;", "func f{a};var b;set b f{a};end b;"],
        ],
        ids=["return-position", "body-position"],
    )
    def test_unbounded_recursion_grows_walkers_without_crashing(
        self, program: list[str]
    ) -> None:
        machine = _machine(program)
        for _ in range(3000):
            machine.step()
        assert len(machine.walkers) > 1000
        assert not machine.halted

    def test_at_copy_beside_a_call_preserves_the_original(self) -> None:
        """A copied list beside a user call leaves its input intact."""
        program = [
            'begin;var l;set l "A";var v;'
            "set v len{at{l, 0.5, at{l, 0.5}+1}}+f{0};"
            "var c;set c at{l, 0.5};out c;end;",
            "func f{a};end a;",
        ]
        assert _run(program) == "A"

    def test_at_copy_beside_two_calls_preserves_the_original(self) -> None:
        """Resuming after two calls also preserves the original list."""
        program = [
            'begin;var l;set l "A";var v;'
            "set v len{at{l, 0.5, at{l, 0.5}+1}}+f{0}+g{0};"
            "var c;set c at{l, 0.5};out c;end;",
            "func f{a};end a;",
            "func g{a};end a;",
        ]
        assert _run(program) == "A"


class TestGenerators:
    def test_boolean_length_does_not_leak_the_table(self) -> None:
        lengths = {len(alight(bin(v)[2:].zfill(8))) for v in range(256)}
        assert len(lengths) == 1

    def test_boolean_refuses_a_nullary_table(self) -> None:
        with pytest.raises(ValueError, match="at least one input"):
            alight("0")

    def test_registered_generator_runs_through_the_public_api(self) -> None:
        assert esolangs.run("Alight", alight("01"), "1\n") == "1"


class TestEmptyProgram(EmptyProgramContract):
    run = staticmethod(lambda code: _run(code))
    empty_program: ClassVar[list[str]] = [""]
    empty_raises = "empty program"


class TestEdgeCases:
    @pytest.mark.parametrize(
        ("program", "message"),
        [
            ('begin;var v;set v "abc;', "unterminated string"),
            ("begin;var v;set v len{v;", "expected"),
            ("begin;var v;set v '", "unterminated string"),
            ("begin;var v;set v 1+;", "expression ends early"),
            ("begin;var v;set v @;", "cannot parse operand"),
            ("begin;var v;set v [1 2];", "expected"),
            ("begin;var v;set v 1 2;", "trailing text"),
            ("begin;var v;v 1;", "unknown command"),
            ("begin;+;", "cannot parse command"),
        ],
    )
    def test_malformed_programs_raise_value_error(
        self, program: str, message: str
    ) -> None:
        with pytest.raises(ValueError, match=message):
            run([program], ScriptedIO())

    @pytest.mark.parametrize(
        ("program", "message"),
        [
            ('begin;var v;set v "ab"*"cd";end;', "two lists"),
            ('begin;var v;set v "ab"-2;end;', "list and"),
            ('begin;var v;set v "ab"*1.5;end;', "repeat count"),
            ("begin;var v;set v nil+1;end;", "cannot apply"),
            ('begin;var v;set v len{"ab", 1.5};end;', "pad count"),
            ("begin;var v;set v trunc{nil};end;", "takes one number"),
            ("begin;var v;set v len{1};end;", "takes a list"),
            ('begin;var v;set v at{"ab", 9.5, 65};end;', "past the end"),
            ("begin;var v;set v 0-1;out v;end;", "not a character code"),
            ("begin;var v;set v 65.5;out v;end;", "not a character code"),
            ('begin;var v;set v at{"ab", nil};end;', "index is not a number"),
        ],
    )
    def test_invalid_operations_raise_halt_error(
        self, program: str, message: str
    ) -> None:
        with pytest.raises(HaltError, match=message):
            run([program], ScriptedIO())

    def test_a_program_may_be_handed_over_as_a_string(self) -> None:
        io = ScriptedIO("")
        run("begin;var c;set c 65;out c;end;", io)
        assert io.getvalue() == "A"


class TestFunctionDefinitionEdges:
    @pytest.mark.parametrize(
        "definition",
        [
            "func other{a};end a;",
            "func g{end};end 65;",
            "func g{a;end a;",
            "func g{a}x;end a;",
            "func g{a b};end a;",
        ],
    )
    def test_a_header_that_does_not_match_is_not_the_function(
        self, definition: str
    ) -> None:
        with pytest.raises(HaltError, match="no such function"):
            run(["begin;var v;set v f{1};end;", definition], ScriptedIO())

    @pytest.mark.parametrize(
        ("program", "message"),
        [
            ('begin;var v;set v len{"ab", 1, 2};end;', "optionally a count"),
            ('begin;var v;set v at{"ab", 0.5, 65, 1};end;', "optionally a value"),
        ],
    )
    def test_builtin_arity_errors(self, program: str, message: str) -> None:
        with pytest.raises(HaltError, match=message):
            run([program], ScriptedIO())

    @pytest.mark.parametrize(
        ("lines", "message"),
        [
            (["begin;var v x;end;"], "trailing text after variable name"),
            (["begin;turn right x;end;"], "trailing text"),
            (
                ["begin;var v;set v f{1};end;", "func f{a};end a b;"],
                "trailing text after end value",
            ),
        ],
    )
    def test_trailing_text_is_malformed(self, lines: list[str], message: str) -> None:
        with pytest.raises(ValueError, match=message):
            run(lines, ScriptedIO())

    def test_a_malformed_number_literal_is_refused(self) -> None:
        with pytest.raises(ValueError, match="bad number literal"):
            run(["begin;var v;set v 1.2.3;end;"], ScriptedIO())
