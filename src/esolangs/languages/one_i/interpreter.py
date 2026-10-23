"""Interpreter for 1 + i.

One stack of complex numbers and functions; ``[...]`` pushes a function
and the only number literal is ``i``.  ``?`` pops a decider and invokes
the function on top of the stack when it is nonzero, the one below it when
it is zero; both stay on the stack, and ``?`` as a function's last
command is a tail call.  The program halts at its end.  The wiki's
examples and its constants table run as stated, but for 22, whose
expression is 12 under any operand order.

Commands:
    ``c l e /``: conjugate, principal log, exp, reciprocal of the top.
    ``+ * ^``: add, multiply, power; the second value popped is the left
        operand, the base of ``^``, and ``0^0`` is 1.
    ``> <``: pop ``b`` then ``a``; push 0 when ``a > b`` (``a < b``), else 1.
    ``% : ( ) $``: swap top and bottom, duplicate, move the bottom to the
        top, move the top to the bottom, discard.
    ``p o``: print a number; print its real part, and its imaginary part
        from 256 up, as bytes.

Input/output:
    ``A`` reads a character's code point and pushes ``i`` at EOF; ``B`` and
    ``C`` read a decimal token, ``D`` a line in ``p``'s format.  ``p``
    writes ``a``, ``bi``, ``a + bi`` or ``a - bi``; ``o`` writes each byte
    as the character with that code point.

Errors:
    ProgramError: A character that is no command; an unmatched bracket.
    InputExhaustedError: ``B``, ``C`` or ``D`` at EOF.
    ArgumentError: ``B`` given a token that is not an integer.
    HaltError: Underflow; a function where a number is needed; a non-real
        comparison; ``?`` reaching a non-function or nothing; a zero
        reciprocal; ``l`` of 0; overflow; ``C`` or ``D`` text that does not
        parse.

Decisions:
    * ``?`` peeks its functions and takes the top one on nonzero, and ``(``
      and ``)`` roll as above: the wiki's truth machine and cat need both.
    * Arithmetic is exact over Gaussian rationals; ``l``, ``e`` and powers
      other than integer powers of exact numbers use floating point.
    * ``p`` prints a non-integer real as Python's shortest float text,
      ``i``/``-i`` for a unit coefficient, and ``a - bi`` for a negative
      imaginary part.
    * Whitespace is ignored.  ``%`` and the rolls leave a stack of fewer
      than two values as it is.
"""

from __future__ import annotations

import cmath
import math
import re
from array import array
from bisect import bisect_left
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO

#: An exact Gaussian rational ``(re, im)``, or a float once inexact.
type _Num = tuple[Fraction, Fraction] | complex
type _Value = _Num | _Fn
#: ``(function, next text index, next command number)`` frames, innermost
#: first; the number keeps a snapshot's bits what a command list gave.
type _Frames = tuple[tuple[_Fn, int, int], _Frames] | None
#: ``(values popped, values pushed, turn)``; ``turn`` is a ``deque.rotate``
#: step, or ``_SWAP`` to exchange the top and bottom.
type _Edit = tuple[int, tuple[_Value, ...], int]

_COMMANDS = "icle+*/^><%:()$ABCDpo?"
_BAD = re.compile(rf"[^{re.escape(_COMMANDS)}\[\]]")
_SPACE = re.compile(r"\s")
_BRACKET = re.compile(r"[\[\]]")
_SWAP = 2
_ZERO = Fraction(0)
_I: _Num = (_ZERO, Fraction(1))
_REAL = r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
_UNSIGNED = r"(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"


