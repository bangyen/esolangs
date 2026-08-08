"""Tests for the public package API."""

import pytest

import esolangs
from esolangs.exceptions import (
    EsolangError,
    UnknownLanguageError,
    UnsupportedTranspilationError,
)
from esolangs.tools import boolean


@pytest.mark.parametrize("language", ["Sophie", "CircleFuck", "BFStack", "huf"])
def test_generate_round_trips(language: str) -> None:
    program = esolangs.generate(language, "Hi")
    assert esolangs.run(language, program) == "Hi"


def test_run_feeds_stdin() -> None:
    program = boolean.circlefuck("1101", 2)
    assert esolangs.run("CircleFuck", program, stdin="1\n0\n") == "0"
    assert esolangs.run("CircleFuck", program, stdin="0\n1\n") == "1"


def test_list_languages() -> None:
    names = esolangs.list_languages()
    assert "Sophie" in names
    assert "CircleFuck" in names
    assert names == sorted(names)


def test_unknown_language_raises() -> None:
    with pytest.raises(UnknownLanguageError):
        esolangs.generate("NoSuchLanguage", "x")
    with pytest.raises(UnknownLanguageError):
        esolangs.run("NoSuchLanguage", "x")
    assert issubclass(UnknownLanguageError, EsolangError)
    assert issubclass(UnknownLanguageError, ValueError)


def test_run_eof_when_input_runs_out() -> None:
    program = boolean.circlefuck("10", 1)  # reads one input bit
    with pytest.raises(EOFError):
        esolangs.run("CircleFuck", program, stdin="")


def test_transpile_round_trips() -> None:
    program = esolangs.generate("BF", "Hi")
    art = esolangs.transpile("BF", "ASCII art", program)
    assert esolangs.run("ASCII art", art) == "Hi"


def test_transpile_reverse_round_trips() -> None:
    program = esolangs.generate("BF", "Hi")
    art = esolangs.transpile("BF", "ASCII art", program)
    recovered = esolangs.transpile("ASCII art", "BF", art)
    assert recovered == program
    assert esolangs.run("BF", recovered) == "Hi"


def test_transpile_unsupported_pair_raises() -> None:
    with pytest.raises(UnsupportedTranspilationError):
        esolangs.transpile("BF", "Unsquare", "x")
    assert issubclass(UnsupportedTranspilationError, EsolangError)
    assert issubclass(UnsupportedTranspilationError, ValueError)


def test_transpile_to_circlefuck() -> None:
    program = esolangs.generate("BF", "Hi")
    circlefuck = esolangs.transpile("BF", "CircleFuck", program)
    assert esolangs.run("CircleFuck", circlefuck) == "Hi"
