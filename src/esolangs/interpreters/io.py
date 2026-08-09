"""Shared I/O for interpreters.

Every interpreter routes its output and input through an :class:`IO`
instance instead of calling ``input``/``print`` directly.  This centralizes
the three pieces of boilerplate each interpreter used to repeat:

* the ``print(..., end="")`` call for character output,
* the ``input("\\nInput: "[new:])`` prompt with its leading-newline flag,
* the interaction plumbing, so the library can feed a string as stdin and
  capture output without monkey-patching the builtins.

The concrete source is injected at the low-level seam: the base class reads
with ``input()`` and writes with ``print(..., end="")`` (so direct calls
like ``bf.run(code)`` keep working under the test suite's
``patch("builtins.input")``/``redirect_stdout``), while :class:`ScriptedIO`
overrides those two primitives to consume a provided string and accumulate
output.  Callers select the source by constructing the object, not by
branching on a flag.

The newline flag tracks whether the next input prompt should begin on a
fresh line: it is set to ``True`` after any bare output (so the prompt moves
to its own line) and back to ``False`` after reading (the cursor is already
at the start of a line).  Programs that never print keep the prompt on the
current line.
"""

from __future__ import annotations

import io as _stdlib_io


class IO:
    """Routes interpreter output and input through pluggable primitives.

    Subclasses override :meth:`_read` and :meth:`_write` to change where
    input comes from and where output goes; everything else (the typed
    methods and the newline flag) is shared.
    """

    def __init__(self) -> None:
        self._newline = False

    # -- low-level seam: override in subclasses -----------------------

    def _read(self, prompt: str) -> str:
        return input(prompt)

    def _write(self, value: object) -> None:
        print(value, end="")

    # -- output -------------------------------------------------------

    def print_str(self, text: str) -> None:
        """Write ``text`` without a trailing newline."""
        self._write(text)
        self._newline = True

    def print_value(self, value: object) -> None:
        """Write any value the way ``print(value, end="")`` would."""
        self._write(value)
        self._newline = True

    def print_char(self, char: str) -> None:
        """Write a single character."""
        self._write(char)
        self._newline = True

    def print_num(self, num: int) -> None:
        """Write a number's decimal representation."""
        self._write(num)
        self._newline = True

    def print_line(self, text: str = "") -> None:
        """Write ``text`` followed by a newline."""
        self._write(text + "\n")
        self._newline = False

    # -- input --------------------------------------------------------

    def input_str(self, prompt: str = "Input: ") -> str:
        """Read a whole line of input, returning it without the newline."""
        prefix = "\n" if self._newline else ""
        val = self._read(prefix + prompt)
        self._newline = False
        return val

    def input_char(self, prompt: str = "Input: ") -> int:
        """Read a line and return its first character as a byte value."""
        return ord(self.input_str(prompt)[0])

    def input_num(self, prompt: str = "Input: ") -> int:
        """Read a line and parse it as an integer."""
        return int(self.input_str(prompt))


class ScriptedIO(IO):
    """An :class:`IO` that reads from a string and captures output.

    Used by :func:`esolangs.run` to drive a program from a ``stdin`` string
    without patching the builtins.  ``_read`` ignores the prompt (matching
    the old patched reader) and raises :class:`EOFError` when input runs
    out; ``_write`` appends to an internal buffer returned by
    :meth:`getvalue`.
    """

    def __init__(self, stdin: str = "") -> None:
        super().__init__()
        self._lines = iter(stdin.splitlines())
        self._buffer = _stdlib_io.StringIO()

    def _read(self, prompt: str) -> str:
        try:
            return next(self._lines)
        except StopIteration:
            raise EOFError from None

    def _write(self, value: object) -> None:
        self._buffer.write(str(value))

    def getvalue(self) -> str:
        """Return everything written so far."""
        return self._buffer.getvalue()
