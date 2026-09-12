r"""Shared bracket-matching helper for the interpreters."""

from __future__ import annotations


def unmatched(char: str, position: int) -> ValueError:
    r"""Build the rejection every static bracket scan raises."""
    return ValueError(f"unmatched {char!r} at position {position}")


def match_brackets(
    code: str, open_char: str = "[", close_char: str = "]"
) -> dict[int, int]:
    r"""Map each bracket to its partner, ``{open: close, close: open}``."""
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
