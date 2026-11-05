"""Character streams preserve newlines; EOF remains language-specific."""

import importlib
from unittest.mock import patch

import pytest

import esolangs
from esolangs.runtime.io import IO, ScriptedIO
from tests.support.input_convention import (
    assert_echoes_a_newline,
)
from tests.support.input_convention import reading_languages as _reading_languages
from tests.support.reference import REFERENCE


def test_character_input_preserves_newline() -> None:
    assert_echoes_a_newline(REFERENCE, ",.")


def test_newline_is_distinct_from_eof() -> None:
    source = ScriptedIO("\n")
    assert source.input_char() == 10
    with pytest.raises(EOFError):
        source.input_char()


def test_stream_echo_preserves_characters_on_the_same_line() -> None:
    assert esolangs.run(REFERENCE, ",.,.,.", stdin="ab\n") == "ab\n"


def test_interactive_empty_line_is_a_newline_character() -> None:
    with patch("builtins.input", return_value=""):
        assert IO().input_char() == 10


# What a language does when a *reading* program is handed no input at all.
# The default is that the ``EOFError`` escapes, so the caller sees a real end
# of input.  A language that answers differently says why in its
# ``LANGUAGE``'s ``eof=``: a statement about it, not an exception to ignore.


@pytest.mark.parametrize("name", _reading_languages())
def test_running_out_of_input_reaches_the_caller(name: str) -> None:
    """A program that reads, handed nothing, raises rather than inventing."""
    from esolangs.generation.examples import BOOLEAN_EXAMPLES

    example = BOOLEAN_EXAMPLES[name]
    from esolangs.raster import Raster

    program = example.generator("0110")
    if isinstance(program, Raster):
        from esolangs import run

        with pytest.raises(EOFError):
            run(name, program, stdin="")
        return
    module = importlib.import_module(
        f"esolangs.languages.{example.interpreter}.interpreter"
    )
    argument = program.splitlines() if example.split else program
    extra = {key: value for key, value in example.kwargs if key != "seed"}
    try:
        module.run(argument, io=ScriptedIO(""), **extra)
    except EOFError:
        return
    pytest.fail(
        f"{name} ran past EOF; if its spec gives EOF a value, "
        f'add eof="<what it does>" to its LANGUAGE'
    )
