"""Tokenize Fargo lines and recover function definitions and calls."""

from collections.abc import Collection, Mapping
from dataclasses import dataclass

# The wiki renders the truth machine with zero-width spaces inside two of
# its lines; they are invisible presentation, not syntax, so the tokenizer
# drops them rather than letting them ride along inside a token.
_ZERO_WIDTH = "\u200b"


@dataclass(frozen=True)
class _Def:
    """One user-defined function: its parameters and its code tokens."""

    name: str
    params: tuple[str, ...]
    code: tuple[str, ...]


def _strip_comment(line: str) -> str:
    """Drop a ``#`` comment and the zero-width spaces the wiki renders."""
    return line.split("#", 1)[0].replace(_ZERO_WIDTH, "")


def _is_literal(token: str) -> bool:
    """Whether ``token`` is a binary literal (the regex ``/[0-1]+/``)."""
    return bool(token) and all(c in "01" for c in token)


def _bare_name(token: str) -> str:
    """Return the name ``token`` refers to, without a raw-function mark.

    The bare ``:`` is the conditional itself and is returned untouched.
    """
    return token.removeprefix(":") or token


def _parse_program(
    code: str, builtins: Collection[str]
) -> tuple[dict[str, _Def], list[tuple[str, ...]]]:
    """Split a program into its definitions and its top-level calls.

    A line whose first token is already defined (or a literal) is a call.
    """
    defs: dict[str, _Def] = {}
    calls: list[tuple[str, ...]] = []
    for raw_line in code.splitlines():
        tokens = tuple(_strip_comment(raw_line).split())
        if not tokens:
            continue
        head = tokens[0]
        if (
            head in builtins
            or head in defs
            or _is_literal(head)
            or head.startswith(":")
        ):
            calls.append(tokens)
            continue
        defs[head] = _parse_definition(head, tokens[1:], defs, builtins)
    return defs, calls


def _parse_definition(
    name: str,
    rest: tuple[str, ...],
    defs: Mapping[str, _Def],
    builtins: Collection[str],
) -> _Def:
    """Split a definition's tokens into its parameters and its code.

    Tokens before the first defined name are parameters; ``name`` and each
    gathered parameter count as defined.
    """
    params: list[str] = []
    known = set(defs) | {name}
    index = 0
    for index, token in enumerate(rest):  # noqa: B007 - the cursor is the result
        bare = _bare_name(token)
        if bare in builtins or bare in known or _is_literal(bare):
            break
        params.append(token)
        known.add(bare)
    else:
        index = len(rest)
    return _Def(name, tuple(params), tuple(rest[index:]))
