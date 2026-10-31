"""Executed command and snapshot-bit bounds."""

from esolangs.runtime.memory import parse_int_memory


def _bits(value: int) -> int:
    return (value.bit_length() or 1) + (value < 0)


def workspace(n: int, program: str) -> int:
    """The program's cells, then what a run adds: 5 bits an input read, cell 0's sign.

    Reads lift each cell 0 -> 48/49 (+5 bits).  Cell 0, the unconditional
    decrements' target, is -1 after the entry jump (+1 bit).  In the pass loop
    it also falls to -16 while the reads still hold 32+ (+4 more, net of the
    counter's shrink); the peak is pass 16.  A constant never normalizes, so
    its cell 0 reaches -2 (3 bits) while the reads are wide: +2.  The pointer
    ends at the cell count, the input cursor at n.  Every table reaches it.
    """
    cells = parse_int_memory(program)
    constant = len(cells) == cells[2] + 3 * n + 3  # entry, n reads, one jump
    return (
        sum(_bits(cell) for cell in cells)
        + 5 * n
        + len(cells).bit_length()
        + n.bit_length()
        + (2 if constant else 5)
    )
