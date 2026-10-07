"""Interpreter for Smu, Zzo38's minimal Smurf over the string stack.

``(...)`` pushes its nested contents; ``=`` pops a name and then a value and
assigns; ``|`` pops a string and pushes its tail then its head (an empty
string is just popped); ``+`` pops two names and pushes the second's value
followed by the top's.  ``=`` and ``+`` with fewer than two strings, and
``|`` on an empty stack, do nothing.  Each run starts by pushing one input
bit (``|`` 0, ``+`` 1, ``=`` at EOF) and ends by popping and outputting a
string, then popping the next one as the program to run; the stack and
variables carry over.  No string left halts.  The preprocessor drops ``&``
comments to end of line and whitespace, then expands macros: a name (digits
then one ASCII letter) opens a definition the first time and closes it the
second; afterwards the name expands.  Other characters are ignored.

Judgment calls:

- An unset variable reads as the empty string.  The wiki cat needs it: at
  EOF it looks up ``==``, never set, and runs the result as an empty
  program, which ends the run with nothing left to execute.
- Bits ride bytes little-endian, as in Boolfuck: each input byte supplies
  eight runs' bits, low bit first, and output bits pack low bit first into
  bytes, a partial byte padded with zeros at halt.  So the wiki cat copies
  bytes.  Input is reduced modulo 256.  EOF is a value, ``=``, never an
  ``EOFError``.
- Output ``=`` ("wait for more input unless EOF") prints nothing: input is
  a stream read one bit per run, so there is nothing to wait for.
- Output of ``(`` or ``)`` is unspecified and raises
  :class:`~esolangs.exceptions.HaltError` before any of the string prints.
- Parentheses "must be nested correctly": an unbalanced source raises
  :class:`ValueError`; an unbalanced string popped as the next program
  raises :class:`~esolangs.exceptions.HaltError` before it runs.
- A second macro name inside a definition raises :class:`ValueError`
  ("you cannot define a macro inside of another macro"), as does a
  definition left open; digits not followed by a letter are ignored.

Cost: each run scans its program once for top-level literals; ``|`` and
``+`` build Python strings, so each costs the length of what it builds.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from esolangs._drive import drive
from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.brackets import unmatched
from esolangs.interpreters.io import IO

#: New program counter, strings popped, strings pushed, and an assignment.
type _Effect = tuple[int, int, tuple[str, ...], tuple[str, str] | None]

_PARENS = re.compile(r"[()]")
#: Commands and macro names; anything else, a lone digit run included, is dropped.
_TOKENS = re.compile(r"[()=|+]|[0-9]*[A-Za-z]")
_BITS = {"|": 0, "+": 1}


def preprocess(source: str) -> str:
    """Return ``source`` with comments, whitespace and macros expanded away."""
    text = "".join(re.sub(r"&[^\n]*", "", source).split())
    macros: dict[str, str] = {}
    out: list[str] = []
    body: list[str] = []
    defining = ""
    for token in _TOKENS.finditer(text):
        name = token.group()
        if name in "()=|+":
            (body if defining else out).append(name)
            continue
        if name in macros:
            (body if defining else out).append(macros[name])
        elif name == defining:
            macros[name], body, defining = "".join(body), [], ""
        elif defining:
            raise ValueError(f"Smu macro {name!r} defined inside macro {defining!r}")
        else:
            defining = name
    if defining:
        raise ValueError(f"Smu macro {defining!r} is never closed")
    return "".join(out)


def literals(code: str) -> dict[int, int]:
    """Map each top-level ``(`` to its ``)``; raise ValueError if unbalanced."""
    closes: dict[int, int] = {}
    depth = start = 0
    for match in _PARENS.finditer(code):
        at = match.start()
        if code[at] == "(":
            if not depth:
                start = at
            depth += 1
        elif not depth:
            raise unmatched(")", at, "open the string with '('")
        else:
            depth -= 1
            if not depth:
                closes[start] = at
    if depth:
        raise unmatched("(", start, "close the string with ')'")
    return closes


def _advance(
    code: str,
    pc: int,
    closes: Mapping[int, int],
    stack: Sequence[str],
    values: Mapping[str, str],
) -> _Effect:
    """Return one command's effect on the stack and variables; pure."""
    command = code[pc]
    if command == "(":
        end = closes[pc]
        return end + 1, 0, (code[pc + 1 : end],), None
    if command == "|":
        if not stack:
            return pc + 1, 0, (), None
        text = stack[-1]
        return pc + 1, 1, (text[1:], text[0]) if text else (), None
    if len(stack) < 2:
        return pc + 1, 0, (), None
    if command == "=":
        return pc + 1, 2, (), (stack[-1], stack[-2])
    joined = values.get(stack[-2], "") + values.get(stack[-1], "")
    return pc + 1, 2, (joined,), None


class _Machine:
    """One run's program and counter, the shared stack and variables, bit buffers."""

    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.code = preprocess(code)
        self.closes = literals(self.code)
        self.pc = 0
        self.fresh = True  # the run's input bit is not pushed yet
        self.done = False
        self._stack: list[str] = []
        self.values: dict[str, str] = {}
        self.incoming = self.remaining = self.outgoing = self.used = 0

    @property
    def halted(self) -> bool:
        return self.done

    @property
    def ip(self) -> int:
        return self.pc

    @property
    def stack(self) -> list[object]:
        return list(self._stack)

    def snapshot(self) -> tuple[object, ...]:
        return (
            self.code,
            self.pc,
            self.fresh,
            self.done,
            tuple(self._stack),
            frozenset(self.values.items()),
            self.incoming,
            self.remaining,
            self.outgoing,
            self.used,
            self.io.position(),
        )

    def _read_bit(self) -> str:
        if not self.remaining:
            try:
                self.incoming = self.io.input_char() % 256
            except EOFError:
                return "="
            self.remaining = 8
        bit = self.incoming & 1
        self.incoming >>= 1
        self.remaining -= 1
        return "|+"[bit]

    def _write(self, text: str) -> None:
        if not set(text) <= {"|", "+", "="}:
            raise HaltError(
                f"Smu cannot output {text!r}",
                hint="output strings may hold only | (0), + (1) and =",
            )
        for char in text:
            if char in _BITS:
                self.outgoing |= _BITS[char] << self.used
                self.used += 1
                if self.used == 8:
                    self.io.print_char(chr(self.outgoing))
                    self.outgoing = self.used = 0

    def _end_run(self) -> None:
        """Output the top string and load the next one, or halt."""
        if self._stack:
            self._write(self._stack.pop())
        if not self._stack:
            if self.used:
                self.io.print_char(chr(self.outgoing))
                self.outgoing = self.used = 0
            self.done = True
            return
        code = self._stack.pop()
        try:
            closes = literals(code)
        except ValueError as error:
            raise HaltError(f"Smu program {code!r} is unbalanced: {error}") from None
        self.code, self.closes, self.pc, self.fresh = code, closes, 0, True

    def step(self) -> None:
        if self.done:
            return
        if self.fresh:
            self._stack.append(self._read_bit())
            self.fresh = False
        elif self.pc < len(self.code):
            self.pc, pops, pushes, assignment = _advance(
                self.code, self.pc, self.closes, self._stack, self.values
            )
            if pops:
                del self._stack[-pops:]
            self._stack.extend(pushes)
            if assignment is not None:
                self.values[assignment[0]] = assignment[1]
        else:
            self._end_run()


def run(code: str, io: IO) -> None:
    """Execute a Smu program, one input bit per run."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