class _Code:
    """The program text, whitespace dropped, with each ``[``'s closing ``]``.

    Flat: a parsed tree of ``(offset, char)`` tuples cost ~120 bytes a
    command (1.1 GB parsed at n = 20, 9.1M characters); this is ~3.
    """

    def __init__(self, code: str) -> None:
        #: Source offset of each text index; ``None`` while no whitespace.
        self.origin: array[int] | None = None
        self.text = text = code
        if _SPACE.search(code):
            self.text = text = "".join(code.split())
            self.origin = array("q", (i for i, c in enumerate(code) if not c.isspace()))
        #: Each ``[``'s text index, ascending, and its ``]``'s: ~2 bytes a
        #: character where an array over the whole text cost 4.
        self.opens = array("q")
        self.closes = array("q")
        bad = _BAD.search(text)
        limit = bad.start() if bad else len(text)
        open_ks: list[int] = []
        for found in _BRACKET.finditer(text, 0, limit):
            at = found.start()
            if found.group() == "[":
                open_ks.append(len(self.opens))
                self.opens.append(at)
                self.closes.append(0)
            elif open_ks:
                self.closes[open_ks.pop()] = at
            else:
                raise ValueError(f"1 + i: unmatched ']' at {self.offset(at)}")
        if bad:
            raise ValueError(
                f"1 + i has no command {bad.group()!r} at {self.offset(limit)}"
            )
        if open_ks:
            raise ValueError(
                f"1 + i: unmatched '[' at {self.offset(self.opens[open_ks[-1]])}"
            )

    def close(self, at: int) -> int:
        """The text index of the ``]`` closing the ``[`` at ``at``."""
        return self.closes[bisect_left(self.opens, at)]

    def offset(self, at: int) -> int:
        """The source offset of text index ``at``."""
        return at if self.origin is None else self.origin[at]


@dataclass(frozen=True, eq=False)
class _Fn:
    """A function literal: the text between a ``[`` and its ``]``.

    Compared and hashed by identity, so O(1).
    """

    code: _Code
    #: Text index of the ``[``, ``-1`` for the program: the function's name.
    start: int
    #: Text index one past the last command.
    end: int

    @property
    def offset(self) -> int:
        """The ``[``'s source offset, ``-1`` for the program."""
        return -1 if self.start < 0 else self.code.offset(self.start)

    def __repr__(self) -> str:
        return f"_Fn(offset={self.offset})"


def _parse(code: str) -> _Fn:
    """Return the program as a function; brackets nest."""
    flat = _Code(code)
    return _Fn(flat, -1, len(flat.text))


def _complex(value: _Num) -> complex:
    if isinstance(value, complex):
        return value
    return complex(float(value[0]), float(value[1]))


def _number(value: _Value, command: str) -> _Num:
    if isinstance(value, _Fn):
        raise HaltError(f"1 + i {command} needs a number, got a function")
    return value


def _add(a: _Num, b: _Num) -> _Num:
    if isinstance(a, tuple) and isinstance(b, tuple):
        return (a[0] + b[0], a[1] + b[1])
    return _complex(a) + _complex(b)


def _mul(a: _Num, b: _Num) -> _Num:
    if isinstance(a, tuple) and isinstance(b, tuple):
        return (a[0] * b[0] - a[1] * b[1], a[0] * b[1] + a[1] * b[0])
    return _complex(a) * _complex(b)


def _recip(a: _Num) -> _Num:
    if isinstance(a, complex):
        return 1 / a
    norm = a[0] * a[0] + a[1] * a[1]
    if not norm:
        raise ZeroDivisionError
    return (a[0] / norm, -a[1] / norm)


def _pow(base: _Num, power: _Num) -> _Num:
    exact = isinstance(base, tuple) and isinstance(power, tuple)
    if exact and not power[1] and power[0].denominator == 1:  # type: ignore[index]
        k = int(power[0])  # type: ignore[index]
        result: _Num = (Fraction(1), _ZERO)
        square = base
        k_left = abs(k)
        while k_left:
            if k_left & 1:
                result = _mul(result, square)
            k_left >>= 1
            if k_left:
                square = _mul(square, square)
        return result if k >= 0 else _recip(result)
    if _complex(base) == 0 and _complex(power) == 0:
        return (Fraction(1), _ZERO)
    return _complex(base) ** _complex(power)


