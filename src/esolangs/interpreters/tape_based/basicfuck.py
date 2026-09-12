r"""Interpreter for Basicfuck."""

from __future__ import annotations

import re
import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_NAME = r"[_a-zA-Z]\w*"
_DIRECTIVE = re.compile(
    r"#basicfuck t=(\d+|unbounded) r=(\d*)~(\d*)( o=(wrap|halt|nearest))?\s*$"
)
_ALLOCATE = re.compile(r"#allocate(?:\s*" + _NAME + r"(?:->\d+)?,?)*\s*$")
_ASSIGN = re.compile(_NAME + r"(?:->\d+)?\s*[+-]=\s*" + _NAME + r"(?:->\d+)?")
_IDENT = re.compile(r"(\s*(" + _NAME + r")(?:->(\d+))?,?)(.*)$", re.S)
_NAME_ONLY = re.compile(_NAME + r"(?:->\d+)?$")


def _index(key: str, var: list[tuple[str, int]]) -> int:
    r"""Return the tape offset of ``key`` (``X`` or ``X->n``)."""
    ind = 0
    if "->" in key:
        name, _, idx = key.partition("->")
        ind += int(idx)
        key = name
    for name, size in var:
        if name != key:
            ind += size
        else:
            return ind
    raise ValueError("Identifier is undefined.")


def _parse_allocate(line: str) -> tuple[list[tuple[str, int]], list[int]]:
    r"""Parse the ``#allocate`` line into (variables, initial tape cells)."""
    if not _ALLOCATE.fullmatch(line):
        raise ValueError("Missing/Invalid identifiers.")
    var: list[tuple[str, int]] = []
    tape: list[int] = []
    rest = line[len("#allocate") :]
    while (m := _IDENT.match(rest)) is not None:
        size = int(m.group(3)) if m.group(3) else 1
        tape.extend([0] * size)
        name = m.group(2)
        if name in ("if", "while", "write", "read"):
            raise ValueError("Invalid identifier.")
        var.append((name, size))
        rest = m.group(4)
    return var, tape


def _lexer(program: str) -> list[str]:
    r"""Tokenize the body into names, numbers, and punctuation."""
    tokens: list[str] = []
    i = 0
    n = len(program)
    while i < n:
        while i < n and program[i].isspace():
            i += 1
        if i >= n:
            break
        char = program[i]
        if char.isalpha() or char == "_":
            j = i
            while j < n and (program[j].isalnum() or program[j] == "_"):
                j += 1
            if (
                j + 1 < n
                and program[j : j + 2] == "->"
                and j + 2 < n
                and program[j + 2].isdigit()
            ):
                k = j + 2
                while k < n and program[k].isdigit():
                    k += 1
                tokens.append(program[i:k])
                i = k
            else:
                tokens.append(program[i:j])
                i = j
        elif char.isdigit():
            j = i
            while j < n and program[j].isdigit():
                j += 1
            tokens.append(program[i:j])
            i = j
        elif char in "!(){};":
            tokens.append(char)
            i += 1
        elif program[i : i + 2] in ("+=", "-=", "->", "<-"):
            tokens.append(program[i : i + 2])
            i += 2
        else:
            raise ValueError("Invalid token.")
    return tokens


def _parser(tokens: list[str], var: list[tuple[str, int]]) -> tuple[int, ...]:
    r"""Compile the tokens to the flat instruction tuple the machine runs."""
    result: list[int] = []
    ind = 0
    size = len(tokens)
    pair = 0

    def fail() -> None:
        raise ValueError("Invalid syntax.")

    def find(n: int) -> None:
        result.append(_index(tokens[ind + n], var))

    while ind < size:
        s = tokens[ind]
        ind += 1
        if (s == "if" or s == "while") and ind + 4 < size:
            result.append(-3 if s == "if" else -4)
            if tokens[ind] == "!":
                result.append(-7)
                ind += 1
            ok = ind < size and tokens[ind] == "("
            if ok:
                ind += 1
                ok = ind < size and _NAME_ONLY.match(tokens[ind]) is not None
                if ok:
                    ind += 1
                    ok = ind < size and tokens[ind] == ")"
                    if ok:
                        ind += 1
                        ok = ind < size and tokens[ind] == "{"
                        if ok:
                            ind += 1
            if not ok:
                fail()
            pair += 1
            find(-3)
            result.append(-8)
        elif (s == "write" or s == "read") and ind + 2 < size:
            arrow = "<-" if s == "write" else "->"
            ok = ind < size and tokens[ind] == arrow
            if ok:
                ind += 1
                ok = ind < size and _NAME_ONLY.match(tokens[ind]) is not None
                if ok:
                    ind += 1
                    ok = ind < size and tokens[ind] == ";"
                    if ok:
                        ind += 1
            if not ok:
                fail()
            result.append(-5 if s == "write" else -6)
            find(-2)
        elif _NAME_ONLY.match(s) is not None and ind + 2 < size:
            if not (tokens[ind] in ("+=", "-=") and tokens[ind + 2] == ";"):
                fail()
            result.append(-1 if tokens[ind] == "+=" else -2)
            ind += 1
            sec = tokens[ind]
            find(-2)
            if _NAME_ONLY.match(sec) is not None:
                find(0)
            else:
                if not sec.isdigit():
                    fail()
                n = 2 * int(sec)
                if n > 0:
                    n -= 1
                result.append(-n - 10)
            ind += 2
        elif s == "}":
            result.append(-9)
            pair -= 1
        else:
            fail()
    if pair != 0:
        fail()
    return tuple(result)


