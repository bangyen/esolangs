"""Parse Nybbleist commands and bind labels within each bracket scope."""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import TYPE_CHECKING, NamedTuple

from esolangs.runtime.source_hints import syntax_error

if TYPE_CHECKING:
    from collections.abc import Mapping

VARIABLES = "XY"
DIGITS = "0123456789ABCDEF"
_TOKEN = re.compile(r"([*<>?!@:#%+\-^&\[\]|$~])([0-9A-FXY]*)")


class Instruction(NamedTuple):
    """One instruction and its lexical scope or bracket return address."""

    op: str
    args: str
    scope: int
    resume: int = 0


class Target(NamedTuple):
    """A local jump or a call to the start of a child scope."""

    destination: int
    call: bool = False


class Program(NamedTuple):
    """Immutable instructions and name bindings for each lexical scope."""

    code: tuple[Instruction, ...]
    labels: tuple[Mapping[str, Target], ...]


def _syntax(message: str) -> ValueError:
    return syntax_error(
        f"Nybbleist {message}", "use X or Y for a variable and 0-F for label digits"
    )


def _validate(op: str, args: str, *, nested: bool) -> None:
    if op in "<>?":
        valid = len(args) == 1 and args in VARIABLES
    elif op in "+-^&":
        valid = len(args) == 2 and args[0] in VARIABLES
    elif op == "~":
        valid = len(args) >= 2 and args[0] in VARIABLES
    elif op in "#%*!":
        valid = bool(args)
    elif op == ":":
        valid = bool(args) and all(digit in DIGITS for digit in args)
    elif op == "]":
        valid = nested and all(digit in DIGITS for digit in args)
    else:
        valid = not args and (op != "|" or nested)
    if not valid:
        raise _syntax(f"has invalid operands or scope for {op}{args}")


def _define(labels: dict[str, Target], name: str, target: Target) -> None:
    if name in labels:
        raise _syntax(f"defines label {name} twice in one scope")
    labels[name] = target


def parse(source: str) -> Program:
    """Expand grouped pushes and writes, and resolve bracket boundaries."""
    text = "".join(source.split())
    pos = scope = 0
    code: list[Instruction] = []
    labels: list[dict[str, Target]] = [{}]
    openings: list[tuple[int, int]] = []
    while pos < len(text):
        token = _TOKEN.match(text, pos)
        if token is None:
            raise _syntax(f"has an invalid token at {text[pos]!r}")
        op, args = token.group(1, 2)
        _validate(op, args, nested=bool(openings))
        pos = token.end()
        match op:
            case ":":
                _define(labels[scope], args, Target(len(code)))
            case "[":
                openings.append((scope, len(code)))
                code.append(Instruction(op, "", scope))
                scope = len(labels)
                labels.append({})
            case "]":
                code.append(Instruction(op, "", scope))
                scope, opener = openings.pop()
                code[opener] = Instruction("[", "", scope, len(code))
                if args:
                    _define(labels[scope], args, Target(opener + 1, call=True))
            case "*" | "!":
                code.extend(Instruction(op, value, scope) for value in args)
            case _:
                code.append(Instruction(op, args, scope))
    if openings:
        raise _syntax("has an unclosed '['")
    return Program(tuple(code), tuple(MappingProxyType(items) for items in labels))
