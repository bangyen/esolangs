"""Interpreter for Basicfuck.

A source-level language compiled to cells by the interpreter itself.  A
``#basicfuck t=.. r=.. o=..`` directive sets the tape size, cell range, and
overflow behavior (``wrap``/``halt``/``nearest``); ``#allocate`` names the
variables (plain ``X`` or array ``X->n``).  ``X += Y`` / ``X -= Y`` add or
subtract a constant or another variable, ``if``/``while (X) { ... }`` branch
and loop (with an optional ``!`` negating the condition), ``write <- X``
prints X as a byte, ``read -> X`` stores the next input byte, and ``X->n``
indexes into an allocated array.  ``//`` comments are stripped.

Semantics:
- malformed programs (a bad directive, identifier, token, syntax, or a tape
  too small for the allocations) raise :class:`ValueError`;
- a ``halt`` underflow/overflow raises :class:`HaltError`, while ``wrap``
  and ``nearest`` bound the cell instead;
- an array access past the allocation (``X->n`` beyond the array) raises
  :class:`HaltError`, and the cross-check exits 3 too (it used to be
  undefined out-of-bounds memory);
- ``,`` (read) stores the first byte of a line and raises
  :class:`EOFError` when input runs out, where the cross-check exits with
  status 3.

The interpreter runs on a :class:`_Machine` (the compiled instructions, the
tape, and an explicit frame stack for the nested if/while scopes), so it is
step-capable: ``step()`` executes one instruction and ``halted`` is true once
no frame remains.  A while loop whose body never changes its condition is a
finite-state cycle the state-cycle hang detector can prove (an empty body
loop is a no-op step whose repeated snapshot proves a hang); the ``run()``
backstop stays for the unbounded-growth class (a loop whose body keeps
growing a tape cell).
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


def _parser(tokens: list[str], var: list[tuple[str, int]]) -> tuple[int, ...]:
    """Compile the tokens to the flat instruction tuple the machine runs.

    Prefix notation: ``+=`` -1, ``-=`` -2, ``if``
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
    return tuple(result)


class _Frame:
    """One active scope: its code, cursor, and the while loop it serves.

    A frame whose ``loop`` is True is the owner of a running ``while`` body
    (the body itself is a separate frame on top of it); when that body
    completes, the owner re-checks its condition and re-runs the body or
    continues past the loop.
    """

    __slots__ = ("body", "cond_pos", "loop", "neg", "prog", "ptr")

    def __init__(
        self,
        prog: tuple[int, ...],
        ptr: int = 0,
        *,
        loop: bool = False,
        cond_pos: int = -1,
        neg: bool = False,
        body: tuple[int, ...] | None = None,
    ) -> None:
        self.prog = prog
        self.ptr = ptr
        self.loop = loop
        self.cond_pos = cond_pos
        self.neg = neg
        self.body = body


