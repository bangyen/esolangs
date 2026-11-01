"""Direct constants and the unchanged lookup envelopes."""


def execution(n: int, program: str) -> int:
    """Two commands per discarded input, then push, print and halt."""
    if program.startswith("[INP INT][ADD 48]"):
        return 4
    if program.startswith("[INP INT][JMP F 3 IF 0]"):
        return 7
    if program.startswith("[INP INT][POP]"):
        return 2 * n + 3
    return 5 * (1 << n) + 5 * n + 1


def workspace(n: int, program: str) -> int:
    """Constants hold one byte, three cursors and the halt flag."""
    bl = int.bit_length
    if n == 1 and program.startswith("[INP INT]"):
        return 9 + program.count("[").bit_length()
    if program.startswith("[INP INT][POP]"):
        return 7 + bl(2 * n + 3) + bl(2 * n - 1) + bl(n)
    return 6 * (1 << n) + n + 2 + bl(6 * n + 5) + bl(2 * n - 1) + bl(n)
