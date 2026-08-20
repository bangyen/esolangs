"""Interpreter for Suptiftam.

A statement-per-line language of functions (one argument, no return value,
recursion for loops) and two-dimensional tape-tapes.  ``read`` and ``term``
are built-in tapes standing for input and output: ``read`` is loaded from
stdin before execution (each input line becomes a row of byte cells, past
the end all cells are zero), and ``term`` is rendered after the program
halts.  The four builtin functions (``down``/``left``/``right``/``up``)
move a tape's head; ``include`` reads a file, which this interpreter does
not support.

Decisions for gaps in the wiki spec (documented):
- ``read`` is populated lazily, one input line per row on first access, so
  a program that never reads input does not consume stdin; reading past the
  end of the input yields a zero cell (the wiki's EOF convention) and
  running out of input lines never raises :class:`EOFError`;
- output is the bounding box of the cells written to ``term`` (rows joined
  with newlines): byte cells render as their character, integer cells as
  their decimal string, unwritten cells inside the box as NUL bytes;
- ``term`` and ``read`` are untyped tapes (the wiki's own examples store
  both bytes and integers in ``term``), so they never trigger the type
  mismatch; user tapes declared with ``[integer]``/``[byte]`` are typed and
  a mismatched assignment leaves the cell unchanged and deterministically
  prints the digit ``'0'`` (the wiki's "random digit") to ``term``;
- assigning to an undeclared name declares it with the value's type (the
  wiki's ``x=A``/``A=7`` example relies on ``A=7`` declaring ``A``);
- math operands may be identifiers, integer literals, or byte literals and
  math never nests; ``/`` truncates toward zero, results are integers unless
  both operands are bytes (then the result is a byte, so the wiki's
  ``'a' - 'A'`` space renders as a character), and bytes wrap only when
  stored into a byte cell;
- the wiki's examples are untested: its truth-machine's ``%-[read]48%``
  subtracts 100 (the literal ``48`` is base-23-parsed to 100), so the
  committed example and the boolean generator use ``%-[read]22%`` (the
  literal ``22`` parses to 48) instead;
- undefined behavior is pinned: passing a non-tape to a move builtin,
  calling an undefined function, an undeclared identifier, exceeding the
  recursion limit (250), and division by zero all raise
  :class:`~esolangs.exceptions.HaltError`; ``include`` raises
  :class:`~esolangs.exceptions.HaltError` because file-based I/O is not
  supported;
- malformed programs (unbalanced call tokens, a stray ``fi``, a header
  missing its colon) raise :class:`ValueError`.

``_Machine`` runs on the parsed top-level statement list and an explicit
cursor, so it is step-capable: ``step()`` executes one top-level
statement and ``halted`` is true once the cursor reaches the end.  A
statement's own function call still runs to completion inside that one
``step()`` through the original recursive ``_call``/``_run_statement``,
since Suptiftam has no looping construct other than function recursion
(already capped at ``_MAX_DEPTH``, so it halts rather than hangs).
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Any

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_MAX_DEPTH = 250

_OPERATORS = "+-/"
_LITERAL_DIGITS = {ch: i for i, ch in enumerate("0123456789ABCD")}

# Tokens and statements are heterogeneous tuples: a byte token is
# ``("byte", int)``, a math token ``("math", op, x, y)``, a call statement
# ``("call", name, arg, condition)``.  A ``tuple[Any, ...]`` keeps the
# narrow shapes usable without a large tagged union.
_Node = tuple[Any, ...]


class _Tape:
    """A 2D tape: unbounded cells, a movable head, and an optional cell type.

    ``fixed`` is ``None`` (untyped, e.g. the built-in ``term``/``read``),
    ``"int"`` (cells hold integers), or ``"byte"`` (cells hold unsigned
    wrapping bytes).  ``reader`` lazily supplies cell values for ``read``
    instead of a pre-populated ``cells`` dict.
    """

    __slots__ = ("cells", "fixed", "reader", "x", "y")

    def __init__(
        self,
        fixed: str | None = None,
        reader: Any = None,
    ) -> None:
        self.cells: dict[tuple[int, int], tuple[str, int]] = {}
        self.fixed = fixed
        self.reader = reader
        self.x = 0
        self.y = 0

    def get_cell(self) -> tuple[str, int]:
        """Return the ``(kind, value)`` under the head (zeros beyond input)."""
        if self.reader is not None:
            value = self.reader(self.x, self.y)
            return ("byte", 0) if value is None else ("byte", value)
        return self.cells.get((self.x, self.y), ("byte", 0))

    def set_cell(self, kind: str, value: int) -> None:
        """Write a ``(kind, value)`` to the cell under the head."""
        self.cells[(self.x, self.y)] = (kind, value)


class _Var:
    """A scalar variable: either an unbounded integer or a wrapping byte."""

    __slots__ = ("kind", "value")

    def __init__(self, kind: str, value: int) -> None:
        self.kind = kind
        self.value = value


class _State:
    """The whole-program state: scopes, tapes, functions, and lazy input."""

    def __init__(self, io: IO) -> None:
        self.io = io
        self.globals: dict[str, object] = {}
        self.functions: dict[str, list[tuple[str, list[_Node]]]] = {}
        self._rows: list[list[int] | None] = []
        self.depth = 0
        self.read = _Tape(reader=self._read_cell)
        self.term = _Tape()
        self.globals["read"] = self.read
        self.globals["term"] = self.term

    def _read_cell(self, x: int, y: int) -> int | None:
        """Return the ``read`` tape's byte at ``(x, y)``, loading rows lazily."""
        while len(self._rows) <= y:
            try:
                line = self.io.input_str()
            except EOFError:
                self._rows.append(None)
            else:
                self._rows.append([ord(c) for c in line])
        row = self._rows[y]
        if row is None or x < 0 or x >= len(row):
            return None
        return row[x]


