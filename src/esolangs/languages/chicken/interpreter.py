r"""Interpreter for Chicken.

Torbjorn Soderstedt's 2013 one-word language.  A line holds ``chicken``
words; its count is an opcode.  One JavaScript-valued array is code, data and
stack at once: cell 0 is the array itself, cell 1 the whole input string,
then one cell per source line, one ``0`` (exit) pad, and the working stack
above it.  The stack top is the array end, so a pop truncates the array and
a push appends.  A step runs the cell at ``ip`` (which starts at 2); a run
ends at an exit and prints the top of the stack.

Commands:
    0 exit.  1 push ``"chicken"``.  2, 3, 4 add, subtract, multiply: pop
    ``a`` then ``b``, push ``b OP a``.  5 push ``b == a`` (loose).
    6 load: the next cell ``v`` (consumed) names the source ``cells[v]``;
    pop ``a``, push ``source[a]`` (0 names the array, 1 the input).
    7 store: pop address ``a``, then value ``v``; ``cells[a] = v``.
    8 jump: pop ``offset``, then ``cond``; if ``cond`` is truthy,
    ``ip += offset`` (``ip`` already past the jump).
    9 char: pop ``x``, push the string ``"&#x;"``.
    10+ push the number ``n - 10``.

Input/output:
    The whole of stdin is the input string, cell 1.  The output is the top of
    the stack at exit as a JavaScript string, with each ``&#<digits>;``
    replaced by that character.

Errors:
    ProgramError: a word other than ``chicken`` in a line.
    HaltError: the array used as a number, string or comparand; a
        non-integer jump offset; a store to a non-index address; a load
        from an ``undefined`` source.
    InterpreterLimitError: a store to an address past the cell limit.

Decisions:
    * Values follow JavaScript: numbers, strings, booleans, ``undefined``.
      ``+`` concatenates if either side is a string, else adds numbers;
      ``-`` and ``*`` coerce to numbers; ``==`` is loose; truthiness is
      JavaScript's (``"0"`` is truthy).  Integers are exact, not doubles.
      A string reads as a number only if it is blank (0) or a decimal
      integer; anything else (``"1.5"``, ``"0x10"``) is NaN.
    * The stack really is the array: the wiki's ``undefined`` example
      (push 7, load) and its NaN example (push 8, load from a five-line
      program) both read past the array end, which only holds if a pop
      truncates.  The 99 Chickens example takes its count from cell 1.
    * Jump offsets count from the cell after the jump: the 99 Chickens loop
      (``push 0, push 23, sub, jump`` back to the loop head) needs it.
    * A source line ends at ``\n``; the text after the last ``\n`` is a line
      only if non-empty, so ``11 6 0`` ends in exactly one blank line.
    * Running off the array (a jump past the end or before the start)
      exits and prints, like reading an undefined cell as opcode 0 in the
      original; a defined non-opcode cell (a hole, a string) pushes
      ``cell - 10`` through the default arm.
    * Only decimal ``&#N;`` entities unescape (the original's replace);
      a code point outside Unicode or a surrogate raises ``HaltError``.
    * A load whose source is a number or boolean yields ``undefined`` (the
      Deadfish example indexes a cell holding 10 to get it).  A key that is
      not a non-negative integer or canonical integer string yields
      ``undefined`` too.
"""

from __future__ import annotations

import re

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._validate import check_address
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error


class _Self:
    """Cell 0: the array itself, which no operator may read as a value."""

    def __repr__(self) -> str:
        return "<stack>"


#: JavaScript ``undefined`` is ``None``: a hole, a read past the end, an
#: empty pop.
SELF = _Self()
NAN = float("nan")

#: A JavaScript value: int or NaN, bool, str, ``undefined``, or the array.
type _Value = int | float | bool | str | _Self | None

_INTEGER = re.compile(r"[+-]?[0-9]+")
_INDEX = re.compile(r"0|[1-9][0-9]*")
_ENTITY = re.compile(r"&#([0-9]+);")


def _number(value: _Value) -> int | float:
    """Return ``Number(value)``."""
    if isinstance(value, _Self):
        raise HaltError(
            "Chicken cannot use the stack array as a number",
            hint="use only numbers, strings and booleans as operands",
        )
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0
        return int(text) if _INTEGER.fullmatch(text) else NAN
    return NAN


def _text(value: _Value) -> str:
    """Return ``String(value)``."""
    if isinstance(value, _Self):
        raise HaltError(
            "Chicken cannot print or join the stack array",
            hint="use only numbers, strings and booleans as operands",
        )
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return "NaN"
    return "undefined" if value is None else str(value)


def _truthy(value: _Value) -> bool:
    if isinstance(value, float):
        return False  # the only float is NaN
    if value is None:
        return False
    return isinstance(value, _Self) or bool(value)


def _equal(left: _Value, right: _Value) -> bool:
    """Return ``left == right`` under JavaScript's loose equality."""
    if isinstance(left, _Self) or isinstance(right, _Self):
        if left is right:
            return True
        raise HaltError(
            "Chicken cannot compare the stack array with another value",
            hint="compare only numbers, strings and booleans",
        )
    if left is None or right is None:
        return left is right
    if isinstance(left, str) and isinstance(right, str):
        return left == right
    return _number(left) == _number(right)


