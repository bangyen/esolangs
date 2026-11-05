"""Input-reading examples whose native EOF raises to the caller."""

import esolangs


def reading_languages() -> list[str]:
    """The examples whose programs read their inputs from the stream."""
    from esolangs.generation.examples import BOOLEAN_EXAMPLES
    from esolangs.registry import LANGUAGES

    eof = {lang.interpreter for lang in LANGUAGES.values() if lang.eof}
    return sorted(
        name
        for name, example in BOOLEAN_EXAMPLES.items()
        # A ``fill`` means the bits are embedded in the program text, so
        # the language has no input command to run out of.
        if example.fill is None and example.interpreter not in eof
    )


def assert_echoes_a_newline(language: str, program: str) -> None:
    """``program`` echoes one character; a newline must come back as one."""
    assert esolangs.run(language, program, stdin="\n") == "\n"


def assert_reads_tokens_on_one_line(language: str) -> None:
    """A numeric reader takes ``0 1`` on one line as two inputs.

    Each numeric reader calls this from its own test file.
    """
    program = esolangs.generate(language, "0110")
    assert (
        esolangs.read_answer(language, esolangs.run(language, program, stdin="0 1"))
        == "1"
    )
