"""Interpreter for Unary.

Count zero digits, remove the leading binary 1, and decode 3-bit commands
in > < + - . , [ ] order. Whitespace is ignored, as in the wiki's formatted
example. Empty source halts, though no program encodes to it ("the most
significant bit is always 1"); one zero encodes empty Brainfuck. The
unspecified Brainfuck dialect follows this repo: 8-bit wrapping cells, a tape
growing in both directions.

Input/output:
    Character I/O as Brainfuck.  ``,`` at EOF stores zero, as in the wiki's
    cat example.

Errors:
    ProgramError: a symbol other than zero or whitespace; an incomplete
        3-bit triple; unmatched brackets.
"""

from collections.abc import Mapping
from typing import Any

from esolangs.compressed import CompressedText
from esolangs.languages.brainfuck.interpreter import _Machine as _BFMachine
from esolangs.languages.brainfuck.interpreter import _State as _BFState
from esolangs.languages.brainfuck.interpreter import _written
from esolangs.languages.unary.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._source import ProgramSource, compressed_text_source
from esolangs.runtime.brackets import BracketProgram
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error


def _at_eof(state: _BFState) -> _BFState:
    """Return the comma successor with Unary's zero EOF value."""
    ind, ptr, tape = state
    return ind + 1, ptr, _written(tape, ptr, 0)


def decode(code: str | CompressedText) -> str:
    """Return decoded Brainfuck, rejecting nonzero symbols and partial triples."""
    count = 0
    chunks = code.chunks() if isinstance(code, CompressedText) else (code,)
    for chunk in chunks:
        if chunk.replace("0", "").strip():
            raise syntax_error(
                "Unary source must contain only zeros and whitespace",
                "write only 0 characters, with optional whitespace",
            )
        count += chunk.count("0")
    if not count:
        return ""
    bits = count.bit_length() - 1
    if bits % 3:
        raise syntax_error(
            "Unary encoding has an incomplete 3-bit command",
            (
                "choose a zero count whose binary encoding after the "
                "leading 1 contains complete three-bit commands"
            ),
        )
    return "".join(
        "><+-.,[]"[(count >> shift) & 7] for shift in range(bits - 3, -1, -3)
    )


class _Machine(_BFMachine):
    """Decode Unary, then run it as Brainfuck with zero-valued EOF."""

    #: The zero is a value: an underfed run finishes on another row.  The
    #: census missed it because a termination answer has no output to read.
    eof_is_a_value = True

    def __init__(self, code: str | CompressedText | BracketProgram, io: IO) -> None:
        super().__init__(code if isinstance(code, BracketProgram) else decode(code), io)

    def step(self) -> None:
        try:
            super().step()
        except EOFError:
            # Only comma reads input; it has no jump and replaces the cell.
            self.state = _at_eof(self.state)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain decoded commands and loop partners without expanding source."""
    if not isinstance(source, (str, CompressedText)):
        raise TypeError("unary machines require text or compressed source")
    if options:
        raise TypeError("unary machines accept no runtime options")
    program = BracketProgram.parse(decode(source))
    return RuntimePlan(lambda io: _Machine(program, io), lambda io: _drive(program, io))


def _drive(code: str | CompressedText | BracketProgram, io: IO) -> CompletionReport:
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def _execute(code: str | CompressedText | ProgramSource, io: IO) -> CompletionReport:
    """Decode Unary and run its Brainfuck program."""
    return _drive(compressed_text_source(code), io)


def run(code: str | CompressedText | ProgramSource, io: IO) -> None:
    """Decode Unary and run its Brainfuck program."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run, loader=compressed_text_source)
