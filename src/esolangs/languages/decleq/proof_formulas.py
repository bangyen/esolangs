"""Executed command and snapshot-bit bounds."""

from esolangs.runtime.memory import parse_int_memory


def execution(n: int, _: str) -> int:
    """An input reads, normalizes in 47, branches and jumps; then print, halt."""
    return 50 * n + 3


def _bits(value: int) -> int:
    return (value.bit_length() or 1) + (value < 0)


def workspace(n: int, program: str) -> int:
    """The program's cells, then what a run adds: 5 bits an input read, cell 0's sign.

    Reads lift each cell 0 -> 48/49 (+5 bits), all before the chains shrink
    them; cell 0, the unconditional decrements' target, is -1 after the entry
    jump (+1 bit).  A constant never normalizes, so its cell 0 also reaches
    -2 (3 bits) while the reads are still wide: +2.  The pointer ends at the
    cell count, the input cursor at n.  Every table reaches it.
    """
    cells = parse_int_memory(program)
    constant = len(cells) == cells[2] + 3 * n + 3  # entry, n reads, one jump
    return (
        sum(_bits(cell) for cell in cells)
        + 5 * n
        + len(cells).bit_length()
        + n.bit_length()
        + 1
        + constant
    )
