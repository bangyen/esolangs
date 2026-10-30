"""Interpreter for Basicfuck.

Rdococ's variable language that compiles to brainfuck.  Line one is the
directive ``#basicfuck t=<size|unbounded> r=<min>~<max> o=<mode>``, line two
``#allocate`` names the variables (``X``, or ``X->n`` for ``n`` cells, the
first named ``X``), and the rest is statements.  The machine runs the
statements directly: one tape cell per allocated cell, a program counter into
the compiled statements, and a branch or jump for each ``if`` and ``while``.

Commands:
    ``X += Y`` / ``X -= Y``       add or subtract a constant or a variable
    ``if (X) { .. }``             run the block when X is non-zero
    ``while (X) { .. }``          repeat the block while X is non-zero
    ``if !(X)`` / ``while !(X)``  negate the test
    ``write <- X``                print X as a character
    ``read -> X``                 store the next input character's code in X
    ``X->n``                      the cell n past X (``n`` a literal)

Input/output:
    ``read`` takes one character (newlines included), ``write`` prints one.
    ``read`` at EOF raises: the page's cat supports three EOF conventions
    and so fixes none.

Errors:
    ProgramError: a bad directive, ``#allocate``, token or statement, an
        undefined or reserved name, allocations beyond the tape.
    InputExhaustedError: ``read`` at EOF.
    HaltError: an overflow under ``o=halt``; a cell outside the tape; a
        ``write`` of a value that is not a character.

Decisions:
    * Unbounded means unbounded: an omitted end of ``r`` is no limit, and
      ``o`` is ignored when both ends are omitted.  An end given without
      ``o``, or ``wrap`` with an end omitted, is rejected: the page ties
      ``o`` to the range.
    * ``wrap`` is modular over ``min..max``, so adding 300 under ``0~255``
      adds 44; the page's cat needs only 255 + 1 -> 0.
    * ``r`` may start negative (``r=-128~127``): "minimum cell value".
    * Cells start at 0 even when 0 lies outside ``r``; the first write
      applies the overflow rule, as does a ``read`` value outside ``r``.
    * The page's "temporary variables" for ``X += Y`` cost a tape cell: a
      bounded tape keeps one cell back whenever a program adds or subtracts
      a variable, so ``t`` must hold the allocations plus one.  A bounded
      tape is exactly ``t`` cells (less that one), so an ``X->n`` past the
      allocations but inside it is legal (the page's ``arr->3`` is ``z``);
      an unbounded tape is the allocations.
    * ``X->Y`` with a variable ``Y`` ("plus the value of Y") is never
      exercised by the page and raises ProgramError; ``n`` is a literal.
    * ``//`` comments run to end of line; the directives may follow blank or
      comment lines, and ``#allocate`` fits on one line.  A block ends at
      ``}`` and takes no ``;``; every other statement requires one.
"""

from __future__ import annotations

import re

from esolangs.exceptions import HaltError, ProgramError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO

_NAME = r"[A-Za-z_]\w*"
_DIRECTIVE = re.compile(
    r"#basicfuck\s+t=(\d+|unbounded)\s+r=(-?\d*)~(-?\d*)(?:\s+o=(wrap|halt|nearest))?"
)
_ALLOCATE = re.compile(r"#allocate\s*(.*)")
_ITEM = re.compile(rf"\s*({_NAME})(?:->(\d+))?\s*")
_TOKEN = re.compile(rf"\s*(?:({_NAME})|(\d+)|(\+=|-=|->|<-|[!(){{}};]))")
_RESERVED = frozenset({"if", "while", "write", "read"})

#: Opcodes; every op is a tuple led by its code.
_ADD, _BRANCH, _JUMP, _WRITE, _READ = range(5)

type _Op = tuple[int, ...]
#: ``(program counter, tape)``: the whole run state as a value.  The tape
#: has a fixed length (set by ``#allocate``), so a rebuilt tuple costs a
#: constant of the program text, not of the run.
type _State = tuple[int, tuple[int, ...]]
#: ``(min, max, mode)``; ``None`` ends are unbounded and mode is None then.
type _Range = tuple[int | None, int | None, str | None]