# -- parsing ---------------------------------------------------------------


def _tokenize(line: str) -> list[_Node]:
    """Split one statement line into tokens."""
    tokens: list[_Node] = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c == " ":
            i += 1
        elif c in "():~=":
            tokens.append((c,))
            i += 1
        elif c == "'":
            if i + 2 >= n or line[i + 2] != "'":
                raise ValueError(f"malformed byte literal at position {i}")
            tokens.append(("byte", ord(line[i + 1])))
            i += 3
        elif c == "%":
            token, i = _scan_math(line, i)
            tokens.append(token)
        elif c == "[":
            token, i = _scan_tape_decl(line, i, tokens)
            tokens[-1] = token  # replace the trailing identifier with the decl
        elif c.isalpha():
            j = i
            while j < n and line[j].isalpha():
                j += 1
            name = line[i:j]
            k = j
            while k < n and line[k] == " ":
                k += 1
            if name == "if" and k < n and line[k] == "(":
                token, i = _scan_if(line, j)
                tokens.append(token)
            else:
                tokens.append(("ident", name))
                i = j
        elif c.isdigit():
            j = i
            while j < n and line[j] in _LITERAL_DIGITS:
                j += 1
            tokens.append(("num", _base23(line[i:j])))
            i = j
        else:
            raise ValueError(f"unexpected character {c!r} at position {i}")
    return tokens


def _skip_spaces(line: str, i: int) -> int:
    n = len(line)
    while i < n and line[i] == " ":
        i += 1
    return i


def _base23(text: str) -> int:
    value = 0
    for ch in text:
        value = value * 23 + _LITERAL_DIGITS[ch]
    return value


