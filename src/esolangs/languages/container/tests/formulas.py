"""Container's emitted characters: the threshold program's worst table."""


def _digits(m: int) -> int:
    """Decimal digits of 1..m written together."""
    total, low = 0, 1
    for e in range(1, len(str(max(m, 1))) + 1):
        total += e * max(0, min(m, 10**e - 1) - low + 1)
        low *= 10
    return total


def _threshold(n: int, _: str) -> int:
    """Threshold program on 0 0 (1 0)^(T/2-1), n <= 25 (one-letter names)."""

    def d(m: int) -> int:
        return len(str(m))

    pulse = 36 + d(2 * n) + sum(12 + d(2 * k) + d(2 * k + 1) for k in range(1, n))
    window = sum(36 + d(2 * k) + d(2 * k + 1) + d(2 * k + 2) for k in range(n))
    counter = 24 + d(2 * n - 1) + d(2 * n) + d(2 * n + 1)
    counter += sum(6 + d(2**j) for j in range(n))
    steps = 6 + 6 * (2**n - 2) + _digits(2**n - 1)
    tail = 25 + 2 * d(2 * n + 1)
    return pulse + window + counter + steps + tail + 9 * n + 12 + 2**n


FORMULAS = {"scaling": (_threshold, False, (2, 3, 4, 5))}
