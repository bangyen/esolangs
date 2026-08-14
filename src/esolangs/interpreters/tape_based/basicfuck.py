"""Interpreter for Basicfuck.

A source-level language compiled to cells by the interpreter itself.  A
``#basicfuck t=.. r=.. o=..`` directive sets the tape size, cell range, and
overflow behavior (``wrap``/``halt``/``nearest``); ``#allocate`` names the
variables (plain ``X`` or array ``X->n``).  ``X += Y`` / ``X -= Y`` add or
subtract a constant or another variable, ``if``/``while (X) { ... }`` branch
and loop (with an optional ``!`` negating the condition), ``write <- X``
prints X as a byte, ``read -> X`` stores the next input byte, and ``X->n``
indexes into an allocated array.  ``//`` comments are stripped.

Semantics match the Rust cross-check (``extra/rust/basicfuck.rs``):
- malformed programs (a bad directive, identifier, token, syntax, or a tape
  too small for the allocations) raise :class:`ValueError`;
- a ``halt`` underflow/overflow raises :class:`HaltError`, while ``wrap``
  and ``nearest`` bound the cell instead;
- an array access past the allocation (``X->n`` beyond the array) raises
  :class:`HaltError`, and the reference exits 3 too (it used to be undefined
  out-of-bounds memory);
- ``,`` (read) stores the first byte of a line and raises
  :class:`EOFError` when input runs out, where the reference exits with
  status 3.
"""

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
    """Return the tape offset of ``key`` (``X`` or ``X->n``)."""
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
    """Parse the ``#allocate`` line into (variables, initial tape cells)."""
    if not _ALLOCATE.fullmatch(line):
        raise ValueError("Missing/Invalid identifiers.")
    var: list[tuple[str, int]] = []
    tape: list[int] = []
    rest = line[len("#allocate") :]
    while True:
        m = _IDENT.match(rest)
        if not m:
            break
        size = int(m.group(3)) if m.group(3) else 1
        tape.extend([0] * size)
        name = m.group(2)
        if name in ("if", "while", "write", "read"):
            raise ValueError("Invalid identifier.")
        var.append((name, size))
        rest = m.group(4)
        if not rest.strip():
            break
    return var, tape


def _lexer(program: str) -> list[str]:
    """Tokenize the body into names, numbers, and punctuation."""
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


def _parser(tokens: list[str], var: list[tuple[str, int]]) -> list[int]:
    """Compile the tokens to the flat instruction list the executor runs.

    Prefix notation mirrors the C++ reference: ``+=`` -1, ``-=`` -2, ``if``
    -3, ``while`` -4, ``write`` -5, ``read`` -6, ``!`` -7, ``{`` -8, ``}``
    -9; nonnegative numbers are variable tape offsets and constants below -9
    are encoded as ``-2n-9`` (odd) / ``2n-10`` (even) for positive/negative
    ``n``.
    """
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
    return result


def _execute(
    prog: list[int],
    tape: _BoundedTape,
    mode: str,
    bot: int,
    top: int,
    io: IO,
    ptr: int,
) -> None:
    """Run the compiled ``prog`` starting at ``ptr`` (mirrors the C++ run())."""
    size = len(prog)
    while ptr < size:
        op = prog[ptr]
        ptr += 1
        if op > -3:  # += / -=
            num = prog[ptr + 1]
            if num < 0:  # a constant, encoded below -10
                num += 10
                if num % 2:
                    num = (num - 1) // -2
                else:
                    num //= 2
            else:  # a variable: read its current value
                num = tape[num]
            if op == -2:
                num = -num
            cell = prog[ptr]
            value = tape[cell] + num
            if value < bot:
                if mode == "h":
                    raise HaltError("Underflow error.")
                value = top if mode == "w" else bot
            if value > top:
                if mode == "h":
                    raise HaltError("Overflow error.")
                value = bot if mode == "w" else top
            tape[cell] = value
            ptr += 2
        elif op > -5:  # if / while
            neg = False
            if prog[ptr] == -7:
                neg = True
                ptr += 1
            ptr += 1
            end = ptr
            ptr += 1
            pair = 1
            while pair != 0:
                end += 1
                inner = prog[end]
                if inner == -8:
                    pair += 1
                elif inner == -9:
                    pair -= 1
            body = prog[ptr:end]
            cond = bool(tape[prog[ptr - 2]]) ^ neg
            if op == -3:
                if cond:
                    _execute(body, tape, mode, bot, top, io, 0)
            else:
                while cond:
                    _execute(body, tape, mode, bot, top, io, 0)
                    cond = bool(tape[prog[ptr - 2]]) ^ neg
            ptr = end + 1
        elif op == -5:  # write
            io.print_char(chr(tape[prog[ptr]] & 0xFF))
            ptr += 1
        else:  # read
            tape[prog[ptr]] = io.input_char()
            ptr += 1


def run(code: str, io: IO) -> None:
    """Run a Basicfuck program."""
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
    # the reference reserves a cell for variable-variable arithmetic
    if _ASSIGN.search(body) and lim != -1:
        lim -= 1
    if lim != -1 and lim < len(tape):
        raise ValueError("Insufficient memory.")

    instructions = _parser(_lexer(body), var)
    _execute(instructions, _BoundedTape(tape), mode, bot, top, io, 0)


class _BoundedTape:
    """A tape that treats an out-of-allocation index as an invalid operation.

    An array access past its allocation (``X->n`` beyond the array) is
    undefined in the reference; both it and the interpreter now halt with an
    invalid operation instead of reading or writing memory.
    """

    def __init__(self, cells: list[int]) -> None:
        """Wrap the allocated ``cells`` with bounds checks."""
        self._cells = cells

    def __len__(self) -> int:
        return len(self._cells)

    def __getitem__(self, index: int) -> int:
        if not 0 <= index < len(self._cells):
            raise HaltError("tape index out of bounds")
        return self._cells[index]

    def __setitem__(self, index: int, value: int) -> None:
        if not 0 <= index < len(self._cells):
            raise HaltError("tape index out of bounds")
        self._cells[index] = value

    def append(self, value: int) -> None:
        """Append a cell (used by the pointer growth)."""
        self._cells.append(value)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
