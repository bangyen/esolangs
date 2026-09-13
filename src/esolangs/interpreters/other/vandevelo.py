"""Interpreter for Vandevelo.

Vandevelo has only nil and not-nil values. Assignments may be lazy or strict,
comparisons test the two values, and ``::`` stops evaluating a statement when
its left operand is nil. ``Inp`` reads a line; empty input, ``0``, and one
space are nil, while every other line is not nil.

Input exhaustion raises :class:`EOFError`. Malformed programs raise
:class:`ValueError`; the language has no invalid runtime operation requiring
:class:`~esolangs.exceptions.HaltError`.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass

from esolangs.interpreters.io import IO

_NAME = re.compile(r"[A-Za-z0-9_&*$]+")
_ASSIGN = re.compile(r"([A-Za-z0-9_&*$]+)\s*(~!>|~>|-!>|->)\s*(.+)")

@dataclass(frozen=True)
class _Expr:
    """One expression node."""

    kind: str
    name: str = ""
    left: _Expr | None = None
    right: _Expr | None = None


type _Value = bool | _Expr
type _State = tuple[object, ...]


def _expr(source: str) -> _Expr:
    """Parse one comparison expression or variable access."""
    source = source.strip()
    for operator, kind in (("==", "eq"), ("!=", "ne")):
        if operator in source:
            left, right = source.split(operator, 1)
            return _Expr(kind, left=_expr(left), right=_expr(right))
    if not source.endswith("?") or not _NAME.fullmatch(source[:-1]):
        raise ValueError(f"invalid expression: {source}")
    return _Expr("var", name=source[:-1])


@dataclass(frozen=True)
class _Statement:
    """One parsed source line."""

    target: str | None
    strict: bool
    negate: bool
    parts: tuple[_Expr, ...]


def _statement(line: str) -> _Statement | None:
    """Parse a line after removing its comment."""
    line = line.split("--", 1)[0].strip()
    if not line:
        return None
    match = _ASSIGN.fullmatch(line)
    if match is not None:
        target, operator, value = match.groups()
        return _Statement(target, operator.startswith("~"), "!" in operator, (_expr(value),))
    return _Statement(None, False, False, tuple(_expr(part) for part in line.split("::")))


class _Machine:
    """A Vandevelo evaluator with an explicit, cycle-visible expression stack."""

    def __init__(self, code: str, io: IO) -> None:
        self.statements = tuple(
            statement
            for line in code.splitlines()
            if (statement := _statement(line)) is not None
        )
        self.io = io
        self.ind = 0
        self.part = 0
        self.store: dict[str, _Value] = {"Nil": False}
        self.stack: list[tuple[_Expr, int, bool | None]] = []
        self.pending: bool | None = None

    @property
    def halted(self) -> bool:
        return self.ind >= len(self.statements)

    @property
    def ip(self) -> int:
        return self.ind

    @property
    def memory(self) -> list[int]:
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete evaluator state."""
        return (
            self.ind,
            self.part,
            tuple(sorted(self.store.items())),
            tuple(self.stack),
            self.pending,
            self.io.position(),
        )

    def _finish_part(self, value: bool) -> None:
        statement = self.statements[self.ind]
        if statement.target is not None:
            self.store[statement.target] = value != statement.negate
            self.ind += 1
            self.part = 0
        elif not value or self.part + 1 == len(statement.parts):
            self.ind += 1
            self.part = 0
        else:
            self.part += 1

    def step(self) -> None:
        """Advance one expression-evaluation operation."""
        if self.halted:
            return
        statement = self.statements[self.ind]
        if not self.stack:
            if statement.target is not None and not statement.strict:
                lazy_value = statement.parts[0]
                if statement.negate:
                    lazy_value = _Expr("not", left=lazy_value)
                self.store[statement.target] = lazy_value
                self.ind += 1
                return
            self.stack.append((statement.parts[self.part], 0, None))

        expression, stage, left = self.stack.pop()
        kind = expression.kind
        if kind == "var":
            name = expression.name
            if name == "Inp":
                result = self.io.input_str() not in {"", "0", " "}
            elif name not in self.store:
                raise ValueError(f"undefined variable: {name}")
            else:
                stored = self.store[name]
                if isinstance(stored, bool):
                    result = stored
                else:
                    self.stack.append((stored, 0, None))
                    return
        elif kind == "not":
            operand = expression.left
            if operand is None:
                raise ValueError("negation has no operand")
            if stage == 0:
                self.stack.append((expression, 1, None))
                self.stack.append((operand, 0, None))
                return
            result = not self.pending
        elif stage == 0:
            operand = expression.left
            if operand is None:
                raise ValueError("comparison has no left operand")
            self.stack.append((expression, 1, None))
            self.stack.append((operand, 0, None))
            return
        elif stage == 1:
            operand = expression.right
            if operand is None:
                raise ValueError("comparison has no right operand")
            self.stack.append((expression, 2, self.pending))
            self.stack.append((operand, 0, None))
            return
        else:
            result = left == self.pending
            if kind == "ne":
                result = not result

        self.pending = result
        if not self.stack:
            self._finish_part(result)


def run(code: str, io: IO) -> None:
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
