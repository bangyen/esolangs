"""Preview spelling edits without executing or rewriting a program."""

from typing import cast

from esolangs._execution import interpreter_errors, interpreter_module
from esolangs.cli_args import _check_count, _errors, _split_positional
from esolangs.cli_io import _read_program
from esolangs.registry import LANGUAGES, SourceKind, resolve


def _suggest(rest: list[str]) -> None:
    """Print located corrections; leave the file and stdin untouched."""
    rest = _split_positional(rest, set())
    _check_count("suggest", rest, 2)
    with _errors():
        language = resolve(rest[0])
    # A language offers its own: ``suggest_corrections`` in its interpreter.
    handler = getattr(interpreter_module(language), "suggest_corrections", None)
    source = _read_program(rest[1], language=language)
    if handler is None:
        reason = (
            "raster source has no command spellings to correct"
            if LANGUAGES[language].source_kind == SourceKind.RASTER
            else "no safe keyword correction rules are available for this language"
        )
        print(f"{language}: {reason}; the program is not validated")
        return
    source = cast(str, source)
    with (
        _errors(),
        interpreter_errors(
            "source preview exceeds parser recursion depth", language=language
        ),
    ):
        corrections = handler(source)
    line, column, cursor = 1, 1, 0
    for correction in corrections:
        prefix = source[cursor : correction.start]
        newlines = prefix.count("\n")
        line += newlines
        column = len(prefix) - prefix.rfind("\n") if newlines else column + len(prefix)
        cursor = correction.start
        print(
            f"{rest[1]}:{line}:{column}: {correction.before!r} -> "
            f"{correction.after!r}; {correction.reason}"
        )
    if not corrections:
        print("no unambiguous command corrections found; the program is not validated")