def _fit(value: int, rng: _Range) -> int:
    """Return ``value`` under the directive's overflow rule."""
    bot, top, mode = rng
    below = bot is not None and value < bot
    if not below and (top is None or value <= top):
        return value
    if mode == "halt":
        raise HaltError("cell overflow")
    if bot is not None and top is not None and mode == "wrap":
        return bot + (value - bot) % (top - bot + 1)
    if below:
        assert bot is not None
        return bot
    assert top is not None
    return top


def _cell(cells: tuple[int, ...], index: int) -> int:
    """Return the cell at ``index``, or halt outside the tape."""
    if not 0 <= index < len(cells):
        raise HaltError("tape index out of bounds")
    return cells[index]


def _advance(
    state: _State, ops: tuple[_Op, ...], rng: _Range, byte: int | None = None
) -> tuple[_State, str | None]:
    """Return the state after one statement, and the character to print.

    Pure: a ``read`` arrives as ``byte``, a ``write`` leaves as the return.
    """
    pc, cells = state
    op = ops[pc]
    out = None
    code = op[0]
    if code == _ADD:
        _, target, sign, by_cell, operand = op
        amount = _cell(cells, operand) if by_cell else operand
        value = _fit(_cell(cells, target) + sign * amount, rng)
        cells = (*cells[:target], value, *cells[target + 1 :])
    elif code == _BRANCH:
        _, source, want, target = op
        if bool(_cell(cells, source)) != bool(want):
            return (target, cells), None
    elif code == _JUMP:
        return (op[1], cells), None
    elif code == _WRITE:
        value = _cell(cells, op[1])
        if not 0 <= value <= 0x10FFFF:
            raise HaltError("write of a value that is not a character")
        out = chr(value)
    else:
        assert byte is not None
        target = op[1]
        _cell(cells, target)
        cells = (*cells[:target], _fit(byte, rng), *cells[target + 1 :])
    return (pc + 1, cells), out


class _Compiler:
    """One pass over the tokens, producing ops with resolved offsets."""

    def __init__(self, tokens: list[str], offsets: dict[str, int]) -> None:
        self.tokens = tokens
        self.offsets = offsets
        self.at = 0
        self.ops: list[_Op] = []
        self.by_cell = False

    def peek(self) -> str | None:
        return self.tokens[self.at] if self.at < len(self.tokens) else None

    def take(self, expect: str | None = None) -> str:
        if self.at >= len(self.tokens):
            raise ProgramError("unexpected end of program")
        token = self.tokens[self.at]
        if expect is not None and token != expect:
            raise ProgramError(f"expected {expect!r}, got {token!r}")
        self.at += 1
        return token

    def ref(self) -> int:
        """Parse ``X`` or ``X->n`` into a tape offset."""
        name = self.take()
        if not re.fullmatch(_NAME, name) or name in _RESERVED:
            raise ProgramError(f"not a variable: {name!r}")
        if name not in self.offsets:
            raise ProgramError(f"undefined variable {name!r}")
        shift = 0
        if self.peek() == "->":
            self.take()
            number = self.take()
            if not number.isdigit():
                raise ProgramError("X->Y needs a literal Y")
            shift = int(number)
        return self.offsets[name] + shift

    def block(self, closer: str | None) -> None:
        while (token := self.peek()) != closer:
            if token is None:
                raise ProgramError("missing '}'")
            self.statement()

    def statement(self) -> None:
        word = self.peek()
        if word in ("if", "while"):
            self.take()
            want = 1
            if self.peek() == "!":
                self.take()
                want = 0
            self.take("(")
            source = self.ref()
            self.take(")")
            self.take("{")
            start = len(self.ops)
            self.ops.append((_BRANCH, source, want, -1))
            self.block("}")
            self.take("}")
            if word == "while":
                self.ops.append((_JUMP, start))
            self.ops[start] = (_BRANCH, source, want, len(self.ops))
            return
        if word in ("write", "read"):
            self.take()
            self.take("<-" if word == "write" else "->")
            self.ops.append((_WRITE if word == "write" else _READ, self.ref()))
        else:
            target = self.ref()
            sign = {"+=": 1, "-=": -1}.get(self.take())
            if sign is None:
                raise ProgramError("expected '+=' or '-='")
            if (self.peek() or "").isdigit():
                self.ops.append((_ADD, target, sign, 0, int(self.take())))
            else:
                self.ops.append((_ADD, target, sign, 1, self.ref()))
                self.by_cell = True
        self.take(";")


