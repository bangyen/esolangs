"""Bounded empty-source runs for every registered interpreter."""

import os

import pytest

import esolangs
from esolangs.exceptions import ExecutionTimeoutError, HaltError, ProgramError
from esolangs.registry import LANGUAGES, SourceKind

# Empty-source rejections are language contracts, not arbitrary exceptions:
# each is its ``LANGUAGE``'s ``empty_program=``.
_REJECTION_KINDS = (ProgramError, HaltError)


def _check_empty_program(language: str) -> None:
    source = (
        esolangs.Raster((((255, 255, 255),),))
        if LANGUAGES[language].source_kind is SourceKind.RASTER
        else ""
    )
    isolated = os.name != "posix"
    options = {
        "timeout": 3,
        "isolated": isolated,
        "max_output": 1024 if isolated else None,
    }
    message = LANGUAGES[language].empty_program
    if not message:
        try:
            esolangs.run(language, source, **options)
        except esolangs.EsolangError as exc:
            pytest.fail(
                f"{language} refuses an empty program; if the spec does, add "
                f"empty_program={str(exc)!r} to its LANGUAGE"
            )
        return
    with pytest.raises(esolangs.EsolangError) as caught:
        esolangs.run(language, source, **options)
    error = caught.value
    assert type(error) in _REJECTION_KINDS, f"{type(error).__name__}: {error}"
    assert str(error) == message, f"{language}: {error}"


@pytest.mark.medium
@pytest.mark.parametrize("language", sorted(LANGUAGES))
def test_empty_program_terminates(language: str) -> None:
    _check_empty_program(language)


#: A language whose spec rejects an empty program, with the message it uses.
_REJECTS = next(name for name, lang in LANGUAGES.items() if lang.empty_program)


@pytest.mark.parametrize("error", [TypeError, AttributeError, RuntimeError])
def test_unexpected_failure_is_not_an_empty_source_rejection(monkeypatch, error):
    def broken_run(*_args, **_kwargs):
        raise error("injected constructor failure")

    monkeypatch.setattr(esolangs, "run", broken_run)
    with pytest.raises(error, match="injected constructor failure"):
        _check_empty_program(_REJECTS)


def test_wrong_rejection_message_fails(monkeypatch):
    def broken_run(*_args, **_kwargs):
        raise ProgramError("injected parser failure")

    monkeypatch.setattr(esolangs, "run", broken_run)
    with pytest.raises(AssertionError, match="injected parser failure"):
        _check_empty_program(_REJECTS)


def test_timeout_is_not_an_empty_source_rejection(monkeypatch):
    def timed_run(*_args, **_kwargs):
        raise ExecutionTimeoutError(LANGUAGES[_REJECTS].empty_program)

    monkeypatch.setattr(esolangs, "run", timed_run)
    with pytest.raises(AssertionError, match="ExecutionTimeoutError"):
        _check_empty_program(_REJECTS)
