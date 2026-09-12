r"""Interpreter for CV(N)(C)."""

from __future__ import annotations

import math
import sys
from collections.abc import Hashable

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

__all__ = ["run"]

# U+030A COMBINING RING ABOVE,.
# into ``ɰ̊``.
# joins exactly this pair and.
_RING = "̊"
_WHILE_ZERO = "ɰ" + _RING

# The consonant classes.
# structure treats them as a.
# third position, so ``ŋ`` can.
# N of a syllable.
_FRICATIVES = frozenset("θfsʒ")
# ``ɡ`` is U+0261 LATIN SMALL.
# table spells the.
# world.
# Both are accepted, and the.
# tokenization so nothing.
_SCRIPT_G = "ɡ"
_PLOSIVES = frozenset("pkdbt" + _SCRIPT_G + "qʔʡc")
_APPROXIMANTS = frozenset({"ɹ", "j", _WHILE_ZERO, "ɰ", "ʋ"})
_CONSONANTS = _FRICATIVES | _PLOSIVES | _APPROXIMANTS
_NASALS = frozenset("mnŋɲ")
_VOWELS = frozenset("iəæou")

# The function's own alphabet,.
# ``p`` and ``k`` are absent:.
# not a fixed symbol.
_FUNCTION_SYMBOLS = {
    "d": "a",
    "b": "+",
    "t": "-",
    "ɡ": "*",
    "q": "/",
    "ʔ": "(",
    "ʡ": ")",
}

_ADDITIVE = frozenset("+-")
_MULTIPLICATIVE = frozenset("*/")

# The individual commands the.
# reads as the operation it.
# bare IPA character.
# directly: they are membership.
# dispatch these name.
_PRINT_NUM = "θ"
_PRINT_CHAR = "f"
_READ_NUM = "s"
_READ_CHAR = "ʒ"
_CLEAR_FUNCTION = "c"
_POP_FRONT_APPEND = "p"
_INCREMENT = "i"
_DECREMENT = "ə"
_SQUARE = "æ"
_SQRT = "o"
_PUSH_FRONT = "m"
_PUSH_BACK = "n"
_POP_FRONT = "ŋ"
_GOTO = "ɹ"
_GOTO_LINE = "j"
_WHILE_NONZERO = "ɰ"
_LOOP_END = "ʋ"


def _as_int(line: str) -> int:
    r"""Parse an input line as an integer, taking anything else as zero."""
    try:
        return int(line)
    except ValueError:
        return 0


def _tokenize(code: str) -> list[str]:
    r"""Split ``code`` into commands, joining ``ɰ`` with its combining ring."""
    tokens: list[str] = []
    index = 0
    while index < len(code):
        char = code[index]
        if char == "ɰ" and code[index + 1 : index + 2] == _RING:
            tokens.append(_WHILE_ZERO)
            index += 2
            continue
        if char == "g":
            char = _SCRIPT_G
        if char not in _CONSONANTS and char not in _NASALS and char not in _VOWELS:
            raise ValueError(f"not a CV(N)(C) symbol: {char!r}")
        tokens.append(char)
        index += 1
    return tokens


def _syllabify(tokens: list[str]) -> list[int]:
    r"""Return the token index each syllable starts at, or reject the."""
    starts: list[int] = []
    index = 0
    while index < len(tokens):
        starts.append(index)
        if tokens[index] not in _CONSONANTS:
            raise ValueError(f"syllable must start with a consonant: {tokens[index]!r}")
        index += 1
        if index >= len(tokens) or tokens[index] not in _VOWELS:
            raise ValueError("syllable must have a vowel after its consonant")
        index += 1
        if index < len(tokens) and tokens[index] in _NASALS:
            index += 1
        # A consonant here closes this.
        # open the next one with.
        if (
            index < len(tokens)
            and tokens[index] in _CONSONANTS
            and (index + 1 >= len(tokens) or tokens[index + 1] not in _VOWELS)
        ):
            index += 1
    return starts


def _match_loops(tokens: list[str]) -> dict[int, int]:
    r"""Pair every loop opener with its ``ʋ``, rejecting an unbalanced."""
    pairs: dict[int, int] = {}
    stack: list[int] = []
    for index, token in enumerate(tokens):
        if token in (_WHILE_ZERO, _WHILE_NONZERO):
            stack.append(index)
        elif token == _LOOP_END:
            if not stack:
                raise ValueError("loop end with no matching start")
            start = stack.pop()
            pairs[start] = index
            pairs[index] = start
    if stack:
        raise ValueError("loop start with no matching end")
    return pairs


