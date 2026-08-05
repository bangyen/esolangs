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
