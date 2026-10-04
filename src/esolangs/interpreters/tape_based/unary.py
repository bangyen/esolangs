"""Interpreter for Unary.

Count zero digits, remove the leading binary 1, and decode 3-bit commands
in > < + - . , [ ] order. Whitespace is ignored, as in the wiki's formatted
example. Empty source halts; one zero encodes empty Brainfuck. Other symbols,
incomplete triples and unmatched brackets raise ValueError. The unspecified
Brainfuck dialect follows this repo: 8-bit wrapping cells, right-growing tape,
left-clamped pointer. Exhausted character input stores zero, as in the
wiki's cat example.
"""

from esolangs._drive import drive
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO
from esolangs.interpreters.source_hints import syntax_error
from esolangs.interpreters.tape_based.brainfuck import _Machine as _BFMachine


class _UnaryBFMachine(_BFMachine):
    def step(self) -> None:
        try:
            super().step()
        except EOFError:
            # Only comma reads input; it has no jump and replaces the cell.
            ind, ptr, tape, _acc, _dirty = self.state
            self.state = (ind + 1, ptr, tape, 0, True)


type _State = _UnaryBFMachine


def decode(code: str) -> str:
    """Return decoded Brainfuck, rejecting nonzero symbols and partial triples."""
    count = 0
    for char in code:
        if char == "0":
            count += 1
        elif not char.isspace():
            raise syntax_error(
                "Unary source must contain only zeros and whitespace",
                "write only 0 characters, with optional whitespace",
            )
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


class _Machine:
    """The decoded Brainfuck machine."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.state: _State = _UnaryBFMachine(decode(code), io)

    @property
    def halted(self) -> bool:
        return self.state.halted

    @property
    def ip(self) -> int:
        return self.state.ip

    @property
    def memory(self) -> list[int]:
        return self.state.memory

    @property
    def stack(self) -> list[object]:
        return self.state.stack

    @property
    def ptr(self) -> int:
        return self.state.ptr

    @property
    def tape(self) -> tuple[int, ...]:
        return self.state.tape

    def input_position(self) -> int:
        return self.state.input_position()

    def snapshot(self) -> tuple[object, ...]:
        return self.state.snapshot()

    def step(self) -> None:
        self.state.step()


def run(code: str, io: IO) -> None:
    """Decode Unary and run its Brainfuck program."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
