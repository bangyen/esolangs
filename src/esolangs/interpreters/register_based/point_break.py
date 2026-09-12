r"""Interpreter for Point Break."""

import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Literal

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_KEYWORDS = frozenset({"LET", "POINT", "IF", "BREAK", "END"})
_OPERATORS = frozenset({"+", "-", "*", "/"})
_OPERANDS = frozenset({"input", "name", "num"})

# A token:.
Token = tuple[str, str]

Let = tuple[Literal["let"], str, list[Token]]
Point = tuple[Literal["point"], str, str]
IfBreak = tuple[Literal["if_break"], str, str]
End = tuple[Literal["end"], str, str]
Statement = Let | Point | IfBreak | End


def _tokenize(line: str) -> list[Token]:
    r"""Tokenize one line; ``#`` starts a comment and stops the scan."""
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
    r"""Raise :class:`ValueError` unless ``tokens`` is a valid expression."""
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
    r"""Parse one line's tokens into a statement tuple."""
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
    r"""Return the index of the open loop frame for ``label``."""
    for i, frame in enumerate(frames):
        if frame[0] == label:
            return i
    raise ValueError(f"no open loop {label!r}")


def _structure(stmts: list[Statement]) -> dict[int, tuple[int, bool]]:
    r"""Validate the loop structure and map POINT indexes to their END."""
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


# : The variable store, as a.
# : returns a new one rather.
type _Vars = Mapping[str, int]

# : The open loop frames,.
type _Frames = tuple[tuple[str, int], ...]

# : The ``?`` port.
# : expression holding several.
#: it -- see :func:`_eval`.
type _Read = Callable[[], int]

# : One instant of a run:.
type _State = tuple[_Vars, _Frames, int]


def _eval(expr: list[Token], variables: _Vars, read: _Read) -> int:
    r"""Evaluate a validated expression; ``?`` reads a number from input."""
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
    r"""Return the state after executing one statement."""
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

    # if_break.
    _, var, label = stmt
    if var not in variables:
        raise HaltError(f"undefined variable {var!r}")
    if not variables[var]:
        return (variables, frames, pc + 1)
    pos = _frame_index(frames, label)
    end, implicit = ends[frames[pos][1]]
    return (variables, frames[:pos], end if implicit else end + 1)


class _Machine:
    r"""Per-run Point Break state: statements, variables, frames, cursor."""

    # : Whether the variables are.
    # : belongs to the language,.
    # : its loop with one more.
    # : ``halted`` has driven the.
    #: its output.
    dumps_on_the_post_halt_step = True

    def __init__(self, code: str | list[str], io: IO) -> None:
        r"""Parse ``code`` into statements."""
        self.io = io
        # Out of ``snapshot``: the dump.
        # compares states of a running.
        self._dumped = False
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
        r"""Whether the cursor has run past the last statement."""
        return self.pc >= len(self.stmts)

    @property
    def dumped(self) -> bool:
        r"""Whether the end-of-run variable dump has already been printed."""
        return self._dumped

    # The VM's language-shaped.
    # cursor.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.pc

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return [self.variables[k] for k in sorted(self.variables)]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            self.pc,
            tuple(sorted(self.variables.items())),
            self.frames,
            self.io.position(),
        )

    @property
    def _state(self) -> _State:
        r"""The machine's fields as the value the transition works on."""
        return (self.variables, self.frames, self.pc)

    def _restore(self, state: _State) -> None:
        r"""Write a transition's result back onto the machine's fields."""
        variables, self.frames, self.pc = state
        self.variables = dict(variables)

    def step(self) -> None:
        r"""Execute one statement, or dump the variables after the halt."""
        if self.halted:
            if not self.dumped:
                self.io.print_str(" ".join(map(str, self.memory)))
                self._dumped = True
            return
        self._restore(_advance(self._state, self.stmts, self.ends, self.io.input_num))


def run(code: str | list[str], io: IO) -> None:
    r"""Execute a Point Break program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    machine.step()  # the post-halt step prints the.


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
