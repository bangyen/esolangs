"""Literal-leaf maxima: source positions fit n+4 bits."""


def workspace(n: int, _program: str) -> int:
    """n frames; one root start is a bit narrower from n=3."""
    return 3 * n * n + 15 * n + 117 + n.bit_length() + int(n < 3)


def witness(n: int) -> str:
    """Alternate two distinct maximal children, seeded by constant/NOT pairs."""
    if n == 1:
        return "10"
    left, right = "0010", "1000"
    for _ in range(2, n):
        left, right = left + right, right + left
    return left


FORMULAS = {"workspace": (workspace, True, (1, 2, 3, 6))}
