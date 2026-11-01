"""Executed command and snapshot-bit bounds."""

from esolangs.runtime.memory import parse_int_memory


def _bits(value: int) -> int:
    return (value.bit_length() or 1) + (value < 0)


def workspace(n: int, program: str) -> int:
    """Program bits plus written cells, final pointer and input cursor.

    Native constants add five scratch bits and one halt-cell sign bit.
    Other tables peak on pass 16: wide reads plus cell zero's sign/growth,
    net of the counter shrinking, add 5n+5 bits.
    """
    cells = parse_int_memory(program)
    if cells[0] == -1:
        return (
            sum(_bits(cell) for cell in cells)
            + 6
            + len(cells).bit_length()
            + n.bit_length()
        )
    return (
        sum(_bits(cell) for cell in cells)
        + 5 * n
        + len(cells).bit_length()
        + n.bit_length()
        + 5
    )
