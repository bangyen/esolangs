"""Verify the BF -> ASCII-art transpiler.

The transpiler's contract is that a brainfuck program and its ASCII-art
translation are interchangeable: each brainfuck command becomes an art
block, ``ascii-art.parse`` recovers the original commands, and both programs
run to identical output through their respective interpreters.  A battery
of programs exercises loops, nested loops, input, pointer movement, cell
wrapping, and comment-stripping.
"""

import importlib

import pytest

import esolangs
from esolangs.exceptions import (
    EsolangError,
    UnsupportedTranspilationError,
)

ascii_art = importlib.import_module("esolangs.interpreters.tape_based.ascii-art")


# (brainfuck program, stdin) pairs; every pair must terminate and agree.
BATTERY = (
    ("+[>+<-]>.", ""),
    ("+++[>++<-]>++.", ""),
    ("+++[>++[>+<-]<-]>+++.", ""),
    (">+<<.", ""),
    (",>,<.>.", "a\nb"),
    (",[.-]", "a"),
    ("+++>+++<.>.", ""),
    ("+++++++++++++++++++++++++++++++++++++++++++++++++.", ""),
    (",", "a"),
    ("", ""),
    ("xx+++xx.xx", ""),
)

# a subset with pinned output, so the battery checks more than self-consistency
PINNED = {
    "+[>+<-]>.>": ("", "\x01"),
    "+++[>++<-]>+++.": ("", "\t"),
    "+++[>++[>+<-]<-]>+++.": ("", "\x03"),
    ">+<<.": ("", "\x00"),
    ",>,<.>.": ("a\nb", "ab"),
    "+++>+++<.>.": ("", "\x03\x03"),
    "+++++++++++++++++++++++++++++++++++++++++++++++++.": ("", "1"),
}


def _filter(program: str) -> str:
    return "".join(c for c in program if c in "+-<>.,[]")


@pytest.mark.parametrize(("program", "stdin"), BATTERY)
def test_transpiled_output_matches_source(program: str, stdin: str) -> None:
    art = esolangs.transpile("BF", "ASCII art", program)
    assert esolangs.run("BF", program, stdin) == esolangs.run("ASCII art", art, stdin)


@pytest.mark.parametrize(("program", "pair"), tuple(PINNED.items()))
def test_pinned_outputs(program: str, pair: tuple[str, str]) -> None:
    stdin, expected = pair
    assert esolangs.run("BF", program, stdin) == expected


@pytest.mark.parametrize(("program", "stdin"), BATTERY)
def test_parse_recovers_source(program: str, stdin: str) -> None:
    art = esolangs.transpile("BF", "ASCII art", program)
    assert ascii_art.parse(art) == _filter(program)


@pytest.mark.parametrize(("program", "stdin"), BATTERY)
def test_reverse_transpiler_recovers_source(program: str, stdin: str) -> None:
    """ASCII art -> BF inverts BF -> ASCII art for well-formed art."""
    art = esolangs.transpile("BF", "ASCII art", program)
    assert esolangs.transpile("ASCII art", "BF", art) == _filter(program)


@pytest.mark.parametrize(("program", "stdin"), BATTERY)
def test_reverse_transpiled_output_matches_source(program: str, stdin: str) -> None:
    art = esolangs.transpile("BF", "ASCII art", program)
    bf_program = esolangs.transpile("ASCII art", "BF", art)
    assert esolangs.run("BF", bf_program, stdin) == esolangs.run(
        "ASCII art", art, stdin
    )


def test_reverse_round_trips_art() -> None:
    """Re-encoding recovered art reproduces it byte for byte."""
    for program, _ in BATTERY:
        art = esolangs.transpile("BF", "ASCII art", program)
        assert (
            esolangs.transpile(
                "BF", "ASCII art", esolangs.transpile("ASCII art", "BF", art)
            )
            == art
        )


def test_reverse_empty_program() -> None:
    assert esolangs.transpile("ASCII art", "BF", "") == ""
    assert esolangs.transpile("BF", "ASCII art", "") == ""


@pytest.mark.parametrize("text", ["Hello, World!", "Hi", "\x00\x01"])
def test_generator_is_transpiled_generator(text: str) -> None:
    """The ASCII-art generator is exactly the BF generator, transpiled."""
    bf_program = esolangs.generate("BF", text)
    art = esolangs.transpile("BF", "ASCII art", bf_program)
    assert esolangs.generate("ASCII art", text) == art
    assert esolangs.run("ASCII art", art) == text


@pytest.mark.parametrize("text", ["Hello, World!", "Hi"])
def test_generator_inverse(text: str) -> None:
    """The reverse transpiler recovers the BF generator's program."""
    art = esolangs.generate("ASCII art", text)
    assert esolangs.transpile("ASCII art", "BF", art) == esolangs.generate("BF", text)


def test_empty_program_stays_empty() -> None:
    art = esolangs.transpile("BF", "ASCII art", "")
    assert art == ""
    assert esolangs.run("ASCII art", art) == ""


def test_unsupported_pair_raises() -> None:
    with pytest.raises(UnsupportedTranspilationError):
        esolangs.transpile("BF", "CircleFuck", "x")
    with pytest.raises(UnsupportedTranspilationError):
        esolangs.transpile("Sophie", "Modulous", "x")
    assert issubclass(UnsupportedTranspilationError, EsolangError)
    assert issubclass(UnsupportedTranspilationError, ValueError)


def test_listed_transpilers_are_known_languages() -> None:
    """Every transpiler source and target is a registered language."""
    from esolangs.tools.transpilers import TRANSPILERS

    known = set(esolangs.list_languages())
    for source, target in TRANSPILERS:
        assert source in known
        assert target in known
