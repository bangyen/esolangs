"""Actionable notes on rejected source, without changing its diagnostic."""

from collections.abc import Iterable
from difflib import get_close_matches


def syntax_error(
    message: str, hint: str, *, error_type: type[ValueError] = ValueError
) -> ValueError:
    """Return a ValueError carrying one source-repair hint."""
    error = error_type(message)
    error.add_note(f"hint: {hint}")
    return error


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
