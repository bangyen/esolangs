"""Executed command and snapshot-bit bounds."""

from esolangs.runtime.memory import parse_int_memory


def execution(n: int, _: str) -> int:
    """An input reads, normalizes in 47, branches and jumps; then print, halt."""
    return 50 * n + 3


def _bits(value: int) -> int:
    return (value.bit_length() or 1) + (value < 0)


def workspace(n: int, program: str) -> int:
    """The program's cells, then what a run can add to them.

    A read cell goes from 0 to a byte below 64 (+5 bits an input); the
    pointer stays below the cell count, the input cursor at most ``n``; cell
    0, the unconditional decrements' target, falls by at most one a level.
    """
    cells = parse_int_memory(program)
    initial = sum(_bits(cell) for cell in cells)
    return (
        initial
        + 5 * n
        + len(cells).bit_length()
        + n.bit_length()
        + (n + 2).bit_length()
    )
