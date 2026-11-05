"""The minority-planting maximum, including the original eight-input rung."""


def _chars(n: int, _: str) -> int:
    return 3 * (1 << n) + 19 * n + 115