def _scan_value(line: str, i: int) -> tuple[_Node, int]:
    """Parse one value expression (ident, literal, byte, or math) at ``i``."""
    i = _skip_spaces(line, i)
    if i >= len(line):
        raise ValueError("expected a value")
    c = line[i]
    if c == "'":
        if i + 2 >= len(line) or line[i + 2] != "'":
            raise ValueError("malformed byte literal")
        return ("byte", ord(line[i + 1])), i + 3
    if c == "%":
        return _scan_math(line, i)
    if c.isalpha():
        j = i
        while j < len(line) and line[j].isalpha():
            j += 1
        return ("ident", line[i:j]), j
    if c.isdigit():
        j = i
        while j < len(line) and line[j] in _LITERAL_DIGITS:
            j += 1
        return ("num", _base23(line[i:j])), j
    raise ValueError(f"expected a value at position {i}")


def _scan_math(line: str, i: int) -> tuple[_Node, int]:
    """Parse ``%op[x]y%`` starting at the opening ``%``."""
    if i + 1 >= len(line) or line[i + 1] not in _OPERATORS:
        raise ValueError(f"malformed math at position {i}")
    op = line[i + 1]
    j = i + 2
    if j >= len(line) or line[j] != "[":
        raise ValueError(f"malformed math at position {i}")
    x, j = _scan_value(line, j + 1)
    if x[0] == "math":
        raise ValueError(f"math cannot be nested at position {i}")
    j = _skip_spaces(line, j)
    if j >= len(line) or line[j] != "]":
        raise ValueError(f"malformed math at position {i}")
    y, j = _scan_value(line, j + 1)
    if y[0] == "math":
        raise ValueError(f"math cannot be nested at position {i}")
    j = _skip_spaces(line, j)
    if j >= len(line) or line[j] != "%":
        raise ValueError(f"malformed math at position {i}")
    return ("math", op, x, y), j + 1


def _scan_if(line: str, i: int) -> tuple[_Node, int]:
    """Parse ``if(<value>)`` after the ident ``if`` at position ``i``."""
    j = _skip_spaces(line, i)
    if j >= len(line) or line[j] != "(":  # pragma: no cover - only called with '('
        raise ValueError(f"malformed if at position {i}")
    j += 1
    j = _skip_spaces(line, j)
    wrapped = j < len(line) and line[j] == ":"
    if wrapped:
        j = _skip_spaces(line, j + 1)
    value, j = _scan_value(line, j)
    j = _skip_spaces(line, j)
    if wrapped:
        if j >= len(line) or line[j] != ":":
            raise ValueError(f"malformed if at position {i}")
        j = _skip_spaces(line, j + 1)
    if j >= len(line) or line[j] != ")":
        raise ValueError(f"malformed if at position {i}")
    return ("if", value), j + 1


def _scan_tape_decl(
    line: str,
    i: int,
    tokens: list[_Node],
) -> tuple[_Node, int]:
    """Parse ``name[TYPE]`` where TYPE is ``integer`` (a byte tape) or ``byte``."""
    if not tokens or tokens[-1][0] != "ident":
        raise ValueError(f"malformed tape declaration at position {i}")
    name = tokens[-1][1]
    j = _skip_spaces(line, i + 1)
    if j >= len(line) or not line[j].isalpha():
        raise ValueError(f"malformed tape declaration at position {i}")
    k = j
    while k < len(line) and line[k].isalpha():
        k += 1
    declared = line[j:k]
    j = _skip_spaces(line, k)
    if j >= len(line) or line[j] != "]":
        raise ValueError(f"malformed tape declaration at position {i}")
    if declared == "integer":
        kind = "byte"
    elif declared == "byte":
        kind = "int"
    else:
        raise ValueError(f"unknown tape type {declared!r}")
    return ("tape", name, kind), j + 1