class _Parser:
    r"""A recursive-descent reader for the function the program has built."""

    def __init__(self, symbols: list[str], accumulator: int) -> None:
        r"""Read ``symbols``, substituting ``accumulator`` for every ``a``."""
        self.symbols = symbols
        self.accumulator = accumulator
        self.index = 0

    def _peek(self) -> str | None:
        return self.symbols[self.index] if self.index < len(self.symbols) else None

    def parse(self) -> int:
        r"""Evaluate the whole function, rejecting anything left over."""
        value = self._expression()
        if self.index != len(self.symbols):
            raise _InvalidFunctionError
        return value

    def _expression(self) -> int:
        r"""Evaluate a sum of terms, left to right."""
        value = self._term()
        while (symbol := self._peek()) in _ADDITIVE:
            self.index += 1
            right = self._term()
            # The accumulator is unsigned,.
            # rather than going negative.
            value = value + right if symbol == "+" else max(value - right, 0)
        return value

    def _term(self) -> int:
        r"""Evaluate a product of factors, left to right."""
        value = self._factor()
        while (symbol := self._peek()) in _MULTIPLICATIVE:
            self.index += 1
            right = self._factor()
            if symbol == "*":
                value *= right
                continue
            if right == 0:
                raise HaltError("division by zero in the function")
            value //= right
        return value

    def _factor(self) -> int:
        r"""Evaluate ``a``, a literal, or a parenthesized expression."""
        symbol = self._peek()
        if symbol is None:
            raise _InvalidFunctionError
        self.index += 1
        if symbol == "a":
            return self.accumulator
        if symbol == "(":
            value = self._expression()
            if self._peek() != ")":
                raise _InvalidFunctionError
            self.index += 1
            return value
        if symbol.isdigit():
            return int(symbol)
        raise _InvalidFunctionError


class _InvalidFunctionError(Exception):
    r"""The built function does not parse, so ``u`` leaves the accumulator."""


# : One instant of a run:.
# :.
# : A value, not a record:.
# : than editing the one it was.
# : tuples for the same reason.
# : has pushed, which no loop.
# :.
# : The tokens, the syllable.
# : stay out: CV(N)(C) never.
# : once and handed to the.
type _State = tuple[int, tuple[int, ...], tuple[str, ...], int]


def _popped(deque: tuple[int, ...], *, front: bool) -> tuple[tuple[int, ...], int]:
    r"""Pop one end of the deque, refusing an empty one."""
    if not deque:
        raise HaltError("pop from an empty deque")
    return (deque[1:], deque[0]) if front else (deque[:-1], deque[-1])


def _applied(accumulator: int, function: tuple[str, ...]) -> int:
    r"""Return the function applied to the accumulator, if it parses."""
    try:
        return _Parser(list(function), accumulator).parse()
    except _InvalidFunctionError:
        return accumulator


def _fricative(
    state: _State, token: str, line: str | None, byte: int | None
) -> tuple[_State, str | int | None]:
    r"""Run one I/O command, reporting anything it prints."""
    accumulator, deque, function, pointer = state
    if token == _PRINT_NUM:
        return state, accumulator
    if token == _PRINT_CHAR:
        return state, chr(accumulator % 256)
    if token == _READ_NUM:
        # The accumulator is unsigned,.
        # and an empty line (a bare.
        return (max(_as_int((line or "").strip()), 0), deque, function, pointer), None
    # what is left is ``ʒ``, the.
    return ((byte or 0) % 256, deque, function, pointer), None


def _plosive(state: _State, token: str) -> _State:
    r"""Append to the function, or reset it."""
    accumulator, deque, function, pointer = state
    if token == _CLEAR_FUNCTION:
        return (accumulator, deque, (), pointer)
    if token in _FUNCTION_SYMBOLS:
        return (accumulator, deque, (*function, _FUNCTION_SYMBOLS[token]), pointer)
    deque, value = _popped(deque, front=token == _POP_FRONT_APPEND)
    return (accumulator, deque, (*function, str(value)), pointer)


def _vowel(state: _State, token: str) -> _State:
    r"""Modify the accumulator."""
    accumulator, deque, function, pointer = state
    if token == _INCREMENT:
        accumulator += 1
    elif token == _DECREMENT:
        accumulator = max(accumulator - 1, 0)
    elif token == _SQUARE:
        accumulator *= accumulator
    elif token == _SQRT:
        accumulator = math.isqrt(accumulator)
    else:
        accumulator = _applied(accumulator, function)
    return (accumulator, deque, function, pointer)


