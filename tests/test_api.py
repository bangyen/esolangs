"""Tests for the public package API."""

import pytest

import esolangs
from esolangs.exceptions import (
    EsolangError,
    UnknownLanguageError,
    UnsupportedTranspilationError,
)
from esolangs.tools import boolean


@pytest.mark.parametrize("language", ["Sophie", "Circlefuck", "BFStack", "huf"])
def test_generate_round_trips(language: str) -> None:
    program = esolangs.generate(language, "Hi")
    assert esolangs.run(language, program) == "Hi"


def test_run_feeds_stdin() -> None:
    program = boolean.circlefuck("1101", 2)
    assert esolangs.run("Circlefuck", program, stdin="1\n0\n") == "0"
    assert esolangs.run("Circlefuck", program, stdin="0\n1\n") == "1"


def test_list_languages() -> None:
    names = esolangs.list_languages()
    assert "Sophie" in names
    assert "Circlefuck" in names
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
        esolangs.run("Circlefuck", program, stdin="")


def test_transpile_round_trips() -> None:
    program = esolangs.generate("brainfuck", "Hi")
    circlefuck = esolangs.transpile("brainfuck", "Circlefuck", program)
    assert esolangs.run("Circlefuck", circlefuck) == "Hi"


def test_transpile_unsupported_pair_raises() -> None:
    with pytest.raises(UnsupportedTranspilationError):
        esolangs.transpile("brainfuck", "Unsquare", "x")
    assert issubclass(UnsupportedTranspilationError, EsolangError)
    assert issubclass(UnsupportedTranspilationError, ValueError)


def test_transpile_to_circlefuck() -> None:
    program = esolangs.generate("brainfuck", "Hi")
    circlefuck = esolangs.transpile("brainfuck", "Circlefuck", program)
    assert esolangs.run("Circlefuck", circlefuck) == "Hi"


def test_run_timeout_halts_runaway_program() -> None:
    """A program that never halts raises HaltError once the timeout elapses."""
    from esolangs.exceptions import HaltError

    with pytest.raises(HaltError, match="timeout"):
        esolangs.run("brainfuck", "+[]", timeout=0.1)


def test_run_timeout_lets_fast_program_finish() -> None:
    program = "++++++++[>++++++++<-]>+++."
    assert esolangs.run("brainfuck", program, timeout=5) == "C"


def test_run_timeout_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        esolangs.run("brainfuck", "+", timeout=0)
    with pytest.raises(ValueError, match="positive"):
        esolangs.run("brainfuck", "+", timeout=-1)


def test_run_timeout_requires_main_thread() -> None:
    """The SIGALRM guard needs a Unix main thread; elsewhere timeout is refused."""
    import threading

    out: list[BaseException | None] = [None]

    def runner() -> None:
        try:
            esolangs.run("brainfuck", "+", timeout=1)
        except BaseException as exc:
            out[0] = exc

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join(5)
    assert isinstance(out[0], ValueError)
    assert "SIGALRM" in str(out[0])


def test_describe_structured_summary() -> None:
    info = esolangs.describe("brainfuck")
    assert info["name"] == "brainfuck"
    assert info["state_model"] == "tape"
    assert info["text_generator"] is True
    assert info["boolean_generator"] is True
    assert info["interpreter"] == "tape_based.brainfuck"
    assert ("brainfuck", "Circlefuck") in info["transpilers"]
    assert info["wiki_url"] == "https://esolangs.org/wiki/brainfuck"


def test_describe_covers_state_models() -> None:
    assert esolangs.describe("Forþ")["state_model"] == "stack"
    assert esolangs.describe("Decleq")["state_model"] == "register"
    assert esolangs.describe("LaserFuck")["state_model"] == "grid"
    assert esolangs.describe("NoComment")["boolean_generator"] is True


def test_describe_unknown_language_raises() -> None:
    with pytest.raises(UnknownLanguageError):
        esolangs.describe("NoSuchLanguage")


def test_describe_language_without_interpreter() -> None:
    info = esolangs.describe("123")
    assert info["state_model"] == "tape"
    assert isinstance(info["transpilers"], list)
