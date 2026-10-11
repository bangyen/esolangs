"""Character streams preserve newlines; EOF remains language-specific."""

import importlib
from unittest.mock import patch

import pytest

import esolangs
from esolangs.interpreters.io import IO, ScriptedIO
from tests.reference import REFERENCE


def assert_echoes_a_newline(language: str, program: str) -> None:
    """``program`` echoes one character; a newline must come back as one."""
    assert esolangs.run(language, program, stdin="\n") == "\n"


def test_character_input_preserves_newline():
    assert_echoes_a_newline(REFERENCE, ",.")


def test_newline_is_distinct_from_eof():
    source = ScriptedIO("\n")
    assert source.input_char() == 10
    with pytest.raises(EOFError):
        source.input_char()


def test_stream_echo_preserves_characters_on_the_same_line():
    assert esolangs.run(REFERENCE, ",.,.,.", stdin="ab\n") == "ab\n"


def test_interactive_empty_line_is_a_newline_character():
    with patch("builtins.input", return_value=""):
        assert IO().input_char() == 10


def assert_reads_tokens_on_one_line(language: str) -> None:
    """A numeric reader takes ``0 1`` on one line as two inputs.

    Each numeric reader calls this from its own test file.
    """
    program = esolangs.generate(language, "0110")
    assert (
        esolangs.read_answer(language, esolangs.run(language, program, stdin="0 1"))
        == "1"
    )


# What a language does when a *reading* program is handed no input at all.
# The default is that the ``EOFError`` escapes, so the caller sees a real end
# of input.  A language that answers differently says why in its
# ``LANGUAGE``'s ``eof=``: a statement about it, not an exception to ignore.
def _reading_languages() -> list[str]:
    """The examples whose programs read their inputs from the stream."""
    from esolangs.registry import LANGUAGES
    from esolangs.tools.examples import BOOLEAN_EXAMPLES

    eof = {lang.interpreter for lang in LANGUAGES.values() if lang.eof}
    return sorted(
        name
        for name, example in BOOLEAN_EXAMPLES.items()
        # A ``fill`` means the bits are embedded in the program text, so
        # the language has no input command to run out of.
        if example.fill is None and example.interpreter not in eof
    )


@pytest.mark.parametrize("name", _reading_languages())
def test_running_out_of_input_reaches_the_caller(name: str) -> None:
    """A program that reads, handed nothing, raises rather than inventing."""
    from esolangs.tools.examples import BOOLEAN_EXAMPLES

    example = BOOLEAN_EXAMPLES[name]
    from esolangs.raster import Raster

    program = example.generator("0110")
    if isinstance(program, Raster):
        from esolangs import run

        with pytest.raises(EOFError):
            run(name, program, stdin="")
        return
    module = importlib.import_module("esolangs.interpreters." + example.interpreter)
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
