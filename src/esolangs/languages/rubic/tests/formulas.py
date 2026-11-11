"""Literal-leaf maxima: source positions fit n+4 bits."""


def witness(n: int) -> str:
    """Alternate two distinct maximal children, seeded by constant/NOT pairs."""
    if n == 1:
        return "10"
    left, right = "0010", "1000"
    for _ in range(2, n):
        left, right = left + right, right + left
    return left
