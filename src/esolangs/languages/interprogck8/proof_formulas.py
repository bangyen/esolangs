"""Executed command and snapshot-bit bounds, R the program's lines."""


def _lines(program: str) -> int:
    return len(program.split("\n")) - program.endswith("\n")


def execution(n: int, program: str) -> int:
    """Each line runs at most once: 86 a level, 168 with lane seeks past n = 15.

    Stride-66 flights cross at most R lines; the printer region adds the rest.
    """
    return (86 if n <= 15 else 168) * n + _lines(program) // 66 + 290


def workspace(n: int, program: str) -> int:
    """A 7-bit accumulator, the line cursor at most R, the input cursor 2n."""
    return 7 + _lines(program).bit_length() + (2 * n).bit_length()
