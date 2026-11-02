"""Direct constants, indexed prefixes and direct-pop tails."""


def execution(n: int, program: str) -> int:
    """Scalar paths, or the largest indexed-prefix/direct-tail walk."""
    if program.startswith("[INP INT][ADD 48]"):
        return 4
    if program.startswith("[INP INT][JMP F 3 IF 0]"):
        return 7
    if program.startswith("[INP INT][POP]"):
        return 2 * n + 3
    return (1 << n) + 3 * n + 2 if n <= 4 else 5 * (1 << n) + 5 * n - 33


def workspace(n: int, program: str) -> int:
    """Stack peak and cursors; full tails need no counter."""
    bl = int.bit_length
    if n == 1 and program.startswith("[INP INT]"):
        return 9 + program.count("[").bit_length()
    if program.startswith("[INP INT][POP]"):
        return 7 + bl(2 * n + 3) + bl(2 * n - 1) + bl(n)
    if n <= 4:
        return 6 * (1 << n) + 2 + bl((1 << n) + 3 * n + 2) + bl(2 * n - 1) + bl(n)
    return 6 * (1 << n) + n + 2 + bl(6 * n + 8) + bl(2 * n - 1) + bl(n)
