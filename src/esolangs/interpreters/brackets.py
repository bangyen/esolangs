"""Shared bracket-matching helper for the interpreters.

Every interpreter that rejects an unbalanced program statically raises
``unmatched '<char>' at position <i>`` as a :class:`ValueError`, spelled
once here; the glyphs are a parameter (``[]``, ``l``, ``{}``).  Not used
by run-time scanners, which have no position to name,
nor by languages where an unmatched bracket is legal.  Token-level
matchers differ in opener,
closer, return shape and error, so each spells its six-line stack loop
itself; all build a table once at load, never a scan per jump.
"""

from __future__ import annotations

from esolangs.interpreters.source_hints import syntax_error


def unmatched(char: str, position: int, hint: str | None = None) -> ValueError:
    """Build the rejection every static bracket scan raises."""
    return syntax_error(
        f"unmatched {char!r} at position {position}",
        hint or "pair each loop opener with its corresponding closing delimiter",
    )


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
                raise unmatched(
                    close_char,
                    i,
                    f"put a matching {open_char!r} before this {close_char!r}",
                )
            open_i = stack.pop()
            res[open_i] = i
            res[i] = open_i
    if stack:
        raise unmatched(
            open_char, stack[-1], f"close this {open_char!r} with {close_char!r}"
        )
    return res
