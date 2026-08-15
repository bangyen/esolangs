"""Shared bracket-matching helper for the interpreters."""

from __future__ import annotations


def match_brackets(code: str) -> dict[int, int]:
    """Map each bracket to its partner, ``{open: close, close: open}``.

    Raises :class:`ValueError` if the brackets are unbalanced.
    """
    stack: list[int] = []
    res: dict[int, int] = {}
    for i, char in enumerate(code):
        if char == "[":
            stack.append(i)
        elif char == "]":
            if not stack:
                raise ValueError(f"unmatched ']' at position {i}")
            open_i = stack.pop()
            res[open_i] = i
            res[i] = open_i
    if stack:
        raise ValueError(f"unmatched '[' at position {stack[-1]}")
    return res
