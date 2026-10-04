"""Interpreter for Unary.

Count zero digits, remove the leading binary 1, and decode 3-bit commands
in > < + - . , [ ] order. Whitespace is ignored, as in the wiki's formatted
example. Empty source halts; one zero encodes empty Brainfuck. Other symbols,
incomplete triples and unmatched brackets raise ValueError. The unspecified
Brainfuck dialect follows this repo: 8-bit wrapping cells, right-growing tape,
left-clamped pointer. Exhausted character input stores zero, as in the
wiki's cat example.
"""

from esolangs._brainfuck import BrainfuckDialect
from esolangs._drive import drive
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO
from esolangs.interpreters.source_hints import syntax_error
from esolangs.interpreters.tape_based.brainfuck import _Machine as _BFMachine

type _State = _BFMachine


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

    eof_is_a_value = True

    def __init__(
        self,
        code: str,
        io: IO,
        *,
        cell_modulus: int | None = 256,
        tape_size: int | None = None,
        boundary: str = "clamp",
        eof: str = "zero",
    ) -> None:
        BrainfuckDialect(cell_modulus, tape_size, boundary, eof)
        self.eof_is_a_value = eof != "error"
        self.supports_tape_growth = tape_size is None
        self.io = io
        self.state: _State = _BFMachine(
            decode(code),
            io,
            cell_modulus=cell_modulus,
            tape_size=tape_size,
            boundary=boundary,
            eof=eof,
        )

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


def run(
    code: str,
    io: IO,
    *,
    cell_modulus: int | None = 256,
    tape_size: int | None = None,
    boundary: str = "clamp",
    eof: str = "zero",
) -> None:
    """Decode Unary and run its Brainfuck program."""
    drive(
        _Machine(
            code,
            io,
            cell_modulus=cell_modulus,
            tape_size=tape_size,
            boundary=boundary,
            eof=eof,
        )
    )


if __name__ == "__main__":
    script_main(run)
