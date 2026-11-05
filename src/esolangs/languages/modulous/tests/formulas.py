"""Modulous's emitted characters: packed pairs and one ordered read per input."""


def _chars(n: int, _: str) -> int:
    """The full-essential asymmetric pair reader attains the source envelope."""
    if n == 1:
        return 68
    if n <= 4:
        return 6 * (1 << n) + 28 * n + 21
    if n == 5:
        return 3 * (1 << n) + 28 * n + 144
    return (1 << (n - 1)) + 48 * n + 157 + sum(len(str(1 << k)) for k in range(n - 1))


def resource_witness(n: int) -> str:
    """Use decoder code3 at the final pair to attain its long one-input arm."""
    return "0" * ((1 << n) - 2) + "10"
