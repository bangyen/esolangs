"""Interpreter for Unary.

Count zero digits, remove the leading binary 1, and decode 3-bit commands
in > < + - . , [ ] order. Whitespace is ignored, as in the wiki's formatted
example. Empty source halts, though no program encodes to it ("the most
significant bit is always 1"); one zero encodes empty Brainfuck. Other symbols,
incomplete triples and unmatched brackets raise ValueError. The unspecified
Brainfuck dialect follows this repo: 8-bit wrapping cells, a tape growing in
both directions. Exhausted character input stores zero, as in the
wiki's cat example.
"""

from esolangs.compressed import CompressedText
from esolangs.languages.brainfuck.interpreter import _Machine as _BFMachine
from esolangs.languages.brainfuck.interpreter import _State as _BFState
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._source import ProgramSource, _read_container, text_source
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error


def _at_eof(state: _BFState) -> _BFState:
    """Return the comma successor with Unary's zero EOF value."""
    ind, ptr, tape, _acc, _dirty = state
    return ind + 1, ptr, tape, 0, True


def load_source(source: ProgramSource) -> str | CompressedText:
    """Keep gzip source compressed; accept the ordinary text containers too."""
    value, _path = _read_container(source)
    if isinstance(value, CompressedText):
        return value
    if isinstance(value, bytes) and value.startswith(b"\x1f\x8b"):
        return CompressedText(value)
    return text_source(value)


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

    def __init__(self, code: str | CompressedText, io: IO) -> None:
        super().__init__(decode(code), io)

    def step(self) -> None:
        try:
            super().step()
        except EOFError:
            # Only comma reads input; it has no jump and replaces the cell.
            self.state = _at_eof(self.state)


def run(code: str | CompressedText | ProgramSource, io: IO) -> None:
    """Decode Unary and run its Brainfuck program."""
    drive(_Machine(load_source(code), io))


if __name__ == "__main__":
    script_main(run)
