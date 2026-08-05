"""Unit tests for the x86 assembly compilers."""

import importlib

import pytest

COMPILERS = [
    "esolangs.compilers.assembly.bfstack",
    "esolangs.compilers.assembly.home-row",
    "esolangs.compilers.assembly.jaune",
    "esolangs.compilers.assembly.unsquare",
]


@pytest.mark.parametrize("module", COMPILERS)
def test_compiler_produces_assembly(module: str) -> None:
    """Each compiler turns a program into x86 assembly."""
    mod = importlib.import_module(module)
    output = mod.comp("Hello")
    assert output.startswith("global _start")
    assert "Hello" not in output  # source text is compiled, not embedded


def test_suffolk_compiler() -> None:
    mod = importlib.import_module("esolangs.compilers.assembly.suffolk")
    output = mod.comp("Hi", 1)
    assert output.startswith("global _start")


class TestBFStackParse:
    def test_group_consecutive(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert mod.parse(">+++.") == [(">", 1), ("+", 3), (".", 1)]

    def test_plus_minus_cancel(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert mod.parse("++--") == []

    def test_push_pop_removed(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert mod.parse(">[+-]<") == [(">", 1), ("<", 1)]

    def test_zero_loop_optimization(self) -> None:
        """A loop that zeroes its cell compiles to a plain zero."""
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert mod.parse("++++[>++<-]") == [("0", 1)]

    def test_empty_program(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert mod.parse("") == []

    def test_empty_bracket_removed(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert mod.parse(">[]") == [(">", 1)]


class TestBFStackComp:
    def test_loop_generates_output_and_syscall(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        output = mod.comp("+[>].")
        assert "output:" in output
        assert "int 80h" in output
        assert ".T1:" in output  # loop label emitted

    def test_input_emits_input_label(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert "input:" in mod.comp(">,")


def test_unsquare_emits_syscalls() -> None:
    mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
    assert "int 80h" in mod.comp("ab")


class TestHomeRow:
    def test_arithmetic(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert "inc dword" in mod.comp("a")
        assert "add dword" in mod.comp("aa")
        assert "dec dword" in mod.comp("s")
        assert "sub dword" in mod.comp("ss")

    def test_movement(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert "down:" in mod.comp("d")
        assert "right:" in mod.comp("f")

    def test_output(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert "print:" in mod.comp("akk")

    def test_conditionals_and_loop(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert ".skip" in mod.comp("j")
        assert ".top" in mod.comp("l")
        assert ".bot" in mod.comp("l")

    def test_halt(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert "int 80h" in mod.comp(";")


class TestJaune:
    def test_arithmetic(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "inc dword" in mod.comp("1+")
        assert "dec dword" in mod.comp("1-")

    def test_subroutines(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "call output" in mod.comp("^")
        assert "call input" in mod.comp("v")
        assert "call left" in mod.comp("<")

    def test_labels_and_jumps(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert ".label" in mod.comp("5:")
        assert "jne" in mod.comp("5?")
        assert "je " in mod.comp("5!")

    def test_subroutine_call(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "call sub" in mod.comp("5@")

    def test_control_flow(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "int 80h" in mod.comp(".")
        assert "ret" in mod.comp(";")
        assert "sub ecx" in mod.comp(">")

    def test_counted_commands(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "mov esi, 2" in mod.comp("^^")
        assert "mov esi, 2" in mod.comp("&&")
        assert "add dword" in mod.comp("2+")
        assert "sub dword" in mod.comp("3-")

    def test_load_and_zero(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "mov edi" in mod.comp("#")
        assert "mov dword [ecx], 0" in mod.comp("%")

    def test_switch_controls(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert ".switch" in mod.comp("v?")
        assert "call switch" in mod.comp("v@")

    def test_subroutine_label(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "sub" in mod.comp("5$")


class TestUnsquare:
    def test_register_commands(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        assert "call zero" in mod.comp("O")
        assert "call one" in mod.comp("I")
        assert "call down" in mod.comp("A")
        assert "call up" in mod.comp("P")
        assert "call swap" in mod.comp("S")

    def test_io(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        assert "call output" in mod.comp("o")
        assert "call input" in mod.comp("i")

    def test_arithmetic_and_shift(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        assert "add edi" in mod.comp("+")
        assert "sub edi" in mod.comp("-")
        assert "shl edi" in mod.comp("x")

    def test_loops(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        output = mod.comp("O>I<")
        assert ".T1" in output
        assert ".B1" in output

    def test_zero_one_with_address(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        assert "mov edi" in mod.comp("OA")
        assert "mov edi" in mod.comp("IA")


class TestSuffolkComp:
    def test_compiles_various_programs(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.suffolk")
        for program in ["!<.", "!!", ">", ">!<", "."]:
            output = mod.comp(program, 1)
            assert output.startswith("global _start")
            assert output