def _is_zero(value: _Num) -> bool:
    if isinstance(value, complex):
        return value == 0
    return not value[0] and not value[1]


def _parts(value: _Num) -> tuple[Fraction | float, Fraction | float]:
    return (value.real, value.imag) if isinstance(value, complex) else value


def _real_text(x: Fraction | float) -> str:
    if isinstance(x, Fraction):
        return str(x.numerator) if x.denominator == 1 else repr(float(x))
    return str(int(x)) if math.isfinite(x) and x.is_integer() else repr(x)


def _text(value: _Num) -> str:
    """``p``'s rendering: ``a``, ``bi``, ``i``, ``a + bi`` or ``a - bi``."""
    re_part, im_part = _parts(value)
    if not im_part:
        return _real_text(re_part)
    size: Fraction | float = -im_part if im_part < 0 else im_part
    coefficient = "i" if size == 1 else _real_text(size) + "i"
    if not re_part:
        return ("-" if im_part < 0 else "") + coefficient
    return f"{_real_text(re_part)} {'-' if im_part < 0 else '+'} {coefficient}"


def _bytes(value: _Num) -> str:
    """``o``'s bytes: the real part, and the imaginary part from 256 up."""
    re_part, im_part = _parts(value)
    out = chr(math.floor(re_part) % 256)
    if im_part >= 256:
        out += chr(math.floor(im_part) % 256)
    return out


def _read_real(token: str) -> _Num:
    if not re.fullmatch(_REAL, token):
        raise HaltError(f"1 + i C needs a real number, got {token!r}")
    return (Fraction(token), _ZERO)


def _read_complex(line: str) -> _Num:
    text = line.strip()
    if re.fullmatch(_REAL, text):
        return (Fraction(text), _ZERO)
    match = re.fullmatch(rf"(?:({_REAL})\s*([+-])\s*|([+-]?))({_UNSIGNED})?i", text)
    if match is None:
        raise HaltError(f"1 + i D needs a complex number, got {line!r}")
    real, sign, alone, size = match.groups()
    negative = (sign or alone) == "-"
    coefficient = Fraction(size) if size else Fraction(1)
    return (
        Fraction(real) if real else _ZERO,
        -coefficient if negative else coefficient,
    )


def _arith(command: str, operands: list[_Num]) -> _Num:
    """Apply a numeric command to its operands, bottom first."""
    if command == "i":
        return _I
    if command == "c":
        a = operands[0]
        return a.conjugate() if isinstance(a, complex) else (a[0], -a[1])
    if command == "l":
        return cmath.log(_complex(operands[0]))
    if command == "e":
        return cmath.exp(_complex(operands[0]))
    if command == "/":
        return _recip(operands[0])
    a, b = operands
    if command == "+":
        return _add(a, b)
    if command == "*":
        return _mul(a, b)
    if command == "^":
        return _pow(a, b)
    if _parts(a)[1] or _parts(b)[1]:
        raise HaltError(f"1 + i {command} compares only real numbers")
    above = _parts(a)[0] > _parts(b)[0]
    below = _parts(a)[0] < _parts(b)[0]
    return (Fraction(0 if (above if command == ">" else below) else 1), _ZERO)


_ARITY = {"i": 0, "c": 1, "l": 1, "e": 1, "/": 1, "p": 1, "o": 1}