def _tokens(body: str) -> list[str]:
    """Split the statements into names, numbers and punctuation."""
    tokens: list[str] = []
    at = 0
    body = body.rstrip()
    while at < len(body):
        match = _TOKEN.match(body, at)
        if match is None:
            raise ProgramError(f"invalid token at {body[at:].strip()[:12]!r}")
        tokens.append(match.group(match.lastindex or 0))
        at = match.end()
    return tokens


def _range(directive: re.Match[str]) -> tuple[int | None, _Range]:
    """Return the tape size (None: unbounded) and the cell range."""
    size, low, high, mode = directive.groups()
    bot = int(low) if low else None
    top = int(high) if high else None
    length = None if size == "unbounded" else int(size)
    if bot is None and top is None:
        return length, (None, None, None)
    if mode is None:
        raise ProgramError("a bounded range needs o=")
    if mode == "wrap" and (bot is None or top is None):
        raise ProgramError("o=wrap needs both ends of r")
    if bot is not None and top is not None and bot > top:
        raise ProgramError("empty cell range")
    return length, (bot, top, mode)


def _compile(code: str) -> tuple[tuple[_Op, ...], int, _Range]:
    """Return the ops, the tape length and the range of a program."""
    lines = [line.partition("//")[0].strip() for line in code.split("\n")]
    lines = [line for line in lines if line]
    if len(lines) < 2:
        raise ProgramError("missing directive or #allocate")
    directive = _DIRECTIVE.fullmatch(lines[0])
    if directive is None:
        raise ProgramError("missing or invalid #basicfuck directive")
    size, rng = _range(directive)
    allocate = _ALLOCATE.fullmatch(lines[1])
    if allocate is None:
        raise ProgramError("missing #allocate")
    offsets: dict[str, int] = {}
    total = 0
    for item in allocate.group(1).split(","):
        match = _ITEM.fullmatch(item)
        if match is None:
            raise ProgramError(f"invalid allocation {item.strip()!r}")
        name, count = match.group(1), match.group(2)
        if name in _RESERVED or name in offsets:
            raise ProgramError(f"invalid or repeated name {name!r}")
        offsets[name] = total
        total += int(count) if count else 1
    compiler = _Compiler(_tokens(" ".join(lines[2:])), offsets)
    compiler.block(None)
    length = total
    if size is not None:
        length = size - 1 if compiler.by_cell else size
        if total > length:
            raise ProgramError("insufficient memory for the allocations")
    return tuple(compiler.ops), length, rng


class _Machine:
    """The run state: the compiled statements, the program counter, the tape."""

    # ``ip`` counts compiled statements, not source characters.
    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.ops, length, self.range = _compile(code)
        self.state: _State = (0, (0,) * length)

    @property
    def halted(self) -> bool:
        return self.state[0] >= len(self.ops)

    @property
    def ip(self) -> int:
        """The current statement index."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The tape."""
        return list(self.state[1])

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, self.io.progress())

    def step(self) -> None:
        """Execute one statement; the shell owns ``read`` and ``write``."""
        if self.halted:
            return
        byte = self.io.input_char() if self.ops[self.state[0]][0] == _READ else None
        self.state, out = _advance(self.state, self.ops, self.range, byte)
        if out is not None:
            self.io.print_char(out)


def run(code: str, io: IO) -> None:
    """Run a Basicfuck program to its end."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
