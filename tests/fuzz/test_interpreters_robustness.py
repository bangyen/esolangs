"""Bounded empty-source runs for every registered interpreter."""

import os
import re

import pytest

import esolangs
from esolangs.exceptions import ExecutionTimeoutError, HaltError, ProgramError
from esolangs.registry import LANGUAGES, SourceKind

# Empty-source rejections are language contracts, not arbitrary exceptions.
_EMPTY_REJECTIONS = {
    "Alight": (ProgramError, "empty program"),
    "123": (ProgramError, "an empty 123 program never halts"),
    "Back": (ProgramError, "Back program cannot be empty"),
    "B-tapemark": (ProgramError, "B-tapemark program needs exactly one start marker"),
    "BF-PDA": (ProgramError, "BF-PDA program cannot be empty"),
    "Cyclic tag": (
        ProgramError,
        "Cyclic tag requires productions,queue using bits and semicolons",
    ),
    "Circlefuck": (ProgramError, "Circlefuck program cannot be empty"),
    "Clockwise": (ProgramError, "Clockwise program cannot be empty"),
    "CV(N)(C)": (ProgramError, "program is empty"),
    "Dig": (ProgramError, "Dig program cannot be empty"),
    "EGL": (ProgramError, "EGL program must begin with 'width,height:'"),
    "Flowchart": (ProgramError, "Flowchart program has no '( )' start node"),
    "Forbin": (ProgramError, "Forbin program has no main function"),
    # A blank raster is a white pixel: Raster itself refuses zero pixels.
    "Line": (ProgramError, "image contains no ink"),
    "Packlang": (ProgramError, "empty program"),
    "Polynomial": (ProgramError, "Polynomial program must start with 'f(x) = '"),
    "Streetcode": (ProgramError, "Streetcode program cannot be empty"),
    "Super SNUSP": (ProgramError, "Super SNUSP program cannot be empty"),
    "Suffolk": (ProgramError, "Suffolk program cannot be empty"),
    "thisthat": (HaltError, "thisthat needs at least one start node"),
    "Befunge": (ProgramError, "Befunge program cannot be empty"),
    "FRACTRAN": (ProgramError, "a FRACTRAN program needs a starting value"),
    "Fish": (ProgramError, "Fish program cannot be empty"),
    "INTERCAL": (
        HaltError,
        "INTERCAL program is insufficiently or excessively polite (E099)",
    ),
    "Thue": (
        ProgramError,
        "a Thue program needs a '::=' line with nothing but whitespace on either "
        "side, to separate its rules from its starting state",
    ),
    "Unlambda": (ProgramError, "an Unlambda program cannot be empty"),
}


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
    rejection = _EMPTY_REJECTIONS.get(language)
    if rejection is None:
        try:
            esolangs.run(language, source, **options)
        except esolangs.EsolangError as exc:
            pytest.fail(
                f"{language} refuses an empty program; if the spec does, add "
                f"{language!r}: ({type(exc).__name__}, {str(exc)!r}) to "
                "_EMPTY_REJECTIONS"
            )
        return
    kind, message = rejection
    with pytest.raises(kind, match=f"^{re.escape(message)}") as caught:
        esolangs.run(language, source, **options)
    assert type(caught.value) is kind
    assert str(caught.value) == message


@pytest.mark.medium
@pytest.mark.parametrize("language", sorted(LANGUAGES))
def test_empty_program_terminates(language: str) -> None:
    _check_empty_program(language)


def test_empty_rejections_name_registered_languages() -> None:
    assert _EMPTY_REJECTIONS.keys() <= LANGUAGES.keys()


@pytest.mark.parametrize("error", [TypeError, AttributeError, RuntimeError])
def test_unexpected_failure_is_not_an_empty_source_rejection(monkeypatch, error):
    def broken_run(*_args, **_kwargs):
        raise error("injected constructor failure")

    monkeypatch.setattr(esolangs, "run", broken_run)
    with pytest.raises(error, match="injected constructor failure"):
        _check_empty_program("Alight")


def test_wrong_rejection_message_fails(monkeypatch):
    def broken_run(*_args, **_kwargs):
        raise ProgramError("injected parser failure")

    monkeypatch.setattr(esolangs, "run", broken_run)
    with pytest.raises(AssertionError, match="injected parser failure"):
        _check_empty_program("Alight")


def test_timeout_is_not_an_empty_source_rejection(monkeypatch):
    def timed_run(*_args, **_kwargs):
        raise ExecutionTimeoutError(_EMPTY_REJECTIONS["thisthat"][1])

    monkeypatch.setattr(esolangs, "run", timed_run)
    with pytest.raises(AssertionError, match="ExecutionTimeoutError"):
        _check_empty_program("thisthat")