class _Machine:
    """Per-run Basicfuck state: the compiled code, tape, and frame stack.

    ``step()`` executes one instruction of the active frame; ``halted`` is
    true once no frame remains.  A while loop whose body never changes its
    condition is a finite-state cycle the state-cycle hang detector can
    prove.  The VM and the hang detector expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Parse and compile ``code`` and start the top-level frame."""
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
        # the cross-check reserves a cell for variable-variable arithmetic
        if _ASSIGN.search(body) and lim != -1:
            lim -= 1
        if lim != -1 and lim < len(tape):
            raise ValueError("Insufficient memory.")

        instructions = _parser(_lexer(body), var)
        self.mode = mode
        self.bot = bot
        self.top = top
        self.tape = _BoundedTape(tape)
        self.frames: list[_Frame] = [_Frame(instructions)]

    @property
    def halted(self) -> bool:
        """Whether every scope has completed."""
        return not self.frames

    # The VM's language-shaped view: Compiled code + frame stack; ip the top frame's
    # cursor, memory tape.

    @property
    def ip(self) -> int | None:
        """The current instruction position."""
        return self.frames[-1].ptr if self.frames else None

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.tape.cells())

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.tape.cells(),
            tuple(
                (f.prog, f.ptr, f.loop, f.cond_pos, f.neg, f.body) for f in self.frames
            ),
            self.io.position(),
        )

    def _cond(self, frame: _Frame, cond_pos: int, *, neg: bool) -> bool:
        """Evaluate the condition at ``cond_pos`` in ``frame``'s code."""
        return bool(self.tape[frame.prog[cond_pos]]) ^ neg

    def _finalize_finished(self) -> None:
        """Pop completed frames, re-running a while body while it holds.

        Only the top frame can be finished at a time; a loop body that still
        has its condition met starts a fresh pass (finalized by a later step,
        so an empty body is a no-op step whose repeated snapshot proves a
        hang).
        """
        while self.frames:
            frame = self.frames[-1]
            if frame.ptr < len(frame.prog):
                return  # an active frame is still running
            self.frames.pop()
            if self.frames and self.frames[-1].loop:
                parent = self.frames[-1]
                if self._cond(parent, parent.cond_pos, neg=parent.neg):
                    self.frames.append(_Frame(parent.body or ()))
                    return
                parent.loop = False

    def step(self) -> None:
        """Execute one instruction of the active frame."""
        if self.halted:
            return
        self._finalize_finished()
        if not self.frames:
            return
        frame = self.frames[-1]
        prog = frame.prog
        if frame.ptr >= len(prog):
            return  # a finished empty loop body is a no-op step
        op = prog[frame.ptr]
        frame.ptr += 1

        if op > -3:  # += / -=
            num = prog[frame.ptr + 1]
            if num < 0:  # a constant, encoded below -10
                num += 10
                if num % 2:
                    num = (num - 1) // -2
                else:
                    num //= 2
            else:  # a variable: read its current value
                num = self.tape[num]
            if op == -2:
                num = -num
            cell = prog[frame.ptr]
            value = self.tape[cell] + num
            if value < self.bot:
                if self.mode == "h":
                    raise HaltError("Underflow error.")
                value = self.top if self.mode == "w" else self.bot
            if value > self.top:
                if self.mode == "h":
                    raise HaltError("Overflow error.")
                value = self.bot if self.mode == "w" else self.top
            self.tape[cell] = value
            frame.ptr += 2
        elif op > -5:  # if / while
            cond_pos = frame.ptr  # the position of the condition variable
            neg = False
            if prog[frame.ptr] == -7:
                neg = True
                frame.ptr += 1
            frame.ptr += 1  # past the condition variable, at the body start
            body_start = frame.ptr
            end = body_start
            frame.ptr += 1
            pair = 1
            while pair != 0:
                end += 1
                inner = prog[end]
                if inner == -8:
                    pair += 1
                elif inner == -9:
                    pair -= 1
            body = prog[frame.ptr : end]
            cond = self._cond(frame, cond_pos + (1 if neg else 0), neg=neg)
            if op == -3:  # if
                if cond:
                    self.frames.append(_Frame(body))
                frame.ptr = end + 1
            else:  # while
                frame.ptr = end + 1  # the continuation past the loop
                frame.loop = True
                frame.cond_pos = cond_pos + (1 if neg else 0)
                frame.neg = neg
                frame.body = body
                if cond:
                    self.frames.append(_Frame(body))
        elif op == -5:  # write
            self.io.print_char(chr(self.tape[prog[frame.ptr]]))
            frame.ptr += 1
        else:  # read
            self.tape[prog[frame.ptr]] = self.io.input_char()
            frame.ptr += 1


def run(code: str, io: IO) -> None:
    """Run a Basicfuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


class _BoundedTape:
    """A tape that treats an out-of-allocation index as an invalid operation.

    An array access past its allocation (``X->n`` beyond the array) is
    undefined in the cross-check; both it and the interpreter now halt with an
    invalid operation instead of reading or writing memory.
    """

    def __init__(self, cells: list[int]) -> None:
        """Wrap the allocated ``cells`` with bounds checks."""
        self._cells = cells

    def cells(self) -> tuple[int, ...]:
        """Return the allocated cells as a tuple (hashable for snapshots)."""
        return tuple(self._cells)

    def __getitem__(self, index: int) -> int:
        if not 0 <= index < len(self._cells):
            raise HaltError("tape index out of bounds")
        return self._cells[index]

    def __setitem__(self, index: int, value: int) -> None:
        if not 0 <= index < len(self._cells):
            raise HaltError("tape index out of bounds")
        self._cells[index] = value


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