def _nan_once(value: int | float) -> int | float:
    """Return ``value``, with any NaN as the one ``NAN`` object.

    ``nan != nan``, and tuples compare equal only through identity, so a
    fresh NaN from ``NAN - 0`` made equal states snapshot unequal.
    """
    return NAN if isinstance(value, float) else value


def _advance(opcode: int, below: _Value, top: _Value) -> _Value:
    """Return the value opcode 2-5 or 9 pushes for ``below OP top``.

    Pure: ``below`` is the second-from-top operand, ``top`` the top one;
    char reads only ``top``.
    """
    if opcode == 2:
        if isinstance(below, str) or isinstance(top, str):
            return _text(below) + _text(top)
        return _nan_once(_number(below) + _number(top))
    if opcode == 3:
        return _nan_once(_number(below) - _number(top))
    if opcode == 4:
        return _nan_once(_number(below) * _number(top))
    if opcode == 5:
        return _equal(below, top)
    return "&#" + _text(top) + ";"


def _key(value: _Value) -> int | None:
    """Return the array index ``value`` names as a property key, or None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return None
    if isinstance(value, str) and _INDEX.fullmatch(value):
        return int(value)
    return None


def _parse(code: str) -> list[int]:
    """Return one chicken count per line."""
    lines = code.split("\n")
    if lines[-1] == "":
        lines.pop()
    counts = []
    for number, line in enumerate(lines, 1):
        words = line.replace("\r", " ").split(" ")
        if any(word not in ("chicken", "") for word in words):
            raise syntax_error(
                f"Chicken line {number} holds something other than 'chicken'",
                "write only the word chicken, separated by spaces",
            )
        counts.append(sum(word == "chicken" for word in words))
    return counts


class _Machine:
    """The array, the instruction pointer, and the printed answer."""

    ip_shape = "opaque"
    #: The input is one string read whole, so a short one is a shorter string.
    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        counts = _parse(code)
        self.io = io
        self.cells: list[_Value] = [SELF, io.input_all(), *counts, 0]
        self.pointer = 2
        self.done = False

    @property
    def halted(self) -> bool:
        return self.done

    @property
    def ip(self) -> int:
        return self.pointer

    @property
    def stack(self) -> list[_Value]:
        """The working stack above the code, top last."""
        return list(self.cells)

    def snapshot(self) -> tuple[object, ...]:
        return (self.pointer, tuple(self.cells), self.io.progress())

    def _pop(self) -> _Value:
        return self.cells.pop() if self.cells else None

    def _get(self, index: int | None) -> _Value:
        if index is None or index >= len(self.cells):
            return None
        return self.cells[index]

    def _load(self) -> None:
        address = _key(self._pop())
        source = self._get(_key(self._get(self.pointer)))
        self.pointer += 1
        if source is None:
            raise HaltError(
                "Chicken load from an undefined source",
                hint="name a source cell holding the array, a string or a number",
            )
        if isinstance(source, _Self):
            self.cells.append(self._get(address))
        elif isinstance(source, str) and address is not None:
            self.cells.append(source[address] if address < len(source) else None)
        else:
            self.cells.append(None)

    def _store(self) -> None:
        address, value = self._pop(), self._pop()
        index = _key(address)
        if index is None:
            raise HaltError(
                f"Chicken store to the non-index address {_text(address)}",
                hint="store to a non-negative integer address",
            )
        check_address(index, "Chicken")
        if index >= len(self.cells):
            self.cells.extend([None] * (index + 1 - len(self.cells)))
        self.cells[index] = value

    def _jump(self) -> None:
        offset, condition = self._pop(), self._pop()
        if not _truthy(condition):
            return
        if not isinstance(offset, int):
            raise HaltError(
                f"Chicken jump by the non-integer offset {_text(offset)}",
                hint="push an integer offset before jumping",
            )
        self.pointer += offset

    def _exit(self) -> None:
        text = _text(self._pop())
        self.done = True
        self.io.print_str(_ENTITY.sub(_unescape, text))

    def step(self) -> None:
        if self.done:
            return
        if not 0 <= self.pointer < len(self.cells):
            self._exit()  # an undefined opcode is falsy: the exit arm
            return
        cell = self.cells[self.pointer]
        self.pointer += 1
        if type(cell) is int and 0 <= cell <= 9:
            if cell == 0:
                self._exit()
            elif cell == 1:
                self.cells.append("chicken")
            elif cell in (2, 3, 4, 5, 9):
                top = self._pop()
                below = top if cell == 9 else self._pop()
                self.cells.append(_advance(cell, below, top))
            elif cell == 6:
                self._load()
            elif cell == 7:
                self._store()
            else:
                self._jump()
            return
        number = _number(cell) - 10
        self.cells.append(number)


def _unescape(match: re.Match[str]) -> str:
    code = int(match.group(1))
    if code > 0x10FFFF or 0xD800 <= code <= 0xDFFF:
        raise HaltError(
            f"Chicken cannot print the code point {code}",
            hint="use a code point in 0..0x10FFFF outside the surrogates",
        )
    return chr(code)


def run(code: str, io: IO) -> None:
    """Run Chicken: read the lines, execute from cell 2, print at exit."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
