"""Shared helpers for the interpreters."""

from __future__ import annotations

from esolangs.interpreters.source_hints import syntax_error


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
                raise syntax_error(
                    f"malformed memory token: {tok!r}",
                    "write whitespace-separated decimal integers; # starts a comment",
                ) from None
    return tokens
