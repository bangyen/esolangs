"""Interpreter for CV(N)(C).

A pronounceable language whose source is a string of IPA symbols parsed as
syllables.  Memory is an unbounded unsigned integer *accumulator*, a
*deque* of unbounded unsigned integers, and a *function* from unbounded
unsigned integers to unbounded unsigned integers that the program builds up
symbol by symbol and applies on demand.

The syllable structure is CV(N)(C): a non-nasal consonant, a vowel, an
optional nasal, and an optional final non-nasal consonant.  Parsing is only
about *validity* -- every symbol is a command in its own right and they run
in written order -- so ``suŋs`` is one syllable running four commands and
``susŋ`` is not a program at all.

The commands, by class:

- **Fricatives do I/O.**  ``θ`` prints the accumulator as an integer, ``f``
  prints it modulo 256 as an ASCII character, ``s`` reads an integer into
  it, and ``ʒ`` reads an ASCII character (modulo 256) into it.
- **Plosives build the function.**  ``d`` appends ``a`` (a reference to the
  accumulator), ``b`` ``+``, ``t`` ``-``, ``ɡ`` ``×``, ``q`` ``÷``, ``ʔ``
  ``(``, ``ʡ`` ``)``; ``p`` and ``k`` pop the front and back of the deque
  and append the popped number as a literal; ``c`` resets the function to
  its empty default.
- **Approximants do control flow.**  ``ɰ̊`` and ``ɰ`` open a while loop,
  jumping past the matching ``ʋ`` when the accumulator is zero and nonzero
  respectively, and ``ʋ`` jumps back to its opener.  ``ɹ`` and ``j`` are
  computed gotos, to the accumulator-th character and the accumulator-th
  syllable of the source.
- **Vowels modify the accumulator**: ``i`` increments, ``ə`` decrements
  (flooring at zero), ``æ`` squares, ``o`` takes the integer square root,
  and ``u`` replaces the accumulator with the function applied to it.
- **Nasals work the deque**: ``m`` and ``n`` push the accumulator to the
  front and back, ``ŋ`` and ``ɲ`` pop the front and back into it.

Decisions for gaps in the wiki spec (documented):

- **Syllabification is greedy, and a final consonant is taken only when it
  cannot begin the next syllable.**  The spec gives the structure and two
  examples of what is and is not a program, but not the rule that splits a
  consonant run.  Since every syllable needs a vowel, a consonant followed
  by a vowel must be an onset, and one that is not must be a coda -- which
  is forced, not chosen, and parses all four of the page's examples.  The
  page's own counterexample ``susŋ`` fails it: the nasal is stranded with
  no vowel, matching the spec's "can't be broken up into valid syllables".
- **``ɰ̊`` is a single command spelled with two codepoints** (``ɰ`` plus
  U+030A COMBINING RING ABOVE), so the tokenizer joins them.  A combining
  ring on anything else, and any symbol outside the command set, makes the
  program malformed.
- **``ɹ`` counts codepoints, not commands.**  The spec says "character",
  and the source is a string of characters; the alternative (counting
  tokens) would make ``ɰ̊`` occupy one position and silently disagree with
  the text the programmer wrote.  A goto to a position that is not the
  start of a syllable is still legal -- execution simply resumes at that
  command -- but landing on the ring of a ``ɰ̊`` resumes at the ``ɰ̊``
  itself, since there is no command to run in the middle of one.
- **A goto past the end of the source halts**, which is what running off
  the end does anyway; the same is true of ``j`` past the last syllable.
- **A loop opener jumps *past* its ``ʋ``, not onto it.**  The spec says
  only "jump to the matching /ʋ/", and landing *on* the loop end would run
  it, sending control straight back to the test it just failed -- an
  infinite loop for the very case the test was meant to escape.  The
  page's truth machine settles it: on input 0 the ``ɰ̊`` must skip the body
  and reach the end of the program, printing ``0`` once and halting, which
  it only does if the jump clears the ``ʋ``.  ``ʋ`` itself jumps back
  *onto* its opener, which re-tests the condition.
- **The function is applied left to right with ``×`` and ``÷`` binding
  tighter than ``+`` and ``-``**, the ordinary arithmetic reading of the
  symbols the spec names.  The wiki's Hello, world! example applies only
  ``a``, ``a×a``, ``a×a+a``, ``a×a+a+a-a`` and ``a×a+(a)``, which pin the
  precedence but never divide, so division's rounding is decided here:
  ``÷`` floors, the only choice that keeps the accumulator an integer.
- **An invalid function does nothing**, as the spec says for ``u``:
  "if the function is valid, else do nothing".  *Valid* is defined by the
  parser -- the token string must parse as a complete expression -- so an
  empty function, unbalanced parentheses, a trailing operator, and two
  adjacent operands are all simply inert.  Division by zero is a runtime
  *operation* rather than a malformed function, so it raises
  :class:`~esolangs.exceptions.HaltError`.
- **The accumulator is unsigned**, so a subtraction that would go below
  zero floors at zero, matching ``ə``'s explicit "decrement if it is
  greater than zero" and the spec's "unbounded *unsigned* integer" memory.
  The same floor applies to a negative integer read by ``s``.
- **Popping an empty deque** (``p``, ``k``, ``ŋ``, ``ɲ``) is an invalid
  runtime operation and raises :class:`~esolangs.exceptions.HaltError`.
- **Unbalanced loops** -- a ``ʋ`` with no opener, or an opener with no
  ``ʋ`` -- make the program malformed (:class:`ValueError`), as does a
  source that does not syllabify or an empty program.
- **``s`` takes an unparseable line as zero.**  An empty line (a bare
  Enter) and a line of junk are both input the user can legitimately type,
  not invalid *operations* the way popping an empty deque is, so neither
  raises.  **EOF** is the separate case and propagates as
  :class:`EOFError` from the IO seam, the repo-wide convention; ``ʒ`` on an
  empty line reads the newline that ended it.
- **The multiplication plosive is accepted spelled either way.**  The
  command table gives it as ``ɡ`` (U+0261 LATIN SMALL LETTER SCRIPT G) but
  the page's own Hello, world! writes a plain ASCII ``g`` seven times and
  never uses U+0261, so a reader who copies either the table or the example
  gets a program that runs.  The ASCII form folds to the IPA one during
  tokenization.
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
    """Parse an input line as an integer, taking anything else as zero.

    An empty line is a bare Enter and a line of junk is what the fuzz suite
    feeds; neither is an *invalid operation* the way popping an empty deque
    is, so both read as 0 rather than raising.  Running out of input is the
    separate case and still raises :class:`EOFError` from the IO seam.
    """
    try:
        return int(line)
    except ValueError:
        return 0


def _tokenize(code: str) -> list[str]:
    """Split ``code`` into commands, joining ``ɰ`` with its combining ring.

    Every other command is one codepoint.  A ring that does not follow
    ``ɰ``, and any symbol that is not a command, makes the program
    malformed -- the fuzz suite feeds exactly that.
    """
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
    """Return the token index each syllable starts at, or reject the source.

    A syllable is a consonant, a vowel, an optional nasal, and an optional
    final consonant.  The final consonant is taken only when it cannot be
    the next syllable's onset -- that is, when no vowel follows it -- which
    is forced by every syllable needing a vowel of its own.
    """
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

    The function is a string over ``a``, the four operators and the two
    parentheses, so this is the grammar of ordinary arithmetic with ``a``
    for the only atom and a number literal where ``p``/``k`` popped one.
    Parsing and evaluating together is enough: the accumulator is fixed for
    the duration of one application, so there is no tree to keep.

    A parse failure means the function is *invalid* in the spec's sense,
    which ``u`` treats as doing nothing, so the error type is private and
    :func:`_apply` converts it to "leave the accumulator alone".
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
        self.deque: list[int] = []
        self.function: list[str] = []
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
        """Return the complete state, hashable for cycle detection.

        Carries the pointer, the accumulator, the deque, the function under
        construction, and the input cursor -- everything a later step can
        read.  Nothing else varies between two runs of the same program, so
        a repeat here is a real cycle.
        """
        return (
            self.pointer,
            self.accumulator,
            tuple(self.deque),
            tuple(self.function),
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one command, advancing the pointer."""
        if self.halted:
            return
        token = self.tokens[self.pointer]
        self.pointer += 1
        if token in _FRICATIVES:
            self._fricative(token)
        elif token in _PLOSIVES:
            self._plosive(token)
        elif token in _VOWELS:
            self._vowel(token)
        elif token in _NASALS:
            self._nasal(token)
        else:
            self._approximant(token)

    def _fricative(self, token: str) -> None:
        """Run one I/O command."""
        if token == _PRINT_NUM:
            self.io.print_num(self.accumulator)
        elif token == _PRINT_CHAR:
            self.io.print_char(chr(self.accumulator % 256))
        elif token == _READ_NUM:
            # The accumulator is unsigned, so a negative line floors at zero,
            # and an empty line (a bare Enter) reads as 0 rather than raising.
            line = self.io.input_str().strip()
            self.accumulator = max(_as_int(line), 0)
        else:
            self.accumulator = self.io.input_char() % 256

    def _plosive(self, token: str) -> None:
        """Append to the function, or reset it."""
        if token == _CLEAR_FUNCTION:
            self.function = []
        elif token in _FUNCTION_SYMBOLS:
            self.function.append(_FUNCTION_SYMBOLS[token])
        else:
            self.function.append(str(self._pop(front=token == _POP_FRONT_APPEND)))

    def _vowel(self, token: str) -> None:
        """Modify the accumulator."""
        if token == _INCREMENT:
            self.accumulator += 1
        elif token == _DECREMENT:
            self.accumulator = max(self.accumulator - 1, 0)
        elif token == _SQUARE:
            self.accumulator *= self.accumulator
        elif token == _SQRT:
            self.accumulator = math.isqrt(self.accumulator)
        else:
            self._apply()

    def _nasal(self, token: str) -> None:
        """Push to or pop from the deque."""
        if token == _PUSH_FRONT:
            self.deque.insert(0, self.accumulator)
        elif token == _PUSH_BACK:
            self.deque.append(self.accumulator)
        else:
            self.accumulator = self._pop(front=token == _POP_FRONT)

    def _approximant(self, token: str) -> None:
        """Jump: a goto, a loop test, or a loop end."""
        if token == _GOTO:
            # Past the end is a halt, which running off the end already is.
            self.pointer = self.offsets.get(self.accumulator, len(self.tokens))
        elif token == _GOTO_LINE:
            self.pointer = (
                self.starts[self.accumulator]
                if self.accumulator < len(self.starts)
                else len(self.tokens)
            )
        elif token == _WHILE_ZERO:
            # Jumping *past* the ``ʋ`` rather than onto it: landing on the
            # loop end would run it and bounce straight back to the test.
            if self.accumulator == 0:
                self.pointer = self.pairs[self.pointer - 1] + 1
        elif token == _WHILE_NONZERO:
            if self.accumulator != 0:
                self.pointer = self.pairs[self.pointer - 1] + 1
        else:
            # ``ʋ`` jumps back *to* its opener, which re-tests the condition.
            self.pointer = self.pairs[self.pointer - 1]

    def _pop(self, *, front: bool) -> int:
        """Pop one end of the deque, refusing an empty one."""
        if not self.deque:
            raise HaltError("pop from an empty deque")
        return self.deque.pop(0) if front else self.deque.pop()

    def _apply(self) -> None:
        """Set the accumulator to the function applied to it, if it parses."""
        try:
            self.accumulator = _Parser(self.function, self.accumulator).parse()
        except _InvalidFunctionError:
            return


def run(code: str, io: IO) -> None:
    """Run a CV(N)(C) program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":  # pragma: no cover
    with open(sys.argv[1], encoding="utf-8") as file:
        run(file.read(), IO())
