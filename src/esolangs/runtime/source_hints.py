"""Actionable notes on rejected source, without changing its diagnostic."""

from collections.abc import Iterable
from difflib import get_close_matches

from esolangs.exceptions import ProgramError, ProgramNotFoundError


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
    message = f"cannot read {label}: {cause}"
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


def error_text(error: BaseException) -> str:
    """Render the diagnostic and its hints, leaving other exception notes alone."""
    hints = (
        note for note in getattr(error, "__notes__", ()) if note.startswith("hint:")
    )
    return "\n".join((str(error), *hints))


def with_hint[E: Exception](error: E, hint: str) -> E:
    """Attach guidance without changing an error's type or diagnostic."""
    error.add_note(f"hint: {hint}")
    return error
