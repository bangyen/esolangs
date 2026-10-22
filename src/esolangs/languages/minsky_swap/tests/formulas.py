"""Minsky Swap's emitted characters: the commands line, then the jump targets."""


def _chars(n: int, _: str) -> int:
    """N: line 1 (3T + 12n + 10), a newline, then the jump targets and spaces."""
    t = 1 << n
    end = 2 * t + 6 * n + 6  # one past the last command; also the two halt targets
    skips = [6 * (i + 2) + t - (1 << (n - 1 - i)) for i in range(n)]  # per stage
    digits = 1 + 2 * len(str(end)) + 2 * sum(len(str(s)) for s in skips) + t
    return (3 * t + 12 * n + 10) + 1 + digits + (3 + 2 * n + t - 1)


FORMULAS = {"scaling": (_chars, True, (3, 4, 5))}
