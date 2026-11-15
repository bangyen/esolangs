"""Parse Onecode expressions and resolve labels before execution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NamedTuple

from esolangs.runtime.memory import parse_integer
from esolangs.runtime.source_hints import syntax_error

_TOKEN = re.compile(
    r"""\s+|//[^\n]*|[a-zA-Z_][a-zA-Z_0-9]*|[0-9]+|"""
    r""""(?:\\[^\n]|[^"\\\n])*"|'(?:\\[^\n]|[^'\\\n])'|[;:~()*,+!/\-=&|^<>\[\]]"""
)
_NAME = re.compile(r"[a-zA-Z_][a-zA-Z_0-9]*")
_PRECEDENCE = {
    "~": 1,
    "|": 2,
    "^": 2,
    "&": 2,
    "=": 3,
    "<": 3,
    ">": 3,
    "+": 4,
    "-": 4,
    "*": 5,
    "/": 5,
}
_FUNCTIONS = frozenset(("getc", "getn", "putc", "putn"))
_RESERVED = _FUNCTIONS | {"if", "else", "goto"}
_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", "0": "\0", "\\": "\\", "'": "'", '"': '"'}

type _Value = int | tuple[int, ...]


class Op(NamedTuple):
    code: str
    arg: _Value | str = 0


@dataclass(frozen=True, slots=True)
class _Expr:
    op: Op
    children: tuple[_Expr, ...] = ()


def _invalid(message: str) -> ValueError:
    return syntax_error(
        f"Onecode {message}", "check expressions, semicolons and labels"
    )


def _tokens(source: str) -> list[str]:
    tokens: list[str] = []
    offset = 0
    while offset < len(source):
        match = _TOKEN.match(source, offset)
        if match is None:
            raise _invalid(f"cannot read character at offset {offset}")
        token = match.group()
        if not token[0].isspace() and not token.startswith("//"):
            tokens.append(token)
        offset = match.end()
    tokens.append("")
    return tokens


def _text(token: str) -> str:
    def escape(match: re.Match[str]) -> str:
        letter = match[1]
        if letter not in _ESCAPES:
            raise _invalid(f"unknown escape {letter!r}")
        return _ESCAPES[letter]

    return re.sub(r"\\(.)", escape, token[1:-1])


class _Parser:
    def __init__(self, source: str) -> None:
        self.tokens = _tokens(source)
        self.index = 0
        self.code: list[Op] = []
        self.labels: dict[str, int] = {}

    def peek(self) -> str:
        return self.tokens[self.index]

    def take(self) -> str:
        token = self.peek()
        if not token:
            raise _invalid("reached the end of an incomplete statement")
        self.index += 1
        return token

    def accept(self, token: str) -> bool:
        if self.peek() != token:
            return False
        self.index += 1
        return True

    def expect(self, token: str) -> None:
        if not self.accept(token):
            raise _invalid(f"expected {token!r}, got {self.peek()!r}")

    def name(self) -> str:
        token = self.take()
        if not _NAME.fullmatch(token) or token in _RESERVED:
            raise _invalid(f"expected a label name, got {token!r}")
        return token

    def primary(self) -> _Expr:
        token = self.take()
        if token in {"*", "!", "-"}:
            operation = {"*": "load_cell", "!": "not", "-": "neg"}[token]
            return _Expr(Op(operation), (self.primary(),))
        if token == "(":
            grouped = self.expression()
            self.expect(")")
            return grouped
        if token == "[":
            values: list[_Expr] = []
            if not self.accept("]"):
                values.append(self.expression())
                while self.accept(","):
                    values.append(self.expression())
                self.expect("]")
            return _Expr(Op("pack", len(values)), tuple(values))
        if token[0] == '"':
            return _Expr(Op("literal", (*map(ord, _text(token)), 0)))
        if token[0] == "'":
            return _Expr(Op("literal", ord(_text(token))))
        if token[0].isdigit():
            return _Expr(Op("literal", parse_integer(token)))
        if token in _FUNCTIONS:
            self.expect("(")
            args = (self.expression(),) if token in {"putc", "putn"} else ()
            self.expect(")")
            return _Expr(Op(token), args)
        if _NAME.fullmatch(token) and token not in _RESERVED:
            return _Expr(Op("load_var", token))
        raise _invalid(f"expected an expression, got {token!r}")

    def expression(self, minimum: int = 1) -> _Expr:
        left = self.primary()
        while (precedence := _PRECEDENCE.get(self.peek(), 0)) >= minimum:
            operator = self.take()
            right = self.expression(precedence if operator == "~" else precedence + 1)
            if operator != "~":
                left = _Expr(Op(operator), (left, right))
            elif left.op.code == "load_var":
                left = _Expr(Op("store_var", left.op.arg), (right,))
            elif left.op.code == "load_cell":
                left = _Expr(Op("store_cell"), (*left.children, right))
            else:
                raise _invalid("assignment needs a variable or memory address")
        return left

    def emit(self, expression: _Expr) -> None:
        pending: list[_Expr | Op] = [expression]
        while pending:
            node = pending.pop()
            if isinstance(node, Op):
                self.code.append(node)
            else:
                pending.append(node.op)
                pending.extend(reversed(node.children))

    def statement(self) -> bool:
        """Emit one statement and report whether it consumed its separator."""
        if self.accept("goto"):
            self.code.append(Op("jump", self.name()))
        elif self.accept("if"):
            self.expect("(")
            self.emit(self.expression())
            self.expect(")")
            self.expect("goto")
            self.code.append(Op("jump_if", self.name()))
            separated = self.accept(";")
            if not self.accept("else"):
                return separated
            self.expect("goto")
            self.code.append(Op("jump", self.name()))
        else:
            self.emit(self.expression())
            self.code.append(Op("discard"))
        return False

    def program(self) -> tuple[Op, ...]:
        while self.peek():
            if self.accept(";"):
                continue
            if self.tokens[self.index + 1] == ":":
                name = self.name()
                self.expect(":")
                if name in self.labels:
                    raise _invalid(f"duplicate label {name!r}")
                self.labels[name] = len(self.code)
                continue
            separated = self.statement()
            if not separated and self.peek():
                self.expect(";")
        result = []
        for op in self.code:
            if op.code in {"jump", "jump_if"}:
                assert isinstance(op.arg, str)
                if op.arg not in self.labels:
                    raise _invalid(f"unknown label {op.arg!r}")
                result.append(Op(op.code, self.labels[op.arg]))
            else:
                result.append(op)
        return tuple(result)


def parse(source: str) -> tuple[Op, ...]:
    """Compile source into immutable postfix operations."""
    try:
        return _Parser(source).program()
    except RecursionError as exc:
        raise _invalid("expression nesting is too deep") from exc
