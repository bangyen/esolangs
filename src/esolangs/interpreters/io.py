r"""Shared interpreter I/O with one cursor for character, token, and line reads.

Character reads return Unicode code points, preserving newlines and unread
text. Numeric reads consume whitespace-delimited integer tokens; string reads
consume one line. Interpreters retain their own cell-width and EOF rules.
Interactive input is line-buffered; ScriptedIO consumes the supplied string
without inserting delimiters. Output is buffered by ScriptedIO.
"""

from __future__ import annotations

import io as _stdlib_io

from esolangs._input import InputSource, read_input
from esolangs.exceptions import ArgumentError, InputExhaustedError
from esolangs.interpreters.source_hints import syntax_error


class IO:
    """Routes interpreter output and input through pluggable primitives.

    Subclasses override :meth:`_read` and :meth:`_write` to change where
    input comes from and where output goes; everything else (the typed
    methods and the newline flag) is shared.
    """

    def __init__(self) -> None:
        """Create an IO with no pending prompt newline."""
        self._newline = False
        self._pending = ""
        self._reads = 0

    def _read(self, prompt: str) -> str:
        return input(prompt)

    def _write(self, value: object) -> None:
        print(value, end="")

    def print_str(self, text: str) -> None:
        r"""Write ``text`` as-is, adding no trailing newline of its own.

        ``_newline`` tracks whether the cursor is mid-line, so that a later
        input prompt knows whether to start with a break.  It is derived
        from the text rather than assumed: ``print_str("a\\n")`` ends a line
        as surely as the old ``print_line("a")`` did, and a prompt after it
        must not insert a second break.
        """
        self._write(text)
        if text:
            self._newline = not text.endswith("\n")

    def print_value(self, value: object) -> None:
        """Write any value the way ``print(value, end="")`` would."""
        self._write(value)
        self._newline = True

    def print_char(self, char: str) -> None:
        """Write a single character, which may itself be a newline."""
        self._write(char)
        if char:
            self._newline = char != "\n"

    def print_num(self, num: int) -> None:
        """Write a number's decimal representation."""
        self._write(num)
        self._newline = True

    # There is deliberately no ``print_line``.  A trailing newline is a
    # choice about a language's output format, not a default: the
    # interpreters that used to reach for it were, in every case, adding a
    # newline that no spec asked for.  Writing ``print_str(text + "\n")``
    # keeps that decision visible at the call site.

    def input_str(self, prompt: str = "Input: ") -> str:
        """Read one line, preserving any text left by character reads."""
        prefix = "\n" if self._newline else ""
        if self._pending:
            value, self._pending = self._pending.rstrip("\n"), ""
        else:
            value = self._read(prefix + prompt)
        self._newline = False
        self._reads += 1
        return value

    def _read_char(self, prompt: str) -> str:
        if not self._pending:
            self._pending = self._read(prompt) + "\n"
        value, self._pending = self._pending[0], self._pending[1:]
        return value

    def input_char(self, prompt: str = "Input: ") -> int:
        """Read the next Unicode character, including newlines."""
        prefix = "\n" if self._newline else ""
        value = self._read_char(prefix + prompt)
        self._newline = False
        self._reads += 1
        return ord(value)

    def _peek_char(self, prompt: str) -> str | None:
        if not self._pending:
            self._pending = self._read(prompt) + "\n"
        return self._pending[0]

    def input_token(self, prompt: str = "Input: ") -> str:
        """Read one whitespace-delimited token, leaving its delimiter unread."""
        prefix = "\n" if self._newline else ""
        next_char = self._peek_char(prefix + prompt)
        while next_char is not None and next_char.isspace():
            self._read_char(prefix + prompt)
            next_char = self._peek_char(prefix + prompt)
        if next_char is None:
            self._read_char(prefix + prompt)
        token = []
        while next_char is not None and not next_char.isspace():
            token.append(self._read_char(prefix + prompt))
            next_char = self._peek_char(prefix + prompt)
        self._newline = False
        self._reads += 1
        return "".join(token)

    def input_num(self, prompt: str = "Input: ") -> int:
        """Read a whitespace-delimited integer from the shared cursor."""
        token = self.input_token(prompt)
        try:
            return int(token)
        except ValueError as exc:
            raise syntax_error(
                f"input must be an integer, got {token!r}",
                "supply a whitespace-separated decimal integer, for example 42",
                error_type=ArgumentError,
            ) from exc

    def input_bit(self, prompt: str = "Input: ") -> int:
        """Read a 0 or 1 character, ignoring surrounding whitespace."""
        value = chr(self.input_char(prompt))
        while value.isspace():
            value = chr(self.input_char(prompt))
        if value not in {"0", "1"}:
            raise syntax_error(
                "input must be a bit",
                ("supply input characters 0 or 1; surrounding whitespace is allowed"),
            )
        return int(value)

    def input_all(self, prompt: str = "Input: ") -> str:
        """Read the remaining character stream through EOF."""
        values = []
        try:
            while self._peek_char(prompt) is not None:
                values.append(self._read_char(prompt))
        except EOFError:
            pass
        self._newline = False
        self._reads += 1
        return "".join(values)

    def position(self) -> int:
        """Report the input cursor, or 0 for a source with no cursor.

        ``ScriptedIO`` overrides this with the character offset;
        an interactive source has no cursor to report, so the base returns
        0.  The state-cycle hang detector snapshots this so a loop that
        keeps reading input is not mistaken for a repeat.
        """
        return 0


