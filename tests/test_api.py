"""Tests for the public package API."""

import warnings

import pytest

import esolangs
from esolangs import tools as boolean
from esolangs.exceptions import EsolangError, UnknownLanguageError


@pytest.mark.parametrize("language", ["Sophie", "Circlefuck", "BFStack"])
def test_generate_computes_its_table(language: str) -> None:
    """XOR, executed on all four rows -- the program, not just its text."""
    program = esolangs.generate(language, "0110")
    for row, expected in enumerate("0110"):
        stdin = esolangs.encode_inputs(
            language, [int(bit) for bit in format(row, "02b")]
        )
        assert esolangs.run(language, program, stdin) == expected


def test_run_feeds_stdin() -> None:
    program = boolean.circlefuck("1101")
    assert esolangs.run("Circlefuck", program, stdin="10") == "0"
    assert esolangs.run("Circlefuck", program, stdin="01") == "1"


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


def test_missing_dependency_error_is_public() -> None:
    assert issubclass(esolangs.MissingDependencyError, EsolangError)
    assert issubclass(esolangs.MissingDependencyError, ImportError)


def test_deliberate_error_keeps_partial_output(monkeypatch: pytest.MonkeyPatch) -> None:
    from esolangs.interpreters.io import ScriptedIO

    error = EsolangError("stop")

    def stop(
        _runner: object, _program: object, io: ScriptedIO, _timeout: object
    ) -> None:
        io.print_str("before")
        raise error

    monkeypatch.setattr(esolangs, "_run", stop)
    with pytest.raises(EsolangError) as caught:
        esolangs.run("brainfuck", "+")
    assert caught.value is error
    assert caught.value.partial_output == "before"
    assert caught.value.__notes__ == ["the program printed 'before' before this"]


def test_run_warns_when_input_runs_out() -> None:
    program = boolean.circlefuck("10")  # reads one input bit
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        esolangs.run("Circlefuck", program, stdin="")


def test_run_timeout_halts_runaway_program() -> None:
    """A program that never halts raises HaltError once the timeout elapses."""
    from esolangs.exceptions import HaltError

    with pytest.raises(HaltError, match="timeout"):
        esolangs.run("brainfuck", "+[]", timeout=0.1)


def test_run_timeout_halts_growing_3d_brainfuck_program() -> None:
    """The signal interrupts a 3D Brainfuck loop whose state never repeats."""
    program = "N+n+S"
    with pytest.raises(esolangs.ExecutionTimeoutError, match="timeout"):
        esolangs.run("3D Brainfuck", program, timeout=0.01)


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
    assert info["boolean_generator"] is True
    assert info["interpreter"] == "tape_based.brainfuck"
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


def test_generate_refuses_a_language_with_no_generator() -> None:
    """A registered language may have no generator, and must say so.

    Deadfish is the live instance this was written ahead of, and having one
    changed the answer.  The guard raised ``UnknownLanguageError``, whose
    message ends "`esolangs list` shows all of them" -- and `esolangs list`
    shows Deadfish, so the refusal contradicted itself the moment it could
    fire for real.  It is an ``ArgumentError`` now, which is still a
    ``ValueError`` for anyone catching broadly, and it says which fact about
    the language is the obstacle.
    """
    with pytest.raises(esolangs.ArgumentError) as exc:
        esolangs.generate("Deadfish", "0110")
    message = str(exc.value)
    assert "no boolean generator" in message
    assert "generator contracts" in message
    assert "'int'" in message


def test_an_unknown_language_is_still_unknown_to_generate() -> None:
    """The other arm, so the two refusals cannot collapse into one."""
    with pytest.raises(UnknownLanguageError):
        esolangs.generate("NoSuchLanguage", "0110")
