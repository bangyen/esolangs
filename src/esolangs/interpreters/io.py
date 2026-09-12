r"""Shared I/O for interpreters."""

from __future__ import annotations

import io as _stdlib_io

from esolangs.exceptions import InputExhaustedError


class IO:
    r"""Routes interpreter output and input through pluggable primitives."""

    def __init__(self) -> None:
        r"""Create an IO with no pending prompt newline."""
        self._newline = False

    # -- low-level seam: override.

    def _read(self, prompt: str) -> str:
        return input(prompt)

    def _write(self, value: object) -> None:
        print(value, end="")

    # -- output.

    def print_str(self, text: str) -> None:
        r"""Write ``text`` as-is, adding no trailing newline of its own."""
        self._write(text)
        if text:
            self._newline = not text.endswith("\n")

    def print_value(self, value: object) -> None:
        r"""Write any value the way ``print(value, end="")`` would."""
        self._write(value)
        self._newline = True

    def print_char(self, char: str) -> None:
        r"""Write a single character, which may itself be a newline."""
        self._write(char)
        if char:
            self._newline = char != "\n"

    def print_num(self, num: int) -> None:
        r"""Write a number's decimal representation."""
        self._write(num)
        self._newline = True

    # There is deliberately no.
    # choice about a language's.
    # interpreters that used to.
    # newline that no spec asked.
    # keeps that decision visible.

    # -- input.

    def input_str(self, prompt: str = "Input: ") -> str:
        r"""Read a whole line of input, returning it without the newline."""
        prefix = "\n" if self._newline else ""
        val = self._read(prefix + prompt)
        self._newline = False
        return val

    def input_char(self, prompt: str = "Input: ") -> int:
        r"""Read a line and return its first character as a byte value."""
        line = self.input_str(prompt)
        return ord(line[0]) if line else 0

    def input_num(self, prompt: str = "Input: ") -> int:
        r"""Read a line and parse it as an integer."""
        return int(self.input_str(prompt))

    def position(self) -> int:
        r"""Report the input cursor, or 0 for a source with no cursor."""
        return 0


class ScriptedIO(IO):
    r"""An :class:`IO` that reads from a string and captures output."""

    def __init__(self, stdin: str = "") -> None:
        r"""Read input from ``stdin`` and capture all output internally."""
        super().__init__()
        self._supplied = stdin.splitlines()
        self._lines = iter(self._supplied)
        self._reads = 0
        self._past_end = 0
        self._buffer = _stdlib_io.StringIO()

    @property
    def reads(self) -> int:
        r"""How many lines the program has taken so far."""
        return self._reads

    @property
    def past_end(self) -> int:
        r"""How many reads went past the end of the supplied input."""
        return self._past_end

    @property
    def supplied(self) -> int:
        r"""How many lines were handed to it."""
        return len(self._supplied)

    def _read(self, _prompt: str) -> str:
        try:
            value = next(self._lines)
        except StopIteration:
            # An InputExhaustedError *is*.
            # convention every interpreter.
            # loop detects -- is unchanged.
            # a bare EOFError() reaches the.
            # which cannot say that the.
            # caller passed, or how much it.
            self._past_end += 1
            raise InputExhaustedError(self._reads, len(self._supplied)) from None
        self._reads += 1
        return value

    def position(self) -> int:
        r"""Report the number of input lines consumed so far."""
        return self._reads

    def _write(self, value: object) -> None:
        self._buffer.write(str(value))

    def getvalue(self) -> str:
        r"""Return everything written so far."""
        return self._buffer.getvalue()