class ScriptedIO(IO):
    """An :class:`IO` that reads from a string and captures output.

    Used by :func:`esolangs.run` to drive a program from text, UTF-8 bytes,
    or a readable stream. Streams are consumed once and left open.
    ``_read`` ignores the prompt (matching
    the old patched reader) and raises :class:`EOFError` when input runs
    out; ``_write`` appends to an internal buffer returned by
    :meth:`getvalue`.
    """

    def __init__(self, stdin: InputSource = "") -> None:
        """Snapshot ``stdin`` as text and capture all output internally."""
        super().__init__()
        stdin = read_input(stdin)
        self._supplied = stdin.count("\n") + int(
            bool(stdin) and not stdin.endswith("\n")
        )
        self._source = stdin
        self._offset = 0
        self._reads = 0
        self._line_reads = 0
        self._character_reads = False
        self._past_end = 0
        self._buffer = _stdlib_io.StringIO()

    @property
    def reads(self) -> int:
        """How many successful character, token, line, or whole-stream reads."""
        return self._reads

    @property
    def past_end(self) -> int:
        """How many reads went past the end of the supplied input.

        Counted even though the read raises, because seven languages catch
        that raise and carry on with a value -- and for them this is the
        only record that it happened.  ``reads`` deliberately does not
        include these: it counts successful reads.
        """
        return self._past_end

    @property
    def supplied(self) -> int:
        """How many lines were handed to it.

        Public so a caller can notice the program read fewer than it was
        given.  Only the opposite direction was ever reported, by the
        exception a read past the end raises -- which already carried both
        numbers.
        """
        return self._supplied

    def _exhausted(self, unit: str) -> None:
        self._past_end += 1
        if unit == "line" and self._character_reads:
            unit = "character"
        supplied = self.supplied if unit == "line" else len(self._source)
        reads = self._line_reads if unit == "line" else self._offset
        raise InputExhaustedError(reads, supplied, unit)

    def _read(self, _prompt: str) -> str:
        if self._offset == len(self._source):
            self._exhausted("line")
        end = self._source.find("\n", self._offset)
        if end < 0:
            end = len(self._source)
            stop = end
        else:
            stop = end + 1
        value = self._source[self._offset : end]
        self._offset = stop
        self._line_reads += 1
        return value.removesuffix("\r")

    def _read_char(self, _prompt: str) -> str:
        self._character_reads = True
        if self._offset == len(self._source):
            self._exhausted("character")
        value = self._source[self._offset]
        self._offset += 1
        return value

    def _peek_char(self, _prompt: str) -> str | None:
        if self._offset == len(self._source):
            return None
        return self._source[self._offset]

    def position(self) -> int:
        """Return the character offset shared by line and character reads."""
        return self._offset

    def _write(self, value: object) -> None:
        self._buffer.write(str(value))

    def getvalue(self) -> str:
        """Return everything written so far."""
        return self._buffer.getvalue()
