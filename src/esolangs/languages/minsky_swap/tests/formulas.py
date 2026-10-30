"""Minsky Swap's emitted characters: the commands line, then the jump targets."""


def _chars(n: int, _: str) -> int:
    """N: line 1 (2T + 6n + 5), a newline, then the jump targets and spaces."""
    t = 1 << n
    end = 2 * t + 6 * n + 6  # one past the last command; also the two halt targets
    skips = [6 * (i + 2) + t - (1 << (n - 1 - i)) for i in range(n)]  # per stage
    digits = 1 + 2 * len(str(end)) + 2 * sum(len(str(s)) for s in skips) + t
    return (2 * t + 6 * n + 5) + 1 + digits + (3 + 2 * n + t - 1)


FORMULAS = {"scaling": (_chars, True, (3, 4, 5))}
