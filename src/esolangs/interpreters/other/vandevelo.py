"""Pure-core interpreter for Vandevelo.

Vandevelo has only nil and not-nil values. Assignments may be lazy or strict,
comparisons test the two values, and ``::`` stops evaluating a statement when
its left operand is nil. ``Inp`` reads a line; empty input, ``0``, and one
space are nil, while every other line is not nil.

Input exhaustion raises :class:`EOFError`. Malformed programs raise
:class:`ValueError`; the language has no invalid runtime operation requiring
:class:`~esolangs.exceptions.HaltError`.

The execution model is a pure function over an immutable ``_State``. The
mutable VM shell performs input and replaces that state once per step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from esolangs.interpreters._entry import script_main
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
type _Store = tuple[tuple[str, _Value], ...]
type _Frame = tuple[_Expr, int, bool | None]


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


@dataclass(frozen=True)
class _State:
    """One immutable Vandevelo evaluator state."""

    ind: int
    part: int
    store: _Store
    stack: tuple[_Frame, ...] = ()
    pending: bool | None = None


def _statement(line: str) -> _Statement | None:
    """Parse a line after removing its comment."""
    line = line.split("--", 1)[0].strip()
    if not line:
        return None
    match = _ASSIGN.fullmatch(line)
    if match is not None:
        target, operator, value = match.groups()
        return _Statement(
            target=target,
            strict=operator.startswith("~"),
            negate="!" in operator,
            parts=(_expr(value),),
        )
    return _Statement(
        target=None,
        strict=False,
        negate=False,
        parts=tuple(_expr(part) for part in line.split("::")),
    )


def _stored(store: _Store, name: str) -> _Value | None:
    """Return ``name``'s value, or ``None`` when it is undefined."""
    return next((value for key, value in store if key == name), None)


def _bind(store: _Store, name: str, value: _Value) -> _Store:
    """Return ``store`` with an immutable binding for ``name``."""
    return (*((key, item) for key, item in store if key != name), (name, value))


def _finish_part(state: _State, statement: _Statement, *, value: bool) -> _State:
    """Return the state after completing one statement part."""
    if statement.target is not None:
        stored = value != statement.negate
        return _State(state.ind + 1, 0, _bind(state.store, statement.target, stored))
    if not value or state.part + 1 == len(statement.parts):
        return _State(state.ind + 1, 0, state.store)
    return _State(state.ind, state.part + 1, state.store)


def _advance(
    state: _State,
    statements: tuple[_Statement, ...],
    *,
    input_value: bool | None = None,
) -> _State:
    """Return the next evaluator state without mutating ``state``."""
    statement = statements[state.ind]
    stack = state.stack
    if not stack:
        if statement.target is not None and not statement.strict:
            lazy_value = statement.parts[0]
            if statement.negate:
                lazy_value = _Expr("not", left=lazy_value)
            return _State(
                state.ind + 1,
                0,
                _bind(state.store, statement.target, lazy_value),
            )
        stack = ((statement.parts[state.part], 0, None),)

    expression, stage, left = stack[-1]
    stack = stack[:-1]
    kind = expression.kind
    if kind == "var":
        name = expression.name
        if name == "Inp":
            if input_value is None:
                raise ValueError("input value required for 'Inp'")
            result = input_value
        else:
            stored = _stored(state.store, name)
            if stored is None:
                raise ValueError(f"undefined variable: {name}")
            if isinstance(stored, bool):
                result = stored
            else:
                return _State(
                    state.ind,
                    state.part,
                    state.store,
                    (*stack, (stored, 0, None)),
                    state.pending,
                )
    elif kind == "not":
        operand = expression.left
        if operand is None:
            raise ValueError("negation has no operand")
        if stage == 0:
            return _State(
                state.ind,
                state.part,
                state.store,
                (*stack, (expression, 1, None), (operand, 0, None)),
                state.pending,
            )
        result = not state.pending
    elif stage == 0:
        operand = expression.left
        if operand is None:
            raise ValueError("comparison has no left operand")
        return _State(
            state.ind,
            state.part,
            state.store,
            (*stack, (expression, 1, None), (operand, 0, None)),
            state.pending,
        )
    elif stage == 1:
        operand = expression.right
        if operand is None:
            raise ValueError("comparison has no right operand")
        return _State(
            state.ind,
            state.part,
            state.store,
            (*stack, (expression, 2, state.pending), (operand, 0, None)),
            state.pending,
        )
    else:
        result = left == state.pending
        if kind == "ne":
            result = not result

    advanced = _State(state.ind, state.part, state.store, stack, pending=result)
    if stack:
        return advanced
    return _finish_part(advanced, statement, value=result)


def _needs_input(state: _State, statements: tuple[_Statement, ...]) -> bool:
    """Whether the next pure transition needs one line of input."""
    if state.stack:
        expression = state.stack[-1][0]
    else:
        statement = statements[state.ind]
        if statement.target is not None and not statement.strict:
            return False
        expression = statement.parts[state.part]
    return expression.kind == "var" and expression.name == "Inp"


class _Machine:
    """Mutable VM shell around Vandevelo's pure evaluator."""

    def __init__(self, code: str, io: IO) -> None:
        self.statements = tuple(
            statement
            for line in code.splitlines()
            if (statement := _statement(line)) is not None
        )
        self.io = io
        self.state = _State(0, 0, (("Nil", False),))

    @property
    def halted(self) -> bool:
        return self.state.ind >= len(self.statements)

    @property
    def ip(self) -> int:
        return self.state.ind

    @property
    def memory(self) -> list[int]:
        return []

    @property
    def stack(self) -> list[object]:
        return list(self.state.stack)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete evaluator state."""
        return (self.state, self.io.position())

    def step(self) -> None:
        """Advance one expression-evaluation operation."""
        if self.halted:
            return
        input_value = None
        if _needs_input(self.state, self.statements):
            input_value = self.io.input_str() not in {"", "0", " "}
        self.state = _advance(self.state, self.statements, input_value=input_value)


def run(code: str, io: IO) -> None:
    """Run a Vandevelo program to the end of its source."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run)
