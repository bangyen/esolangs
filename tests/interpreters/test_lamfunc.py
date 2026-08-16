"""Unit tests for the Lamfunc interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.lamfunc import run


def run_program(code: str) -> str:
    io = ScriptedIO()
    run(code, io)
    return io.getvalue()


class TestBuiltins:
    def test_print_number_as_binary(self) -> None:
        assert run_program("p 5") == "101"
        assert run_program("p 0") == "0"

    def test_print_binary_literal(self) -> None:
        assert run_program("p 0b101") == "101"

    def test_equality(self) -> None:
        assert run_program("p eq 1 1") == "1"
        assert run_program("p eq 1 2") == "0"

    def test_if_selects_branch(self) -> None:
        assert run_program("p i 1 7 8") == "111"
        assert run_program("p i 0 7 8") == "1000"

    def test_if_is_lazy(self) -> None:
        # the unchosen branch's p must not run
        assert run_program("p i 1 3 p 9") == "11"

    def test_combine_bits(self) -> None:
        # 0b10 and 0b110 combine to 0b10110
        assert run_program("p cb 2 6") == "10110"

    def test_last_and_all_but_last_bit(self) -> None:
        assert run_program("p lb 5") == "1"
        assert run_program("p fb 5") == "10"

    def test_set_and_get_variable(self) -> None:
        assert run_program("p vs a 3 p vg a") == "1111"
        assert run_program("p vg missing") == "0"


class TestFunctions:
    def test_identity(self) -> None:
        # F id f - .f returns the argument without calling it
        assert run_program("F id f - .f\np id 7") == "111"

    def test_not(self) -> None:
        # the wiki's not: eq x eq .i .eq
        assert run_program("F not x - eq x eq .i .eq\np not 0") == "1"
        assert run_program("F not x - eq x eq .i .eq\np not 1") == "0"

    def test_call_bound_function(self) -> None:
        # c .p 5 binds a=p, b=5 and calls p 5
        assert run_program("F c a b - a b\np c .p 5") == "101101"

    def test_nested_call(self) -> None:
        # f g x y is f(g(x), y): p takes one arg, so p p 5 prints twice
        assert run_program("p p 5") == "101101"


class TestErrors:
    def test_redefinition_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="redefined"):
            run_program("F f x - x\nF f y - y")

    def test_undefined_function_halts(self) -> None:
        with pytest.raises(HaltError, match="undefined"):
            run_program("nosuch 1")

    def test_definition_needs_dash(self) -> None:
        with pytest.raises(ValueError, match="'-'"):
            run_program("F f x x")
