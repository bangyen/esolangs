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
def test_compiler_produces_assembly(module) -> None:
    """Each compiler turns a program into x86 assembly."""
    mod = importlib.import_module(module)
    output = mod.comp("Hello")
    assert output.startswith("global _start")
    assert "Hello" not in output  # source text is compiled, not embedded


def test_suffolk_compiler() -> None:
    mod = importlib.import_module("esolangs.compilers.assembly.suffolk")
    output = mod.comp("Hi", 1)
    assert output.startswith("global _start")
