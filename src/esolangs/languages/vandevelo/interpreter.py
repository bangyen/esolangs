"""Pure-core interpreter for Vandevelo.

Vandevelo has only nil and not-nil values. Assignments may be lazy or strict,
comparisons test the two values, and ``::`` stops evaluating a statement when
its left operand is nil.

The execution model is a pure function over an immutable state. The
mutable VM shell performs input and replaces that state once per step.  The
language has no invalid runtime operation requiring HaltError.

Input/output:
    ``Inp`` reads a line; empty input, ``0``, and one space are nil, while
    every other line is not nil.  ``Inp`` at EOF raises.

Errors:
    ProgramError: a malformed program, including an invalid expression, a
        read of an undefined variable, and the Comments example's ``?`` target.
    InputExhaustedError: ``Inp`` at EOF.

Decisions:
    * The spec does not delimit input values; ``Inp`` reads one line,
      excluding its newline.
    * ``x :: y`` takes expressions only, and ``a :: b :: c`` stops at the
      first nil.
    * The Comments example ``2? -> 2? --Infinite loop`` writes its target
      with a ``?``, which the table and the truth-machine never do; it is
      malformed here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

_NAME = re.compile(r"[A-Za-z0-9_&*$]+")
_ASSIGN = re.compile(rf"({_NAME.pattern})\s*(~!>|~>|-!>|->)\s*(.+)")


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
        raise syntax_error(
            f"invalid expression: {source}",
            (
                "write a variable access as name?, optionally comparing two "
                "accesses with == or !="
            ),
        )
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

    def seeded(self, expression: _Expr) -> _State:
        """Return this state with ``expression`` as its only frame."""
        return replace(self, stack=((expression, 0, None),))

    def bound_next(self, name: str, value: _Value) -> _State:
        """Return the next statement's state, with ``name`` bound to ``value``."""
        return replace(
            self,
            ind=self.ind + 1,
            part=0,
            store=_bind(self.store, name, value),
            stack=(),
            pending=None,
        )

    def next_statement(self) -> _State:
        """Return the state at the next statement, frames and result spent."""
        return replace(self, ind=self.ind + 1, part=0, stack=(), pending=None)

    def next_part(self) -> _State:
        """Return the state at this statement's next ``::`` part."""
        return replace(self, part=self.part + 1, stack=(), pending=None)

    def descend(
        self,
        rest: tuple[_Frame, ...],
        expression: _Expr,
        stage: int,
        operand: _Expr,
        *,
        left: bool | None = None,
    ) -> _State:
        """Return the state re-parking ``expression`` at ``stage`` under ``operand``."""
        return replace(
            self, stack=(*rest, (expression, stage, left), (operand, 0, None))
        )

    def expand(self, rest: tuple[_Frame, ...], stored: _Expr) -> _State:
        """Return the state with a stored expression's frame over ``rest``."""
        return replace(self, stack=(*rest, (stored, 0, None)))

    def completed(self, rest: tuple[_Frame, ...], *, result: bool) -> _State:
        """Return the state with ``result`` pending over the frames ``rest``."""
        return replace(self, stack=rest, pending=result)


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
        return state.bound_next(statement.target, value != statement.negate)
    if not value or state.part + 1 == len(statement.parts):
        return state.next_statement()
    return state.next_part()


def _start(state: _State, statement: _Statement) -> _State | None:
    """Return the lazy-bind state, or ``None`` when evaluation must run."""
    if statement.target is None or statement.strict:
        return None
    lazy_value = statement.parts[0]
    if statement.negate:
        lazy_value = _Expr("not", left=lazy_value)
    return state.bound_next(statement.target, lazy_value)


def _eval_var(
    state: _State,
    rest: tuple[_Frame, ...],
    expression: _Expr,
    *,
    input_value: bool | None,
) -> _State | bool:
    """Evaluate a variable access: its value, or the state expanding its store."""
    name = expression.name
    if name == "Inp":
        if input_value is None:
            raise syntax_error(
                "input value required for 'Inp'", "supply an input value for Inp"
            )
        return input_value
    stored = _stored(state.store, name)
    if stored is None:
        raise syntax_error(
            f"undefined variable: {name}",
            "assign the variable before reading it with name?",
        )
    if isinstance(stored, bool):
        return stored
    return state.expand(rest, stored)


def _eval_not(
    state: _State,
    rest: tuple[_Frame, ...],
    expression: _Expr,
    stage: int,
) -> _State | bool:
    """Evaluate a negation: descend into its operand, then flip its result."""
    operand = expression.left
    if operand is None:
        raise syntax_error(
            "negation has no operand", "put an expression after the negation"
        )
    if stage == 0:
        return state.descend(rest, expression, 1, operand)
    return not state.pending


def _eval_compare(
    state: _State,
    rest: tuple[_Frame, ...],
    expression: _Expr,
    stage: int,
    *,
    left: bool | None,
) -> _State | bool:
    """Evaluate a comparison stage by stage: left operand, right, then test."""
    if stage == 0:
        operand = expression.left
        if operand is None:
            raise syntax_error(
                "comparison has no left operand",
                "put a variable access before == or !=",
            )
        return state.descend(rest, expression, 1, operand)
    if stage == 1:
        operand = expression.right
        if operand is None:
            raise syntax_error(
                "comparison has no right operand",
                "put a variable access after == or !=",
            )
        return state.descend(rest, expression, 2, operand, left=state.pending)
    result = left == state.pending
    if expression.kind == "ne":
        result = not result
    return result


def _advance(
    state: _State,
    statements: tuple[_Statement, ...],
    *,
    input_value: bool | None = None,
) -> _State:
    """Return the next evaluator state without mutating ``state``."""
    statement = statements[state.ind]
    if not state.stack:
        lazy = _start(state, statement)
        if lazy is not None:
            return lazy
        state = state.seeded(statement.parts[state.part])

    expression, stage, left = state.stack[-1]
    rest = state.stack[:-1]
    if expression.kind == "var":
        outcome = _eval_var(state, rest, expression, input_value=input_value)
    elif expression.kind == "not":
        outcome = _eval_not(state, rest, expression, stage)
    else:
        outcome = _eval_compare(state, rest, expression, stage, left=left)
    if isinstance(outcome, _State):
        return outcome
    advanced = state.completed(rest, result=outcome)
    if rest:
        return advanced
    return _finish_part(advanced, statement, value=outcome)


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
        self._input_reads = 0

    @property
    def halted(self) -> bool:
        return self.state.ind >= len(self.statements)

    @property
    def ip(self) -> int:
        return self.state.ind

    @property
    def stack(self) -> list[object]:
        return list(self.state.stack)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete evaluator state."""
        return (self.state, self.io.progress(), self._input_reads, self.statements)

    def step(self) -> None:
        """Advance one expression-evaluation operation."""
        if self.halted:
            return
        input_value = None
        if _needs_input(self.state, self.statements):
            input_value = self.io.input_str() not in {"", "0", " "}
            self._input_reads += 1
        self.state = _advance(self.state, self.statements, input_value=input_value)


def run(code: str, io: IO) -> None:
    """Run a Vandevelo program to the end of its source."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
