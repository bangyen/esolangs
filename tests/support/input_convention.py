"""Input-reading examples whose native EOF raises to the caller."""


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
