"""What!?'s emitted characters and commands past 15 inputs.

Through 15 inputs one block: 13T + 7n - 1 characters, 6T + 6n + 5 commands.
Past, B = 2^(n-15) blocks of 2^15 rows, h = n - 15 high bits in each label.
"""


def _characters(n: int, _: str) -> int:
    """13(T - B) changes and dashes, 23 + h a block guard, 164 + 3h the rest."""
    t, h = 1 << n, max(0, n - 15)
    if h == 0:
        return 13 * t + 7 * n - 1
    return 13 * t + 164 + 3 * h + (1 << h) * (10 + h)


def _commands(n: int, _: str) -> int:
    """Alternating answers, last row: its block 6 a row, every other block 2."""
    if n <= 15:
        return 6 * (1 << n) + 6 * n + 5
    return 2 * (1 << n) + (1 << 17) + n + 143


FORMULAS = {
    "scaling": (_characters, True, (3, 4, 5, 15, 16)),
    "execution": (_commands, True, (3, 4, 5)),
}
