"""Character streams preserve newlines; EOF remains language-specific."""

import importlib
from unittest.mock import patch

import pytest

import esolangs
from esolangs.interpreters.io import IO, ScriptedIO


@pytest.mark.parametrize(
    ("language", "program"),
    [("brainfuck", ",."), ("3D Brainfuck", "su+dn,."), ("BFStack", ",.")],
)
def test_character_input_preserves_newline(language, program):
    assert esolangs.run(language, program, stdin="\n") == "\n"


def test_newline_is_distinct_from_eof():
    source = ScriptedIO("\n")
    assert source.input_char() == 10
    with pytest.raises(EOFError):
        source.input_char()


def test_stream_echo_preserves_characters_on_the_same_line():
    assert esolangs.run("brainfuck", ",.,.,.", "ab\n") == "ab\n"


def test_interactive_empty_line_is_a_newline_character():
    with patch("builtins.input", return_value=""):
        assert IO().input_char() == 10


@pytest.mark.parametrize("language", ["Befunge", "Line", "Piet"])
def test_numeric_readers_accept_tokens_on_the_same_line(language):
    program = esolangs.generate(language, "0110")
    assert esolangs.read_answer(language, esolangs.run(language, program, "0 1")) == "1"


#: What a language does when a *reading* program is handed no input at
#: all.  Twenty-two files pinned this one language at a time; the split
#: between the two answers is the interesting part, so it is written down
#: here rather than inferred.
#:
#: The default is that the ``EOFError`` escapes: the interpreter does not
#: catch it, so the caller sees a real end of input.  The languages below
#: answer differently, and each for a reason of its own -- so the set is a
#: statement about them, not a list of exceptions to ignore.
_EOF_IS_A_HALT: dict[str, str] = {
    "boolfuck": "EOF supplies zero bits",
    "piet": "an exhausted input command is ignored, as the spec requires",
    # Reads until the input runs out and treats that as its stop, which is
    # how its generated programs terminate at all.
    "suffolk": "reads to exhaustion, so EOF is the halt",
    # Read their inputs before the program runs, so an exhausted stream is
    # a load-time answer rather than a step that fails.
    "fargo": "the interpreter reads before the program starts",
    "circuit_diagram": "resolves its inputs while laying the grid",
    "flowchart": "reads at the switch, which a program without one skips",
    "sbleq": "a failed read leaves the cell alone and the program runs on",
    "malbolge": "an exhausted read is the value 59048, not an error",
    "packlang": "an exhausted charGet is newline byte 10",
    "polynomial": "an exhausted input instruction stores -1",
    # Both specs name the value a failed read answers with, so catching the
    # raise is what makes their own idioms work: FALSE's cat tests ``^``
    # against -1, and an Unlambda read-until-EOF loop needs the ``v`` branch.
    "false": "an exhausted '^' is the spec's -1",
    "fish": "an exhausted 'i' is the spec's -1",
    "unlambda": "an exhausted '@' hands its argument v, the spec's branch",
    "thisthat": "an exhausted '◇' sends the spec's empty transfer",
    # Wiki: the empty container sets IN "with EOF returning 0".
    "container": "an exhausted read sets IN to the spec's 0",
}


@pytest.mark.parametrize("name", sorted(_EOF_IS_A_HALT))
def test_every_eof_exemption_names_a_real_language(name: str) -> None:
    """An exemption whose language is gone must not linger unnoticed."""
    from esolangs.tools.examples import BOOLEAN_EXAMPLES

    assert name in BOOLEAN_EXAMPLES


def _reading_languages() -> list[str]:
    """The examples whose programs read their inputs from the stream."""
    from esolangs.tools.examples import BOOLEAN_EXAMPLES

    return sorted(
        name
        for name, example in BOOLEAN_EXAMPLES.items()
        # A ``fill`` means the bits are embedded in the program text, so
        # the language has no input command to run out of.
        if example.fill is None
        and name not in _EOF_IS_A_HALT
        # Circlefuck specifies that its input command is a no-op at EOF.
        and name != "circlefuck"
        # Suptiftam's read sits inside a loop that never ends without one,
        # so an empty stream is a hang rather than a raise.
        and name != "suptiftam"
        # Alight raises its own error before the read is reached.
        and name != "alight"
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
            run(name, program, "")
        return
    module = importlib.import_module("esolangs.interpreters." + example.interpreter)
    argument = program.splitlines() if example.split else program
    extra = {key: value for key, value in example.kwargs if key != "seed"}
    with pytest.raises(EOFError):
        module.run(argument, io=ScriptedIO(""), **extra)