# : One active scope: ``(prog,.
# :.
# : A frame whose ``loop`` is.
# : (the body itself is a.
# : completes, the owner.
#: continues past the loop.
# :.
# : A tuple rather than a.
# : can hash without unpacking.
type _Frame = tuple[tuple[int, ...], int, bool, int, bool, tuple[int, ...] | None]

# : The tape, as a value.
# : first instruction runs, so.
type _Cells = tuple[int, ...]

# : One instant of a run: the.
type _State = tuple[_Cells, tuple[_Frame, ...]]


def _frame(prog: tuple[int, ...]) -> _Frame:
    r"""Build a fresh frame for ``prog``, at its start and owning no loop."""
    return (prog, 0, False, -1, False, None)


def _read_cell(cells: _Cells, index: int) -> int:
    r"""Read a tape cell, rejecting an index outside the allocation."""
    if not 0 <= index < len(cells):
        raise HaltError("tape index out of bounds")
    return cells[index]


def _write_cell(cells: _Cells, index: int, value: int) -> _Cells:
    r"""Return ``cells`` with one cell replaced, bounds-checked."""
    if not 0 <= index < len(cells):
        raise HaltError("tape index out of bounds")
    return (*cells[:index], value, *cells[index + 1 :])


def _cond_of(cells: _Cells, frame: _Frame, cond_pos: int, *, neg: bool) -> bool:
    r"""Evaluate the condition at ``cond_pos`` in ``frame``'s code."""
    return bool(_read_cell(cells, frame[0][cond_pos])) ^ neg


def _finalize(state: _State) -> _State:
    r"""Pop completed frames, re-running a while body while it holds."""
    cells, frames = state
    while frames:
        prog, ptr, _, _, _, _ = frames[-1]
        if ptr < len(prog):
            return (cells, frames)  # an active frame is still.
        frames = frames[:-1]
        if frames and frames[-1][2]:
            parent = frames[-1]
            if _cond_of(cells, parent, parent[3], neg=parent[4]):
                return (cells, (*frames, _frame(parent[5] or ())))
            frames = (*frames[:-1], (*parent[:2], False, *parent[3:]))
    return (cells, frames)


def _clamp(value: int, bot: int, top: int, mode: str) -> int:
    r"""Apply the directive's overflow rule to an out-of-range value."""
    if value < bot:
        if mode == "h":
            raise HaltError("Underflow error.")
        return top if mode == "w" else bot
    if value > top:
        if mode == "h":
            raise HaltError("Overflow error.")
        return bot if mode == "w" else top
    return value


def _scan_body(prog: tuple[int, ...], start: int) -> int:
    r"""Return the index of the ``}`` closing the block opened at ``start``."""
    end = start
    pair = 1
    while pair != 0:
        end += 1
        inner = prog[end]
        if inner == -8:
            pair += 1
        elif inner == -9:
            pair -= 1
    return end


