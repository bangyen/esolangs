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

The execution model is a pure function over an immutable ``_State``: the
variables, the open loop frames, and the statement cursor.  :func:`_advance`
maps a state and the program's static tables to the next state and never
edits what it is given; :meth:`_Machine.step` rebinds the three fields from
what it returned, so the mutation lives in exactly one place.

The statements and the loop structure stay out of the state: Point Break
never rewrites its own program, and both are computed once when the machine
is parsed.

``?`` is the language's only port, and it stays a callback rather than
being hoisted into the shell.  An expression may hold several of them, and
they are read *as the evaluation reaches them* -- so an expression that
divides by zero or names an undefined variable stops without consuming the
inputs to its right.  Reading them all up front would consume input the
original run leaves alone, which is a difference a corpus of programs whose
expressions raise mid-way can see.
"""

import sys
from collections.abc import Callable, Mapping, Sequence
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


def _frame_index(frames: Sequence[tuple[str, int]], label: str) -> int:
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


#: The variable store, as a mapping.  A value, not a record: the transition
#: returns a new one rather than editing the one it was handed.
type _Vars = Mapping[str, int]

#: The open loop frames, innermost last: ``(label, the POINT's index)``.
type _Frames = tuple[tuple[str, int], ...]

#: The ``?`` port.  A callback rather than a pre-read list, because an
#: expression holding several of them reads each as the evaluation reaches
#: it -- see :func:`_eval`.
type _Read = Callable[[], int]

#: One instant of a run: ``(variables, frames, pc)``.
type _State = tuple[_Vars, _Frames, int]


def _eval(expr: list[Token], variables: _Vars, read: _Read) -> int:
    """Evaluate a validated expression; ``?`` reads a number from input.

    Pure in its state: it only reads ``variables``.  ``read`` is the ``?``
    port, and it is called *as the walk reaches it* -- an expression that
    raises part-way therefore leaves the inputs to its right unread, which
    is behaviour the input cursor records.
    """
    pos = 0

    def factor() -> int:
        nonlocal pos
        kind, value = expr[pos]
        pos += 1
        if kind == "input":
            return read()
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


def _advance(
    state: _State,
    stmts: tuple[Statement, ...],
    ends: Mapping[int, tuple[int, bool]],
    read: _Read,
) -> _State:
    """Return the state after executing one statement.

    Pure in its state: it reads ``state`` and returns a new one.  ``read``
    is the ``?`` port, reached only through :func:`_eval`.

    ``END`` and a taken ``BREAK`` both cut the frame stack back to the
    loop they name.  They differ in where they resume: ``END`` jumps to the
    ``POINT`` that opened the loop, so the body runs again, while ``BREAK``
    resumes after the ``END`` that closes it -- or *at* that ``END`` when
    the loop is closed implicitly by an ancestor's, which is what makes the
    wiki's examples behave as named.
    """
    variables, frames, pc = state
    stmt = stmts[pc]

    if stmt[0] == "let":
        value = _eval(stmt[2], variables, read)
        return ({**variables, stmt[1]: value}, frames, pc + 1)
    if stmt[0] == "point":
        return (variables, (*frames, (stmt[1], pc)), pc + 1)
    if stmt[0] == "end":
        pos = _frame_index(frames, stmt[1])
        return (variables, frames[:pos], frames[pos][1])

    # if_break
    _, var, label = stmt
    if var not in variables:
        raise HaltError(f"undefined variable {var!r}")
    if not variables[var]:
        return (variables, frames, pc + 1)
    pos = _frame_index(frames, label)
    end, implicit = ends[frames[pos][1]]
    return (variables, frames[:pos], end if implicit else end + 1)


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
        self.stmts = tuple(stmts)
        self.ends = _structure(stmts)
        self.variables: dict[str, int] = {}
        self.frames: tuple[tuple[str, int], ...] = ()
        self.pc = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has run past the last statement."""
        return self.pc >= len(self.stmts)

    # The VM's language-shaped view: Variable store + loop frames; ip is the statement
    # cursor.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.pc

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [self.variables[k] for k in sorted(self.variables)]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.pc,
            tuple(sorted(self.variables.items())),
            self.frames,
            self.io.position(),
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (self.variables, self.frames, self.pc)

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields."""
        variables, self.frames, self.pc = state
        self.variables = dict(variables)

    def step(self) -> None:
        """Execute one statement, advancing the machine.

        The one port lives here rather than in the transition: this is the
        shell.  It is handed over as a callback because ``?`` is read as
        the expression walk reaches it, not before the statement runs.
        """
        if self.halted:
            return
        self._restore(_advance(self._state, self.stmts, self.ends, self.io.input_num))


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
