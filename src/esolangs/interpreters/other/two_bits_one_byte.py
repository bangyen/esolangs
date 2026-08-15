"""Interpreter for 2 Bits, 1 Byte.

The program is a single byte whose 8 bits form four 2-bit instructions,
executed in sequence with the instruction pointer wrapping: ``00`` = DON (do
nothing), ``01`` = ACT (apply a bitwise operation to the byte), ``10`` = JMP
(jump, honoring the wrap), and ``11`` = END (print the byte as a character and
halt).  The single program byte is the only input -- there is no separate
input channel.

The 2-bit fields are read from the most significant pair downward (bits 7-6,
then 5-4, 3-2, 1-0), wrapping around.  ACT consumes two further 2-bit
operands X and Y: X selects a bit pair (1 = bits 4-5, 2 = bits 2-3, 3 = bits
0-1; 0 selects nothing) and Y, the value of that pair, picks the operation --
Y <= 1 XORs in the whole selected pair, Y >= 2 XORs in only the pair's high
bit -- after which execution resumes at the field after X.  JMP X jumps the
instruction pointer to field X.  The byte operated on is the program byte
itself, so ACT instructions change the program as it runs.

This matches the RISC-V cross-check (``extra/assembly/2b1b-riscv.s``), which
follows
the wiki's *disassembly example* for ACT (bit toggles / shift-combines driven
by the two operands) rather than the wiki's command-table description of a
fixed value mapping (00->11, 01->10, 10->00, 11->01); the wiki's two
descriptions disagree, and the cross-check follows the example.

Divergences from the cross-check:
- The first byte of ``code`` is the program byte; extra bytes are ignored.
- An empty program halts with no output (the cross-check would read whatever
  byte sits on its stack from stdin).
- Programs that never reach an END (e.g. 0x00) loop forever, exactly as the
  cross-check does; detect that from outside with a step limit or timeout.
"""

import sys

from esolangs.interpreters.io import IO


def _ror2(value: int) -> int:
    """Rotate an 8-bit value right by two bits."""
    return ((value >> 2) | (value << 6)) & 0xFF


def _read_field(state: tuple[int, int], byte: int) -> tuple[tuple[int, int], int]:
    """Advance the ``(cl, bl)`` reader state and return the next 2-bit field.

    Mirrors the cross-check's ``num`` subroutine: ``cl`` walks the field down
    the byte (mod 8) while ``bl`` is a rotating 2-bit mask; the field is
    ``(bl & byte) >> cl``.
    """
    cl, bl = state
    cl = (cl - 2) & 7
    bl = _ror2(bl)
    field = (bl & byte) >> cl
    return (cl, bl), field


def _seek(field: int) -> tuple[int, int]:
    """Return the ``(cl, bl)`` state that reads ``field`` next.

    Mirrors the cross-check's ``ind`` subroutine: the mask ``3`` is positioned
    at the field (``3 << (6 - 2*field)``) and pre-rotated, because
    ``_read_field`` rotates and advances before reading.
    """
    cl = (6 - 2 * field) & 7
    mask = (3 << cl) & 0xFF
    return (cl + 2) & 7, ((mask << 2) | (mask >> 6)) & 0xFF


def run(code: str, io: IO) -> None:
    """Run a 2 Bits, 1 Byte program."""
    if not code:
        return
    byte = ord(code[0]) & 0xFF
    state = (8, 0x03)

    while True:
        state, instr = _read_field(state, byte)
        if instr == 0:  # DON
            continue
        if instr == 1:  # ACT
            state, operand = _read_field(state, byte)
            saved = state
            state = _seek(operand)
            state, toggle = _read_field(state, byte)
            if toggle <= 1:
                byte ^= state[1]
            else:
                byte ^= ((state[1] << 1) & state[1]) & 0xFF
            state = saved
        elif instr == 2:  # JMP
            state, operand = _read_field(state, byte)
            state = _seek(operand)
        else:  # END
            io.print_char(chr(byte))
            return


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], "rb") as file:
            run(file.read().decode("latin-1"), IO())
