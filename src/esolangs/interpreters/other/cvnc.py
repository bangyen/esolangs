"""Interpreter for CV(N)(C).

Source is IPA symbols parsed as CV(N)(C) syllables; parsing is only about
validity, since every symbol is a command run in written order.  Memory
is an unsigned *accumulator*, a *deque*, and a *function* built symbol by
symbol.  Fricatives do I/O (``θ`` int, ``f`` char, ``s`` read int, ``ʒ``
read char); plosives build the function (``d`` ``a``, ``b`` ``+``, ``t``
``-``, ``ɡ`` ``×``, ``q`` ``÷``, ``ʔ`` ``(``, ``ʡ`` ``)``, ``p``/``k``
pop a literal from front/back, ``c`` resets); approximants are control
flow (``ɰ̊``/``ɰ`` loop while zero/nonzero to ``ʋ``, ``ɹ``/``j`` goto
character/syllable); vowels modify the accumulator (``i`` ++, ``ə`` --
floored, ``æ`` square, ``o`` isqrt, ``u`` apply); nasals work the deque
(``m``/``n`` push front/back, ``ŋ``/``ɲ`` pop).

Gaps decided: syllabification is greedy and takes a coda only when no
vowel follows (forced; parses all four wiki examples and rejects
``susŋ``); ``ɰ̊`` is two codepoints joined by the tokenizer; ``ɹ``
counts codepoints, landing on the ring resumes at the ``ɰ̊``; a goto past
the end halts; an opener jumps *past* its ``ʋ`` (the truth machine on
input 0 requires it) and ``ʋ`` jumps onto its opener; ``×``/``÷`` bind
tighter than ``+``/``-`` (pinned by the Hello, world! example) and ``÷``
floors; an invalid function is inert but division by zero raises
:class:`~esolangs.exceptions.HaltError`, as does popping an empty deque;
subtraction and ``s`` floor at zero; unbalanced loops, an empty program
or an unsyllabifiable source raise :class:`ValueError`; ``s`` reads junk
as zero, while EOF raises :class:`EOFError`; ASCII ``g`` folds to ``ɡ``
because the wiki's example uses it.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Hashable

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

__all__ = ["run"]

# U+030A COMBINING RING ABOVE, the voicelessness diacritic that turns ``ɰ``
# into ``ɰ̊``.  It is the only multi-codepoint command, so the tokenizer
# joins exactly this pair and rejects the ring anywhere else.
_RING = "̊"
_WHILE_ZERO = "ɰ" + _RING

# The consonant classes.  Nasals are separate because the syllable
# structure treats them as a distinct slot: CV(N)(C) admits a nasal only in
# third position, so ``ŋ`` can never be an onset and ``s`` can never be the
# N of a syllable.
_FRICATIVES = frozenset("θfsʒ")
# ``ɡ`` is U+0261 LATIN SMALL LETTER SCRIPT G, which is how the command
# table spells the multiplication plosive -- but the page's own Hello,
# world! writes it as the ASCII ``g`` seven times and never uses U+0261.
# Both are accepted, and the ASCII form is folded to the IPA one at
# tokenization so nothing downstream has to know there were two spellings.
_SCRIPT_G = "ɡ"
_PLOSIVES = frozenset("pkdbt" + _SCRIPT_G + "qʔʡc")
_APPROXIMANTS = frozenset({"ɹ", "j", _WHILE_ZERO, "ɰ", "ʋ"})
_CONSONANTS = _FRICATIVES | _PLOSIVES | _APPROXIMANTS
_NASALS = frozenset("mnŋɲ")
_VOWELS = frozenset("iəæou")

# The function's own alphabet, keyed by the plosive that appends each one.
# ``p`` and ``k`` are absent: they append a *number* popped from the deque,
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

# The individual commands the dispatch tests by name, so each branch body
# reads as the operation it performs rather than as a comparison against a
# bare IPA character.  The class frozensets above still spell their members
# directly: they are membership tests over a whole class, not the per-command
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
    """Parse an input line as an integer, taking anything else as zero."""
    try:
        return int(line)
    except ValueError:
        return 0


def _tokenize(code: str) -> list[str]:
    """Split ``code`` into commands, joining ``ɰ`` with its combining ring."""
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
    """Return the token index each syllable starts at, or reject the source."""
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
        # A consonant here closes this syllable only if it has no vowel to
        # open the next one with.
        if (
            index < len(tokens)
            and tokens[index] in _CONSONANTS
            and (index + 1 >= len(tokens) or tokens[index + 1] not in _VOWELS)
        ):
            index += 1
    return starts


def _match_loops(tokens: list[str]) -> dict[int, int]:
    """Pair every loop opener with its ``ʋ``, rejecting an unbalanced source."""
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
    """A recursive-descent reader for the function the program has built.

    Parses and evaluates together since the accumulator is fixed for one
    application.  A parse failure is an *invalid* function, which
    :func:`_apply` turns into "leave the accumulator alone".
    """

    def __init__(self, symbols: list[str], accumulator: int) -> None:
        """Read ``symbols``, substituting ``accumulator`` for every ``a``."""
        self.symbols = symbols
        self.accumulator = accumulator
        self.index = 0

    def _peek(self) -> str | None:
        return self.symbols[self.index] if self.index < len(self.symbols) else None

    def parse(self) -> int:
        """Evaluate the whole function, rejecting anything left over."""
        value = self._expression()
        if self.index != len(self.symbols):
            raise _InvalidFunctionError
        return value

    def _expression(self) -> int:
        """Evaluate a sum of terms, left to right."""
        value = self._term()
        while (symbol := self._peek()) in _ADDITIVE:
            self.index += 1
            right = self._term()
            # The accumulator is unsigned, so a subtraction floors at zero
            # rather than going negative.
            value = value + right if symbol == "+" else max(value - right, 0)
        return value

    def _term(self) -> int:
        """Evaluate a product of factors, left to right."""
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
        """Evaluate ``a``, a literal, or a parenthesized expression."""
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
    """The built function does not parse, so ``u`` leaves the accumulator."""


#: One instant of a run: ``(accumulator, deque, function, pointer)``.
#:
#: A value, not a record: every handler below returns a new state rather
#: than editing the one it was handed.  The deque and the function are
#: tuples for the same reason -- and both are bounded by what the program
#: has pushed, which no loop grows without also growing the accumulator.
#:
#: The tokens, the syllable starts, the loop pairs and the offset table
#: stay out: CV(N)(C) never rewrites its own source, so they are computed
#: once and handed to the transition.
type _State = tuple[int, tuple[int, ...], tuple[str, ...], int]


def _popped(deque: tuple[int, ...], *, front: bool) -> tuple[tuple[int, ...], int]:
    """Pop one end of the deque, refusing an empty one."""
    if not deque:
        raise HaltError("pop from an empty deque")
    return (deque[1:], deque[0]) if front else (deque[:-1], deque[-1])


def _applied(accumulator: int, function: tuple[str, ...]) -> int:
    """Return the function applied to the accumulator, if it parses."""
    try:
        return _Parser(list(function), accumulator).parse()
    except _InvalidFunctionError:
        return accumulator


def _fricative(
    state: _State, token: str, line: str | None, byte: int | None
) -> tuple[_State, str | int | None]:
    """Run one I/O command, reporting anything it prints."""
    accumulator, deque, function, pointer = state
    if token == _PRINT_NUM:
        return state, accumulator
    if token == _PRINT_CHAR:
        return state, chr(accumulator % 256)
    if token == _READ_NUM:
        # The accumulator is unsigned, so a negative line floors at zero,
        # and an empty line (a bare Enter) reads as 0 rather than raising.
        return (max(_as_int((line or "").strip()), 0), deque, function, pointer), None
    # what is left is ``ʒ``, the character read
    return ((byte or 0) % 256, deque, function, pointer), None


def _plosive(state: _State, token: str) -> _State:
    """Append to the function, or reset it."""
    accumulator, deque, function, pointer = state
    if token == _CLEAR_FUNCTION:
        return (accumulator, deque, (), pointer)
    if token in _FUNCTION_SYMBOLS:
        return (accumulator, deque, (*function, _FUNCTION_SYMBOLS[token]), pointer)
    deque, value = _popped(deque, front=token == _POP_FRONT_APPEND)
    return (accumulator, deque, (*function, str(value)), pointer)


def _vowel(state: _State, token: str) -> _State:
    """Modify the accumulator."""
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
    """Push to or pop from the deque."""
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
    """Jump: a goto, a loop test, or a loop end."""
    accumulator, deque, function, pointer = state
    if token == _GOTO:
        # Past the end is a halt, which running off the end already is.
        pointer = offsets.get(accumulator, end)
    elif token == _GOTO_LINE:
        pointer = starts[accumulator] if accumulator < len(starts) else end
    elif token == _WHILE_ZERO:
        # Jumping *past* the ``ʋ`` rather than onto it: landing on the loop
        # end would run it and bounce straight back to the test.
        if accumulator == 0:
            pointer = pairs[pointer - 1] + 1
    elif token == _WHILE_NONZERO:
        if accumulator != 0:
            pointer = pairs[pointer - 1] + 1
    else:
        # ``ʋ`` jumps back *to* its opener, which re-tests the condition.
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
    """Execute one command, returning the new state and anything it prints.

    Pure.  Reads arrive as ``line``/``byte``; prints are reported as int
    (``θ``) or str (``f``) so the shell can pick the port.  The pointer is
    already past the token, so loop arms read ``pointer - 1``.
    """
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
    """The run state of one CV(N)(C) program, steppable one command at a time."""

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` into commands and syllables, ready to step."""
        self.tokens = _tokenize(code)
        if not self.tokens:
            raise ValueError("program is empty")
        self.starts = _syllabify(self.tokens)
        self.pairs = _match_loops(self.tokens)
        # ``ɹ`` indexes the source by codepoint, so the token that each
        # codepoint offset begins at is precomputed once.  A ``ɰ̊`` occupies
        # two offsets and both map to it: there is no command to resume at
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
        """Whether the instruction pointer has run off the end."""
        return self.pointer >= len(self.tokens)

    # The VM's language-shaped view: Accumulator and deque; ip is the command cursor.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.pointer

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [self.accumulator, *self.deque]

    @property
    def stack(self) -> list[object]:
        """The stack."""
        return list(self.deque)

    def snapshot(self) -> Hashable:
        """Return the complete state, hashable for cycle detection."""
        return (
            self.pointer,
            self.accumulator,
            self.deque,
            self.function,
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one command, advancing the pointer.

        Input is taken before the transition; the reported print goes
        through ``print_num`` or ``print_char`` by type.
        """
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
    """Run a CV(N)(C) program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":  # pragma: no cover
    with open(sys.argv[1], encoding="utf-8") as file:
        run(file.read(), IO())
