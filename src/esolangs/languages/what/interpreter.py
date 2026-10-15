r"""Interpreter for What!?.

A pointer walks two parallel 256-slot tapes: integers (unsigned 16-bit,
initially 0) and strings (initially empty).  The program is a flat token
sequence run left to right; it halts past the last token.  A numeric
literal replaces the current integer, a ``"..."`` literal appends to the
current string, and ``+ - * /`` combine the current integer with the one
to its left into the current cell.  ``( ... )`` is a do-while loop on the
current integer; ``[lit op code]`` compares the current value of the
literal's type and, when false, skips past the next ``]``.  The wiki's
Hello World, cat and truth machine run as stated.

Commands:
    ``!`` integer as a character, ``!!`` as a decimal, ``!!!`` the string,
    ``!!!!`` a newline; ``?`` a character's code, ``??`` a decimal,
    ``???`` a line appended to the string; ``,``/``.`` pointer left/right;
    ``'s'`` subtracts ``len(s)``.  Runs of ``!`` and ``?`` split greedily
    into the longest operators; any other character is a no-op.
    Conditional operators: ``:`` equal, ``<`` literal smaller, ``>``
    literal greater, combined by OR; ``;`` negates (alone, ``:;``).

Input/output:
    ``?`` reads one character; ``??`` a whitespace-delimited integer;
    ``???`` one line.  A read at EOF yields 0 or the empty string.

Errors:
    ProgramError: An unterminated quote; an unmatched loop marker; a ``[``
        without a later ``]``, a literal or an operator; a repeated
        conditional operator; a numeric literal over 65535; a ``\`` escape
        other than ``\n``.
    ArgumentError: ``??`` given a non-integer token.
    HaltError: Moving off the tape; arithmetic at slot 0; ``/`` by 0;
        a string over 256 characters; a read over 65535; ``!`` of a
        surrogate.

Decisions:
    * "Previous integer value" is the slot to the left: the truth machine
      ``,1.(-)`` stores 1 there to count down.
    * Arithmetic wraps modulo 65536, so the truth machine's ``(-)`` from 0
      ends at 0; clamping would too, wrapping is the C reading.
    * A false conditional skips to the first later ``]``, nesting ignored:
      the page reads markers "individually", ``[0:]]`` as ``[0:] ]``.  An
      executed ``]`` does nothing, so ``[0:(]`` opens a loop.
    * Loop markers match statically, ignoring conditionals.
    * Strings order by code point, as C's ``strcmp`` does.
    * ``\n`` in a string is a newline: 99 Bottles writes ``".\n"``.
      Its ``'s'`` before the loop makes it count from 98, kept as written.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from esolangs.exceptions import HaltError
from esolangs.runtime import persistent
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO

_CELLS = 256
_WORD = 1 << 16
_COMPARE = frozenset(":;<>")
_DIGITS = frozenset("0123456789")

#: ``(token index, pointer, integer tape, string tape)``.
type _State = tuple[int, int, persistent.Chunked[int], persistent.Chunked[str]]


@dataclass(frozen=True, slots=True)
class _Token:
    """One command.  ``arg`` is a number, a length, a run size or a jump."""

    kind: str
    at: int
    arg: int = 0
    text: str = ""
    literal: int | str = 0
    ops: str = ""


def _quoted(code: str, i: int) -> tuple[str, int]:
    """The ``"..."`` text starting at ``code[i]``, and the offset past it."""
    out: list[str] = []
    j = i + 1
    while j < len(code) and code[j] != '"':
        if code[j] == "\\":
            if code[j + 1 : j + 2] != "n":
                raise ValueError(f"What!?: unknown escape at offset {j}")
            out.append("\n")
            j += 2
            continue
        out.append(code[j])
        j += 1
    if j >= len(code):
        raise ValueError(f"What!?: unterminated string at offset {i}")
    return "".join(out), j + 1


def _number(code: str, i: int) -> tuple[int, int]:
    j = i
    while j < len(code) and code[j] in _DIGITS:
        j += 1
    value = int(code[i:j])
    if value >= _WORD:
        raise ValueError(f"What!?: literal {value} at offset {i} exceeds 65535")
    return value, j


def _skip_space(code: str, i: int) -> int:
    while i < len(code) and code[i].isspace():
        i += 1
    return i


def _condition(code: str, i: int) -> tuple[_Token, int]:
    """Parse ``[lit op`` at ``code[i]``; the jump is filled in later."""
    j = _skip_space(code, i + 1)
    literal: int | str
    if code[j : j + 1] == '"':
        literal, j = _quoted(code, j)
    elif code[j : j + 1] in _DIGITS:
        literal, j = _number(code, j)
    else:
        raise ValueError(f"What!?: conditional at offset {i} lacks a literal")
    j = _skip_space(code, j)
    k = j
    while k < len(code) and code[k] in _COMPARE:
        k += 1
    ops = code[j:k]
    if not ops or len(set(ops)) != len(ops):
        raise ValueError(f"What!?: bad conditional operator at offset {j}")
    return _Token("cond", i, literal=literal, ops=ops), k


def parse(code: str) -> list[_Token]:
    """Return the token sequence with jumps resolved; bad syntax raises."""
    tokens: list[_Token] = []
    i = 0
    while i < len(code):
        c = code[i]
        if c in _DIGITS:
            value, j = _number(code, i)
            tokens.append(_Token("num", i, value))
            i = j
        elif c == '"':
            text, j = _quoted(code, i)
            tokens.append(_Token("str", i, text=text))
            i = j
        elif c == "'":
            j = code.find("'", i + 1)
            if j < 0:
                raise ValueError(f"What!?: unterminated quote at offset {i}")
            tokens.append(_Token("sub", i, j - i - 1))
            i = j + 1
        elif c in "!?":
            j = i
            while j < len(code) and code[j] == c:
                j += 1
            size = 4 if c == "!" else 3
            kind = "out" if c == "!" else "in"
            for start in range(i, j, size):
                tokens.append(_Token(kind, start, min(size, j - start)))
            i = j
        elif c == "[":
            token, i = _condition(code, i)
            tokens.append(token)
        else:
            if c in ",.+-*/()]":
                tokens.append(_Token(c, i))
            i += 1
    return _link(tokens)


def _link(tokens: list[_Token]) -> list[_Token]:
    """Point each ``)`` at its ``(`` and each conditional past its ``]``."""
    opens: list[int] = []
    pending: list[int] = []
    for k, token in enumerate(tokens):
        if token.kind == "(":
            opens.append(k)
        elif token.kind == ")":
            if not opens:
                raise ValueError(f"What!?: unmatched ')' at offset {token.at}")
            tokens[k] = replace(token, arg=opens.pop())
        elif token.kind == "cond":
            pending.append(k)
        elif token.kind == "]":
            for p in pending:
                tokens[p] = replace(tokens[p], arg=k + 1)
            pending = []
    if opens:
        raise ValueError(f"What!?: unmatched '(' at offset {tokens[opens[-1]].at}")
    if pending:
        raise ValueError(f"What!?: '[' at offset {tokens[pending[0]].at} lacks a ']'")
    return tokens


def _holds(token: _Token, cur: int, here: str) -> bool:
    """Whether ``token``'s test holds against the slot's integer or string."""
    literal = token.literal
    if isinstance(literal, str):
        order = (literal > here) - (literal < here)
    else:
        order = (literal > cur) - (literal < cur)
    ops = token.ops
    tests = {":": order == 0, "<": order < 0, ">": order > 0}
    named = [tests[op] for op in ops if op != ";"]
    base = any(named) if named else tests[":"]
    return not base if ";" in ops else base


def _advance(
    state: _State, tokens: list[_Token], value: int | str | None = None
) -> tuple[_State, int | str | None]:
    """Return the state after one token, and what it prints.

    Pure: a read arrives as ``value``.  A printed ``int`` is a decimal, a
    ``str`` is written as is.
    """
    ind, ptr, ints, strs = state
    token = tokens[ind]
    kind = token.kind
    cur = persistent.get(ints, ptr)
    nxt = ind + 1
    out: int | str | None = None
    if kind == "num":
        ints = persistent.put(ints, ptr, token.arg)
    elif kind == "str" or (kind == "in" and token.arg == 3):
        added = token.text if kind == "str" else str(value)
        text = persistent.get(strs, ptr) + added
        if len(text) > _CELLS:
            raise HaltError("What!?: a string exceeds 256 characters")
        strs = persistent.put(strs, ptr, text)
    elif kind == "sub":
        ints = persistent.put(ints, ptr, (cur - token.arg) % _WORD)
    elif kind == "in":
        assert isinstance(value, int)
        if not 0 <= value < _WORD:
            raise HaltError(f"What!?: input {value} does not fit 16 bits")
        ints = persistent.put(ints, ptr, value)
    elif kind == "out":
        if token.arg == 1:
            if 0xD800 <= cur < 0xE000:
                raise HaltError(f"What!?: {cur} is a surrogate, not a character")
            out = chr(cur)
        elif token.arg == 2:
            out = cur
        else:
            out = persistent.get(strs, ptr) if token.arg == 3 else "\n"
    elif kind in ",.":
        ptr += 1 if kind == "." else -1
        if not 0 <= ptr < _CELLS:
            raise HaltError("What!?: the pointer left the 256-slot tape")
    elif kind in "+-*/":
        if ptr == 0:
            raise HaltError(f"What!?: {kind} at slot 0 has no previous value")
        prev = persistent.get(ints, ptr - 1)
        if kind == "/" and prev == 0:
            raise HaltError("What!?: division by zero")
        result = {
            "+": cur + prev,
            "-": cur - prev,
            "*": cur * prev,
            "/": cur // prev if prev else 0,
        }[kind]
        ints = persistent.put(ints, ptr, result % _WORD)
    elif kind == ")":
        if cur:
            nxt = token.arg + 1
    elif kind == "cond" and not _holds(token, cur, persistent.get(strs, ptr)):
        nxt = token.arg
    return (nxt, ptr, ints, strs), out


class _Machine:
    """The run state: token index, pointer and the two tapes."""

    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        self.tokens = parse(code)
        self.io = io
        self.state: _State = (
            0,
            0,
            persistent.chunked([0] * _CELLS),
            persistent.chunked([""] * _CELLS),
        )

    @property
    def halted(self) -> bool:
        return self.state[0] >= len(self.tokens)

    @property
    def ip(self) -> int:
        """The current token's character offset."""
        ind = self.state[0]
        return self.tokens[ind].at if ind < len(self.tokens) else -1

    @property
    def memory(self) -> list[int]:
        """The integer tape."""
        return list(persistent.flatten(self.state[2]))

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, self.io.progress())

    def _read(self, size: int) -> int | str:
        """Take a ``?``-run's input; EOF gives 0 or the empty string."""
        try:
            if size == 1:
                return self.io.input_char()
            if size == 2:
                return self.io.input_num()
            return self.io.input_str()
        except EOFError:
            return 0 if size < 3 else ""

    def step(self) -> None:
        """Execute one token.

        The shell: the two ports live here and nothing else does.
        """
        if self.halted:
            return
        token = self.tokens[self.state[0]]
        value = self._read(token.arg) if token.kind == "in" else None
        self.state, out = _advance(self.state, self.tokens, value)
        if isinstance(out, int):
            self.io.print_num(out)
        elif out is not None:
            self.io.print_str(out)


def run(code: str, io: IO) -> None:
    """Run a What!? program."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