def _parse_header(tokens: list[_Node]) -> tuple[str, str]:
    """Parse an ``fd`` header into ``(name, argument)``.

    The argument is written adjacent to the colon (``arg:`` or ``:arg``)
    with the other two tokens in any order, so the argument is the ident
    next to the colon on the side away from the ``fd`` keyword.
    """
    colon_idx = next((i for i, t in enumerate(tokens) if t[0] == ":"), -1)
    if colon_idx < 0:
        raise ValueError("fd header needs a colon")
    before = tokens[colon_idx - 1] if colon_idx > 0 else None
    after = tokens[colon_idx + 1] if colon_idx + 1 < len(tokens) else None
    arg: _Node | None
    if after is not None and after[0] == "ident" and after[1] != "fd":
        arg = after
    else:
        arg = before
    if arg is None or arg[0] != "ident" or arg[1] == "fd":
        raise ValueError("the fd argument must be an identifier")
    others = [t[1] for t in tokens if t[0] == "ident" and t[1] != "fd" and t != arg]
    if len(others) != 1:
        raise ValueError("fd header needs a function name")
    return others[0], arg[1]


def _parse_call(tokens: list[_Node]) -> _Node:
    """Parse a function-call statement (the four tokens may be in any order)."""
    colons = [i for i, t in enumerate(tokens) if t[0] == ":"]
    if len(colons) != 2 or colons[1] != colons[0] + 2:
        raise ValueError("a call needs its argument between two colons")
    arg = tokens[colons[0] + 1]
    if arg[0] not in ("ident", "num", "byte", "math"):
        raise ValueError("a call's argument must be a value")
    rest = tokens[: colons[0]] + tokens[colons[1] + 1 :]
    name: str | None = None
    condition: _Node | None = None
    parens = 0
    for t in rest:
        if t[0] == "ident":
            if name is not None:
                raise ValueError("a call has exactly one function name")
            name = t[1]
        elif t[0] in ("(", ")"):
            parens += 1
        elif t[0] == "if":
            if condition is not None:
                raise ValueError("a call has at most one if")
            condition = t[1]
        else:
            raise ValueError(f"unexpected token {t!r} in a call")
    if name is None or parens != 2:
        raise ValueError("a call needs a function name and parentheses")
    return ("call", name, arg, condition)


def _parse_decl(tokens: list[_Node], kind: str) -> _Node:
    """Parse ``name~value`` or ``name=value`` into an assignment statement."""
    if len(tokens) != 3 or tokens[0][0] != "ident" or tokens[1][0] != kind:
        raise ValueError(f"malformed {kind} statement")
    if tokens[2][0] not in ("ident", "num", "byte", "math"):
        raise ValueError(f"malformed {kind} statement")
    return ("assign", tokens[0][1], tokens[2])


def _parse_tape_decl(tokens: list[_Node]) -> _Node:
    """Parse a lone ``name[TYPE]`` line into a tape declaration."""
    tapes = [t for t in tokens if t[0] == "tape"]
    if len(tokens) != 1 or not tapes:
        raise ValueError("malformed tape declaration")
    tape = tapes[0]
    return ("tapedecl", tape[1], tape[2])


def _parse(
    lines: Sequence[str],
) -> tuple[dict[str, list[tuple[str, list[_Node]]]], list[_Node]]:
    """Parse a whole program into hoisted functions and top-level statements."""
    functions: dict[str, list[tuple[str, list[_Node]]]] = {}
    top: list[_Node] = []
    stack: list[tuple[str, str, list[_Node]]] = []
    for raw in lines:
        line = raw.strip()
        if "\t" in line or not line:
            continue
        tokens = _tokenize(line)
        is_fi = len(tokens) == 1 and tokens[0] == ("ident", "fi")
        has_fd = any(t == ("ident", "fd") for t in tokens)
        has_lparen = any(t[0] == "(" for t in tokens)
        if is_fi:
            if not stack:
                raise ValueError("fi without a matching fd")
            name, arg, body = stack.pop()
            functions.setdefault(name, []).append((arg, body))
        elif has_fd and not has_lparen:
            name, arg = _parse_header(tokens)
            stack.append((name, arg, []))
        elif has_lparen:
            statement = _parse_call(tokens)
            (stack[-1][2] if stack else top).append(statement)
        elif any(t[0] == "~" for t in tokens):
            statement = _parse_decl(tokens, "~")
            (stack[-1][2] if stack else top).append(statement)
        elif any(t[0] == "=" for t in tokens):
            statement = _parse_decl(tokens, "=")
            (stack[-1][2] if stack else top).append(statement)
        elif any(t[0] == "tape" for t in tokens):
            statement = _parse_tape_decl(tokens)
            (stack[-1][2] if stack else top).append(statement)
        else:
            raise ValueError(f"malformed statement: {line!r}")
    if stack:
        raise ValueError(f"function {stack[-1][0]!r} is missing its fi")
    return functions, top


