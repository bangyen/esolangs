"""Interpreter for Point Break.

Point Break is a variable-based imperative language with four commands:
``LET`` assigns a variable the value of an arithmetic expression (``?`` in
an expression reads a number from input), ``POINT``/``END`` delimit a
labeled infinite loop, and ``IF``/``BREAK`` exits a labeled loop when a
variable is nonzero.  The language has no output command, so a program's
only observable behavior is whether it halts.

The wiki leaves several details open; this interpreter decides as follows.
``BREAK`` resumes after the ``END`` that closes the loop; a loop closed
implicitly by an ancestor's ``END`` (which also ends its children) resumes
at that ``END`` instead, so it loops back -- the reading that makes the
wiki's truth-machine and while-loop examples behave as named.  Expressions
use standard precedence (``*``/``/`` bind tighter than ``+``/``-``,
left-associative), division is floor division, and a ``+``/``-`` directly
before a digit is a signed literal when an operand is expected.  An
undefined variable or division by zero is an invalid operation and halts
the program with :class:`~esolangs.exceptions.HaltError`; a malformed
statement or expression, an unmatched ``END``, a ``BREAK`` outside its
loop, a duplicate loop label, and an unclosed loop are malformed programs
and are rejected with :class:`ValueError`.  An empty loop body is
permitted (it loops forever) and an empty program is a no-op.

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import sys
from typing import Literal

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_KEYWORDS = frozenset({"LET", "POINT", "IF", "BREAK", "END"})
_OPERATORS = frozenset({"+", "-", "*", "/"})
_OPERANDS = frozenset({"input", "name", "num"})

# A token: ("keyword"|"name"|"num"|"op", text) or ("input"|"assign", "").
Token = tuple[str, str]

Let = tuple[Literal["let"], str, list[Token]]
Point = tuple[Literal["point"], str, str]
IfBreak = tuple[Literal["if_break"], str, str]
End = tuple[Literal["end"], str, str]
Statement = Let | Point | IfBreak | End


def _tokenize(line: str) -> list[Token]:
    """Tokenize one line; ``#`` starts a comment and stops the scan."""
    tokens: list[Token] = []
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if c.isspace():
            i += 1
        elif c == "#":
            break
        elif c == "?":
            tokens.append(("input", ""))
            i += 1
        elif c == ":":
            if i + 1 < n and line[i + 1] == "=":
                tokens.append(("assign", ""))
                i += 2
            else:
                raise ValueError("malformed assignment operator (expected ':=')")
        elif "a" <= c <= "z":
            j = i
            while j < n and "a" <= line[j] <= "z":
                j += 1
            tokens.append(("name", line[i:j]))
            i = j
        elif "A" <= c <= "Z":
            j = i
            while j < n and "A" <= line[j] <= "Z":
                j += 1
            if (word := line[i:j]) in _KEYWORDS:
                tokens.append(("keyword", word))
            else:
                raise ValueError(f"unknown keyword {word!r}")
            i = j
        elif "0" <= c <= "9":
            j = i
            while j < n and "0" <= line[j] <= "9":
                j += 1
            tokens.append(("num", line[i:j]))
            i = j
        elif (
            c in "+-"
            and i + 1 < n
            and "0" <= line[i + 1] <= "9"
            and (not tokens or tokens[-1][0] not in _OPERANDS)
        ):
            j = i + 1
            while j < n and "0" <= line[j] <= "9":
                j += 1
            tokens.append(("num", line[i:j]))
            i = j
        elif c in _OPERATORS:
            tokens.append(("op", c))
            i += 1
        else:
            raise ValueError(f"unexpected character {c!r}")
    return tokens


def _check_expr(tokens: list[Token]) -> None:
    """Raise :class:`ValueError` unless ``tokens`` is a valid expression.

    An expression alternates operands (``?``, a number, or a variable) and
    operators, starting and ending with an operand.
    """
    if not tokens or tokens[0][0] not in _OPERANDS:
        raise ValueError("malformed expression")
    expect_operand = False
    for tok in tokens[1:]:
        if expect_operand and tok[0] not in _OPERANDS:
            raise ValueError("malformed expression")
        if not expect_operand and tok[0] != "op":
            raise ValueError("malformed expression")
        expect_operand = not expect_operand
    if expect_operand:
        raise ValueError("malformed expression")


def _parse_statement(tokens: list[Token]) -> Statement:
    """Parse one line's tokens into a statement tuple."""
    first = tokens[0]
    if first == ("keyword", "LET") and len(tokens) >= 4:
        name_tok, assign_tok = tokens[1], tokens[2]
        if name_tok[0] == "name" and assign_tok[0] == "assign":
            expr = tokens[3:]
            _check_expr(expr)
            return ("let", name_tok[1], expr)
    if first == ("keyword", "POINT") and len(tokens) == 2 and tokens[1][0] == "name":
        return ("point", tokens[1][1], "")
    if (
        len(tokens) == 4
        and first == ("keyword", "IF")
        and tokens[1][0] == "name"
        and tokens[2] == ("keyword", "BREAK")
        and tokens[3][0] == "name"
    ):
        return ("if_break", tokens[1][1], tokens[3][1])
    if first == ("keyword", "END") and len(tokens) == 2 and tokens[1][0] == "name":
        return ("end", tokens[1][1], "")
    raise ValueError("malformed statement")