def _advance(
    state: _State,
    bot: int,
    top: int,
    mode: str,
    byte: int | None = None,
) -> tuple[_State, str | None]:
    r"""Execute one instruction of the active frame."""
    cells, frames = _finalize(state)
    if not frames:
        return (cells, frames), None

    prog, ptr, loop, cond_pos_f, neg_f, body_f = frames[-1]
    if ptr >= len(prog):
        return (cells, frames), None  # a finished empty loop body.

    op = prog[ptr]
    ptr += 1
    output: str | None = None

    if op > -3:  # += / -=.
        num = prog[ptr + 1]
        if num < 0:  # a constant, encoded below -10.
            num += 10
            num = (num - 1) // -2 if num % 2 else num // 2
        else:  # a variable: read its current.
            num = _read_cell(cells, num)
        if op == -2:
            num = -num
        cell = prog[ptr]
        cells = _write_cell(
            cells, cell, _clamp(_read_cell(cells, cell) + num, bot, top, mode)
        )
        ptr += 2
        top_frame: _Frame = (prog, ptr, loop, cond_pos_f, neg_f, body_f)
        return (cells, (*frames[:-1], top_frame)), output

    if op > -5:  # if / while.
        cond_pos = ptr  # the position of the condition.
        neg = False
        if prog[ptr] == -7:
            neg = True
            ptr += 1
        ptr += 1  # past the condition variable,.
        end = _scan_body(prog, ptr)
        body = prog[ptr + 1 : end]
        cond = _cond_of(
            cells,
            (prog, ptr, loop, cond_pos_f, neg_f, body_f),
            cond_pos + (1 if neg else 0),
            neg=neg,
        )
        if op == -3:  # if.
            owner: _Frame = (prog, end + 1, loop, cond_pos_f, neg_f, body_f)
            grown = (*frames[:-1], owner)
            if cond:
                grown = (*grown, _frame(body))
            return (cells, grown), output
        # while: the owner keeps the.
        owner = (prog, end + 1, True, cond_pos + (1 if neg else 0), neg, body)
        grown = (*frames[:-1], owner)
        if cond:
            grown = (*grown, _frame(body))
        return (cells, grown), output

    if op == -5:  # write.
        output = chr(_read_cell(cells, prog[ptr]))
        ptr += 1
    else:  # read.
        cells = _write_cell(cells, prog[ptr], byte if byte is not None else 0)
        ptr += 1

    return (cells, (*frames[:-1], (prog, ptr, loop, cond_pos_f, neg_f, body_f))), output


class _Machine:
    r"""Per-run Basicfuck state: the compiled code, tape, and frame stack."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Parse and compile ``code`` and start the top-level frame."""
        self.io = io
        lines = code.split("\n")
        directive = lines[0] if lines else ""
        allocate = lines[1] if len(lines) > 1 else ""
        body = "\n".join(lines[2:])

        m = _DIRECTIVE.fullmatch(directive)
        if not m:
            raise ValueError("Missing/Invalid directives.")
        lim = -1 if m.group(1) == "unbounded" else int(m.group(1))
        mode_count = (1 if m.group(2) else 0) + (1 if m.group(3) else 0)
        if mode_count != 0 and m.group(4) is None:
            raise ValueError("Missing overflow directive.")
        if mode_count != 2 and m.group(5) == "wrap":
            raise ValueError("Invalid overflow directive.")
        bot = int(m.group(2)) if m.group(2) else -(2**31)
        top = int(m.group(3)) if m.group(3) else 2**31 - 1
        mode = m.group(5)[0] if m.group(5) else "n"

        var, tape = _parse_allocate(allocate)

        body = re.sub(r"//[^\n]*", "", body)
        # the cross-check reserves a.
        if _ASSIGN.search(body) and lim != -1:
            lim -= 1
        if lim != -1 and lim < len(tape):
            raise ValueError("Insufficient memory.")

        instructions = _parser(_lexer(body), var)
        self.mode = mode
        self.bot = bot
        self.top = top
        self.cells: _Cells = tuple(tape)
        self.frames: tuple[_Frame, ...] = (_frame(instructions),)

    @property
    def halted(self) -> bool:
        r"""Whether every scope has completed."""
        return not self.frames

    # The VM's language-shaped.
    # cursor, memory tape.

    @property
    def ip(self) -> int | None:
        r"""The current instruction position."""
        return self.frames[-1][1] if self.frames else None

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return list(self.cells)

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # A frame is already a tuple of.
        # in as it stands rather than.
        return (self.cells, self.frames, self.io.position())

    def step(self) -> None:
        r"""Execute one instruction of the active frame."""
        if self.halted:
            return

        cells, frames = _finalize((self.cells, self.frames))
        byte = None
        if frames:
            prog, ptr, _, _, _, _ = frames[-1]
            if ptr < len(prog) and prog[ptr] == -6:
                byte = self.io.input_char()

        state, output = _advance((cells, frames), self.bot, self.top, self.mode, byte)
        self.cells, self.frames = state
        if output is not None:
            self.io.print_char(output)


def run(code: str, io: IO) -> None:
    r"""Run a Basicfuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