def _advance(
    frames: _Frames, stack: Sequence[_Value], got: _Value | None = None
) -> tuple[_Frames, _Edit, str | None]:
    """Run one command: the new frames, the stack edit, any output.

    Pure: ``stack`` (top last) is only read, and a read arrives as ``got``.
    """
    assert frames is not None
    (fn, pc, nth), rest = frames
    code = fn.code
    command: str | _Fn = code.text[pc]
    offset = code.offset(pc)
    after = pc + 1
    if command == "[":
        after = code.close(pc)
        command = _Fn(code, pc, after)
        after += 1
    frames = ((fn, after, nth + 1), rest)
    edit: _Edit = (0, (), 0)
    out = None
    if isinstance(command, _Fn):
        edit = (0, (command,), 0)
    elif command in "ABCD":
        assert got is not None
        edit = (0, (got,), 0)
    elif command in ":$":
        if not stack:
            raise HaltError(f"1 + i {command} needs a value")
        edit = (0, (stack[-1],), 0) if command == ":" else (1, (), 0)
    elif command in "()":
        edit = (0, (), -1 if command == "(" else 1)
    elif command == "%":
        edit = (0, (), _SWAP)
    elif command == "?":
        if not stack:
            raise HaltError("1 + i ? needs a decider")
        decider = _number(stack[-1], "?")
        depth = 3 if _is_zero(decider) else 2
        chosen = stack[-depth] if len(stack) >= depth else None
        if not isinstance(chosen, _Fn):
            raise HaltError("1 + i ? invoked something that is not a function")
        edit = (1, (), 0)
        if after == fn.end:  # a tail call: the caller has nothing left
            frames = rest
        frames = ((chosen, chosen.start + 1, 0), frames)
    else:
        arity = _ARITY.get(command, 2)
        if len(stack) < arity:
            raise HaltError(f"1 + i {command} needs {arity} values")
        operands = [_number(stack[k - arity], command) for k in range(arity)]
        try:
            if command in "po":
                out = (_text if command == "p" else _bytes)(operands[0])
                edit = (1, (), 0)
            else:
                edit = (arity, (_arith(command, operands),), 0)
        except (ZeroDivisionError, OverflowError, ValueError) as exc:
            raise HaltError(
                f"1 + i {command} at {offset}: {exc or 'undefined'}"
            ) from exc
    while frames is not None and frames[0][1] >= frames[0][0].end:
        frames = frames[1]
    return frames, edit, out


class _Machine:
    """The shell around :func:`_advance`: the stack, input and output."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.end = len(code)
        program = _parse(code)
        self.frames: _Frames = ((program, 0, 0), None) if program.end else None
        #: The stack, top at the right.
        self.values: deque[_Value] = deque()

    @property
    def halted(self) -> bool:
        return self.frames is None

    @property
    def ip(self) -> int:
        """The next command's source offset; the code's length once halted."""
        if self.frames is None:
            return self.end
        fn, pc, _ = self.frames[0]
        return fn.code.offset(pc)

    @property
    def stack(self) -> list[_Value]:
        """The stack, bottom first."""
        return list(self.values)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        A function is named by its source offset: its body is fixed source.
        """
        frames: list[tuple[int, int]] = []
        node = self.frames
        while node is not None:
            frames.append((node[0][0].offset, node[0][2]))
            node = node[1]
        values = tuple(
            ("fn", v.offset) if isinstance(v, _Fn) else v for v in self.values
        )
        return (tuple(frames), values, self.io.progress())

    def _read(self, command: str) -> _Value:
        if command == "A":
            try:
                return (Fraction(self.io.input_char()), _ZERO)
            except EOFError:
                return _I
        if command == "B":
            return (Fraction(self.io.input_num()), _ZERO)
        if command == "C":
            return _read_real(self.io.input_token())
        return _read_complex(self.io.input_str())

    def step(self) -> None:
        """Run one command, reading its input first."""
        if self.frames is None:
            return
        fn, pc, _ = self.frames[0]
        command = fn.code.text[pc]
        got = self._read(command) if command in ("A", "B", "C", "D") else None
        self.frames, edit, out = _advance(self.frames, self.values, got)
        popped, pushed, turn = edit
        for _ in range(popped):
            self.values.pop()
        self.values.extend(pushed)
        if turn == _SWAP:
            if self.values:
                self.values[0], self.values[-1] = self.values[-1], self.values[0]
        elif turn:
            self.values.rotate(turn)
        if out is not None:
            self.io.print_str(out)


def run(code: str, io: IO) -> None:
    """Run a 1 + i program."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
