"""Shared bracket-matching helper for the interpreters.

Every interpreter that rejects an unbalanced program statically raises
``unmatched '<char>' at position <i>`` as a :class:`ValueError`, spelled
once here; the glyphs are a parameter (``[]``, ``l``, ``{}``).  Not used
by run-time scanners (Circlefuck, bit~), which have no position to name,
nor by languages where an unmatched bracket is legal (Painfuck, Rotfuck,
Unsquare).  Token-level matchers (BIO, CVNC, Taglate) differ in opener,
closer, return shape and error, so each spells its six-line stack loop
itself; all build a table once at load, never a scan per jump.
"""

from __future__ import annotations


def unmatched(char: str, position: int) -> ValueError:
    """Build the rejection every static bracket scan raises."""
    return ValueError(f"unmatched {char!r} at position {position}")


def match_brackets(
    code: str, open_char: str = "[", close_char: str = "]"
) -> dict[int, int]:
    """Map each bracket to its partner, ``{open: close, close: open}``.

    Raises :class:`ValueError` if unbalanced: an unmatched closer at its own
    position, an unmatched opener at the innermost still waiting.
    """
    stack: list[int] = []
    res: dict[int, int] = {}
    for i, char in enumerate(code):
        if char == open_char:
            stack.append(i)
        elif char == close_char:
            if not stack:
                raise unmatched(close_char, i)
            open_i = stack.pop()
            res[open_i] = i
            res[i] = open_i
    if stack:
        raise unmatched(open_char, stack[-1])
    return res
