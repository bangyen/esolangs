"""Actionable notes on rejected source, without changing its diagnostic."""

import shlex
from collections.abc import Callable, Iterable
from difflib import get_close_matches

from esolangs.exceptions import ProgramError, ProgramNotFoundError


def display_label(text: str) -> str:
    """Keep a diagnostic label on one line without terminal controls."""
    return text if text.isprintable() else repr(text)[1:-1]


def is_option(value: str) -> bool:
    """Tell whether the CLI reads a leading dash as an option."""
    return len(value) > 1 and value[0] == "-" and not value[1].isdigit()


def can_render_argument(value: str, encoding: str) -> bool:
    """Check that an argument can be displayed without terminal controls."""
    if value and not value.isprintable():
        return False
    try:
        value.encode(encoding)
    except UnicodeEncodeError:
        return False
    return True


def shell_argument(
    value: str, *, encoding: str = "utf-8", force_separator: bool = False
) -> str | None:
    """Quote a CLI operand and protect a leading dash from option parsing."""
    if not can_render_argument(value, encoding):
        return None
    separator = "-- " if force_separator or is_option(value) else ""
    return separator + shlex.quote(value)


def syntax_repair(argument: str | None) -> str:
    """Point to the specification when its argument is safe to show."""
    if argument is None:
        return "check the operands and input against the language's syntax"
    return f"check the language syntax with esolangs describe --spec {argument}"


def syntax_error(
    message: str, hint: str, *, error_type: type[ValueError] = ValueError
) -> ValueError:
    """Return a ValueError carrying one source-repair hint."""
    error = error_type(message)
    error.add_note(f"hint: {hint}")
    return error


def program_error_context(message: str, cause: BaseException) -> ProgramError:
    """Keep the cause's repair notes when adding source or transport context."""
    failure = ProgramError(message)
    for note in getattr(cause, "__notes__", ()):
        failure.add_note(note)
    return failure


def source_read_error(label: str, cause: BaseException) -> ProgramError:
    """Describe a failed source read with its repair hint."""
    message = f"cannot read {display_label(label)}: {cause}"
    if isinstance(cause, FileNotFoundError):
        return with_hint(
            ProgramNotFoundError(message),
            "check that the source path exists and names the intended program file",
        )
    return with_hint(
        ProgramError(message), "check that the program file or stream is readable"
    )


def keyword_hint(word: str, known: Iterable[str], fallback: str) -> str:
    """Suggest one unambiguous keyword, otherwise give the accepted syntax."""
    vocabulary = sorted(known)
    folded = [
        candidate for candidate in vocabulary if candidate.casefold() == word.casefold()
    ]
    close = folded or get_close_matches(word, vocabulary, n=2, cutoff=0.65)
    return f"did you mean {close[0]!r}?" if len(close) == 1 else fallback


def error_text(
    error: BaseException, *, render_hint: Callable[[str], str] | None = None
) -> str:
    """Render the diagnostic and its hints, leaving other exception notes alone."""
    hints = (
        note if render_hint is None else render_hint(note)
        for note in getattr(error, "__notes__", ())
        if note.startswith("hint:")
    )
    return "\n".join((str(error), *hints))


def with_hint[E: Exception](error: E, hint: str) -> E:
    """Attach guidance without changing an error's type or diagnostic."""
    error.add_note(f"hint: {hint}")
    return error
