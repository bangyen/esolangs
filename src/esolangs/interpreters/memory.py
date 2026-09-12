"""Shared helpers for the interpreters."""

from __future__ import annotations


def parse_int_memory(code: str) -> list[int]:
    """Split ``code`` into a list of whitespace-separated integers.

    ``#`` starts a comment to the end of its line; a non-integer token is a
    malformed program (:class:`ValueError`).
    """
    tokens: list[int] = []
    for line in code.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        for tok in line.split():
            try:
                tokens.append(int(tok))
            except ValueError:
                raise ValueError(f"malformed memory token: {tok!r}") from None
    return tokens
