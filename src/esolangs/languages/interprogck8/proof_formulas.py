"""Executed command and snapshot-bit bounds, R the program's lines."""


def _lines(program: str) -> int:
    return len(program.split("\n")) - program.endswith("\n")


def execution(n: int, program: str) -> int:
    """Each line runs at most once; a read's called body adds at most 11 lines."""
    return _lines(program) + 11 * n


def workspace(n: int, program: str) -> int:
    """A 7-bit accumulator, the line cursor at most R, the input cursor 2n.

    The slot and the frame calling it each hold a body of at most 33
    characters, the frame's index 4 bits.
    """
    return 7 + _lines(program).bit_length() + (2 * n).bit_length() + 2 * 8 * 33 + 4