# -- runtime ---------------------------------------------------------------


def _lookup(
    name: str,
    state: _State,
    frame: dict[str, object] | None,
) -> _Var | _Tape | None:
    """Resolve a name from the global scope outward (the most global wins)."""
    if name in state.globals:
        obj = state.globals[name]
        return obj if isinstance(obj, (_Var, _Tape)) else None
    if frame is not None and name in frame:
        obj = frame[name]
        return obj if isinstance(obj, (_Var, _Tape)) else None
    return None


def _put(
    name: str, value: object, state: _State, frame: dict[str, object] | None
) -> None:
    """Assign ``value`` to the existing scope, or declare it in the innermost."""
    if name in state.globals or frame is None:
        state.globals[name] = value
    else:
        frame[name] = value


def _eval_value(
    token: _Node,
    state: _State,
    frame: dict[str, object] | None,
) -> _Var | _Tape:
    """Evaluate a value expression to a ``_Var`` or ``_Tape``."""
    kind = token[0]
    if kind == "num":
        return _Var("int", token[1])
    if kind == "byte":
        return _Var("byte", token[1])
    if kind == "math":
        _, op, x, y = token
        left_kind, left = _operand(x, state, frame)
        right_kind, right = _operand(y, state, frame)
        if op == "+":
            result = left + right
        elif op == "-":
            result = left - right
        else:
            if right == 0:
                raise HaltError("division by zero")
            sign = -1 if (left < 0) != (right < 0) else 1
            result = sign * (abs(left) // abs(right))
        # math on two bytes stays a byte (e.g. the wiki's ``'a' - 'A'`` space),
        # so byte results render as characters; any integer operand widens.
        if left_kind == "byte" and right_kind == "byte":
            return _Var("byte", result & 0xFF)
        return _Var("int", result)
    name = token[1]
    obj = _lookup(name, state, frame)
    if obj is not None:
        return obj
    if all(c in _LITERAL_DIGITS for c in name):
        return _Var("int", _base23(name))
    raise HaltError(f"undeclared identifier {name!r}")


def _operand(
    token: _Node,
    state: _State,
    frame: dict[str, object] | None,
) -> tuple[str, int]:
    """Evaluate a math operand to a ``(kind, value)`` (tapes use their cell)."""
    value = _eval_value(token, state, frame)
    if isinstance(value, _Tape):
        return value.get_cell()
    return value.kind, value.value


def _truth(value: _Var | _Tape) -> bool:
    """Return whether a value is nonzero (tapes test the value under the head)."""
    if isinstance(value, _Tape):
        _, cell = value.get_cell()
        return cell != 0
    return value.value != 0


def _print_digit(state: _State) -> None:
    """Print the wiki's "random digit" on a type mismatch, deterministically ``'0'``."""
    state.term.set_cell("byte", ord("0"))


def _assign(
    name: str, value: _Var | _Tape, state: _State, frame: dict[str, object] | None
) -> None:
    """Assign ``value`` to ``name`` (a tape cell, a variable, or a new one)."""
    if isinstance(value, _Tape):
        kind, cell = value.get_cell()
    else:
        kind, cell = value.kind, value.value
    wrapped = cell & 0xFF if kind == "byte" else cell
    obj = _lookup(name, state, frame)
    if isinstance(obj, _Tape):
        if obj.fixed is not None and obj.fixed != kind:
            _print_digit(state)
        else:
            obj.set_cell(kind, wrapped)
    elif isinstance(obj, _Var):
        if obj.kind != kind:
            _print_digit(state)
        else:
            obj.value = wrapped
    else:
        _put(name, _Var(kind, wrapped), state, frame)


def _call(
    name: str,
    argument: _Node,
    state: _State,
    frame: dict[str, object] | None,
) -> None:
    """Run a call statement: a builtin, ``include``, or a user function."""
    if name in ("down", "left", "right", "up"):
        value = _eval_value(argument, state, frame)
        if not isinstance(value, _Tape):
            raise HaltError(f"{name} needs a tape argument")
        if name == "down":
            value.y += 1
        elif name == "left":
            value.x -= 1
        elif name == "right":
            value.x += 1
        else:
            value.y -= 1
        return
    if name == "include":
        raise HaltError("include is not supported (file-based I/O)")
    blocks = state.functions.get(name)
    if not blocks:
        raise HaltError(f"call to undefined function {name!r}")
    if state.depth >= _MAX_DEPTH:
        raise HaltError("recursion limit exceeded")
    value = _eval_value(argument, state, frame)
    state.depth += 1
    try:
        for param, body in blocks:
            local: dict[str, object] = {param: value}
            for statement in body:
                _run_statement(statement, state, local)
    finally:
        state.depth -= 1


def _run_statement(
    statement: _Node,
    state: _State,
    frame: dict[str, object] | None,
) -> None:
    """Execute one parsed statement."""
    kind = statement[0]
    if kind == "call":
        _, name, argument, condition = statement
        if condition is not None and not _truth(_eval_value(condition, state, frame)):
            return
        _call(name, argument, state, frame)
    elif kind == "assign":
        _, name, value = statement
        _assign(name, _eval_value(value, state, frame), state, frame)
    elif kind == "tapedecl":
        _, name, tape_kind = statement
        if _lookup(name, state, frame) is None:
            _put(name, _Tape(tape_kind), state, frame)
    else:
        raise AssertionError(f"unexpected statement {statement!r}")


def _render_term(term: _Tape) -> str:
    """Render the written region of ``term`` as rows of characters."""
    if not term.cells:
        return ""
    xs = [x for x, _ in term.cells]
    ys = [y for _, y in term.cells]
    rows = []
    for y in range(min(ys), max(ys) + 1):
        row = []
        for x in range(min(xs), max(xs) + 1):
            kind, value = term.cells.get((x, y), ("byte", 0))
            row.append(chr(value) if kind == "byte" else str(value))
        rows.append("".join(row))
    return "\n".join(rows)


class _Machine:
    """One Suptiftam run: the parsed program, state, and top-level cursor."""

    def __init__(self, code: str, io: IO) -> None:
        functions, top = _parse(code.splitlines())
        self.state = _State(io)
        self.state.functions = functions
        self.top = top
        self.ind = 0
        self._rendered = False

    @property
    def halted(self) -> bool:
        """Whether the cursor has run off the top-level statements."""
        return self.ind >= len(self.top)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        Globals are captured via ``repr()`` since a tape's cells are an
        unbounded, mutable dict -- sufficient for the state-cycle
        detector's purpose, since a genuine hang re-executes the same
        top-level statement with the same bindings on every lap.
        """
        return (
            self.ind,
            tuple(sorted((k, repr(v)) for k, v in self.state.globals.items())),
            self.state.io.position(),
        )

    def step(self) -> None:
        """Execute one top-level statement, advancing the cursor.

        Rendering ``term`` happens once, on the step that finishes the
        program, matching ``run()``'s original print-after-the-loop.
        """
        if self.halted:
            return
        _run_statement(self.top[self.ind], self.state, None)
        self.ind += 1
        if self.ind >= len(self.top) and not self._rendered:
            self._rendered = True
            rendered = _render_term(self.state.term)
            if rendered:
                self.state.io.print_str(rendered)


def run(code: str, io: IO) -> None:
    """Run a Suptiftam program and print the ``term`` tape's written region."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