def _nasal(state: _State, token: str) -> _State:
    r"""Push to or pop from the deque."""
    accumulator, deque, function, pointer = state
    if token == _PUSH_FRONT:
        return (accumulator, (accumulator, *deque), function, pointer)
    if token == _PUSH_BACK:
        return (accumulator, (*deque, accumulator), function, pointer)
    deque, accumulator = _popped(deque, front=token == _POP_FRONT)
    return (accumulator, deque, function, pointer)


def _approximant(
    state: _State,
    token: str,
    starts: list[int],
    pairs: dict[int, int],
    offsets: dict[int, int],
    end: int,
) -> _State:
    r"""Jump: a goto, a loop test, or a loop end."""
    accumulator, deque, function, pointer = state
    if token == _GOTO:
        # Past the end is a halt, which.
        pointer = offsets.get(accumulator, end)
    elif token == _GOTO_LINE:
        pointer = starts[accumulator] if accumulator < len(starts) else end
    elif token == _WHILE_ZERO:
        # Jumping *past* the ``ʋ``.
        # end would run it and bounce.
        if accumulator == 0:
            pointer = pairs[pointer - 1] + 1
    elif token == _WHILE_NONZERO:
        if accumulator != 0:
            pointer = pairs[pointer - 1] + 1
    else:
        # ``ʋ`` jumps back *to* its.
        pointer = pairs[pointer - 1]
    return (accumulator, deque, function, pointer)


def _advance(
    state: _State,
    token: str,
    starts: list[int],
    pairs: dict[int, int],
    offsets: dict[int, int],
    end: int,
    line: str | None = None,
    byte: int | None = None,
) -> tuple[_State, str | int | None]:
    r"""Execute one command, returning the new state and anything it prints."""
    if token in _FRICATIVES:
        return _fricative(state, token, line, byte)
    if token in _PLOSIVES:
        return _plosive(state, token), None
    if token in _VOWELS:
        return _vowel(state, token), None
    if token in _NASALS:
        return _nasal(state, token), None
    return _approximant(state, token, starts, pairs, offsets, end), None


class _Machine:
    r"""The run state of one CV(N)(C) program, steppable one command at a."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Parse ``code`` into commands and syllables, ready to step."""
        self.tokens = _tokenize(code)
        if not self.tokens:
            raise ValueError("program is empty")
        self.starts = _syllabify(self.tokens)
        self.pairs = _match_loops(self.tokens)
        # ``ɹ`` indexes the source by.
        # codepoint offset begins at is.
        # two offsets and both map to.
        # in the middle of one.
        self.offsets: dict[int, int] = {}
        offset = 0
        for index, token in enumerate(self.tokens):
            for step in range(len(token)):
                self.offsets[offset + step] = index
            offset += len(token)
        self.io = io
        self.accumulator = 0
        self.deque: tuple[int, ...] = ()
        self.function: tuple[str, ...] = ()
        self.pointer = 0

    @property
    def halted(self) -> bool:
        r"""Whether the instruction pointer has run off the end."""
        return self.pointer >= len(self.tokens)

    # The VM's language-shaped.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.pointer

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return [self.accumulator, *self.deque]

    @property
    def stack(self) -> list[object]:
        r"""The stack."""
        return list(self.deque)

    def snapshot(self) -> Hashable:
        r"""Return the complete state, hashable for cycle detection."""
        return (
            self.pointer,
            self.accumulator,
            self.deque,
            self.function,
            self.io.position(),
        )

    def step(self) -> None:
        r"""Execute one command, advancing the pointer."""
        if self.halted:
            return
        token = self.tokens[self.pointer]
        self.pointer += 1

        line = None
        byte = None
        if token == _READ_NUM:
            line = self.io.input_str()
        elif token == _READ_CHAR:
            byte = self.io.input_char()

        state, output = _advance(
            (self.accumulator, self.deque, self.function, self.pointer),
            token,
            self.starts,
            self.pairs,
            self.offsets,
            len(self.tokens),
            line,
            byte,
        )
        self.accumulator, self.deque, self.function, self.pointer = state

        if isinstance(output, int):
            self.io.print_num(output)
        elif output is not None:
            self.io.print_char(output)


def run(code: str, io: IO) -> None:
    r"""Run a CV(N)(C) program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":  # pragma: no cover
    with open(sys.argv[1], encoding="utf-8") as file:
        run(file.read(), IO())
