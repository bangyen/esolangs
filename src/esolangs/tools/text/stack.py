"""Stack text generators."""

from esolangs.tools.text.helpers import _literal_chunks

__all__ = ["modulous"]

# ``PSH STR`` pushes the characters and ``PRT`` pops one, so printing a
# string is the pop repeated by the back-jump until the stack runs out.
_MODULOUS_PRINT = '[PSH STR "{}"][PRT STR][JMP B 1 NIF 0]'


def modulous(text: str, width: int | None = None) -> str:
    """Build a Modulous program that outputs ``text``.

    Plain text is pushed as one ``STR`` literal and printed with ``PRT STR``;
    text containing a quote, bracket, or NUL falls back to per-character
    ``INT`` pushes so the literal is never broken.

    A ``width`` splits the text across several push-and-print statements,
    one per line.  Each carries its own ``JMP`` loop, since that loop is
    what drains the string a character at a time; the fallback form needs no
    such split, being per-character brackets that
    :mod:`~esolangs.tools.wrap` can already break between.
    """
    if not text or '"' in text or "[" in text or "]" in text or "\x00" in text:
        return "".join(f"[PSH INT {ord(c)}][PRT]" for c in text) + "[END]"
    chunks = _literal_chunks(text, width, len(_MODULOUS_PRINT.format("")))
    return "\n".join(_MODULOUS_PRINT.format(chunk) for chunk in chunks)