def _frame_index(frames: list[tuple[str, int]], label: str) -> int:
    """Return the index of the open loop frame for ``label``.

    A plain loop rather than a ``next()`` generator expression, so a
    timeout signal cannot interrupt the evaluation mid-frame and leave the
    coverage tracer's lock held.  The static structure walk guarantees the
    frame is present at runtime, so the fallback only fires during the
    parse-time check of an unmatched ``END``.
    """
    for i, frame in enumerate(frames):
        if frame[0] == label:
            return i
    raise ValueError(f"no open loop {label!r}")


def _structure(stmts: list[Statement]) -> dict[int, tuple[int, bool]]:
    """Validate the loop structure and map POINT indexes to their END.

    Returns ``{pointe_index: (end_index, implicit)}`` where ``implicit``
    records that the loop is closed by an ancestor's ``END`` rather than
    its own.  Raises :class:`ValueError` for an unmatched ``END``, a
    ``BREAK`` outside its loop, a duplicate label, or an unclosed loop.
    """
    ends: dict[int, tuple[int, bool]] = {}
    frames: list[tuple[str, int]] = []
    labels: set[str] = set()
    for idx, stmt in enumerate(stmts):
        kind = stmt[0]
        if kind == "point":
            label = stmt[1]
            if label in labels:
                raise ValueError(f"duplicate loop label {label!r}")
            labels.add(label)
            frames.append((label, idx))
        elif kind == "end":
            label = stmt[1]
            pos = _frame_index(frames, label)
            for child in frames[pos + 1 :]:
                ends[child[1]] = (idx, True)
            ends[frames[pos][1]] = (idx, False)
            del frames[pos:]
        elif kind == "if_break":
            inside = False
            for frame in frames:
                if frame[0] == stmt[2]:
                    inside = True
                    break
            if not inside:
                raise ValueError(f"BREAK {stmt[2]} outside its loop")
    if frames:
        raise ValueError(f"unclosed loop {frames[-1][0]!r}")
    return ends


def _eval(expr: list[Token], variables: dict[str, int], io: IO) -> int:
    """Evaluate a validated expression; ``?`` reads a number from input."""
    pos = 0

    def factor() -> int:
        nonlocal pos
        kind, value = expr[pos]
        pos += 1
        if kind == "input":
            return io.input_num()
        if kind == "name":
            if value not in variables:
                raise HaltError(f"undefined variable {value!r}")
            return variables[value]
        return int(value)

    def term() -> int:
        nonlocal pos
        value = factor()
        while pos < len(expr) and expr[pos][0] == "op" and expr[pos][1] in "*/":
            op = expr[pos][1]
            pos += 1
            right = factor()
            if op == "*":
                value *= right
            elif right == 0:
                raise HaltError("division by zero")
            else:
                value //= right
        return value

    def add() -> int:
        nonlocal pos
        value = term()
        while pos < len(expr) and expr[pos][0] == "op" and expr[pos][1] in "+-":
            op = expr[pos][1]
            pos += 1
            right = term()
            if op == "+":
                value += right
            else:
                value -= right
        return value

    return add()


class _Machine:
    """Per-run Point Break state: statements, variables, frames, cursor.

    ``step()`` executes one statement and ``halted`` says whether the
    program is done, the shape the VM wrapper and the state-cycle hang
    detector expect.  :meth:`snapshot` returns the complete internal state
    — the cursor, variables, open loop frames, and the input cursor — so a
    repeated snapshot is a *proof* that a deterministic run loops forever.
    """

    def __init__(self, code: str | list[str], io: IO) -> None:
        """Parse ``code`` into statements.

        A malformed program raises :class:`ValueError` here; the runtime
        :class:`HaltError`s fire during ``step`` instead.
        """
        self.io = io
        lines = code.splitlines() if isinstance(code, str) else code
        stmts: list[Statement] = []
        for line in lines:
            tokens = _tokenize(line)
            if tokens:
                stmts.append(_parse_statement(tokens))
        self.stmts = stmts
        self.ends = _structure(stmts)
        self.variables: dict[str, int] = {}
        self.frames: list[tuple[str, int]] = []
        self.pc = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has run past the last statement."""
        return self.pc >= len(self.stmts)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.pc,
            tuple(sorted(self.variables.items())),
            tuple(self.frames),
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one statement, advancing the machine."""
        if self.halted:
            return
        stmt = self.stmts[self.pc]
        if stmt[0] == "let":
            self.variables[stmt[1]] = _eval(stmt[2], self.variables, self.io)
            self.pc += 1
        elif stmt[0] == "point":
            self.frames.append((stmt[1], self.pc))
            self.pc += 1
        elif stmt[0] == "end":
            label = stmt[1]
            pos = _frame_index(self.frames, label)
            self.pc = self.frames[pos][1]
            del self.frames[pos:]
        else:  # if_break
            _, var, label = stmt
            if var not in self.variables:
                raise HaltError(f"undefined variable {var!r}")
            if self.variables[var]:
                pos = _frame_index(self.frames, label)
                end, implicit = self.ends[self.frames[pos][1]]
                del self.frames[pos:]
                self.pc = end if implicit else end + 1
            else:
                self.pc += 1


def run(code: str | list[str], io: IO) -> None:
    """Execute a Point Break program.

    The program is a sequence of statements, one per line, with ``#``
    starting a line comment; ``code`` may be a single string or a list of
    lines.
    """
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
