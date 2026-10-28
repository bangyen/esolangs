"""What!?'s emitted characters and commands past 15 inputs.

Through 15 inputs one block: 7(T-1) + digits of 1..T-1 + 7n + 12 characters.
Past, B = 2^(n-15) blocks of 2^15 rows, h = n - 15 high bits in each label.
"""


def _characters(n: int, _: str) -> int:
    """Per block 7 a change and its row digits, 13 the first write; the rest as before.

    A change at row ``r`` writes ``[r>.4x,]`` (``7 + len(r)``); a block has
    at most ``2^k - 1`` of them (alternating), then 23 + h its guard and
    164 + 3h the rest.
    """
    k, h = min(n, 15), max(0, n - 15)
    rows = 1 << k
    block = 7 * (rows - 1) + sum(len(str(r)) for r in range(1, rows))
    if h == 0:
        return block + 7 * n + 12
    return (1 << h) * (block + 13 + 10 + h) + 164 + 3 * h


def _commands(n: int, _: str) -> int:
    """Alternating answers, row 0: every test true, 5 a row; other blocks 1."""
    if n <= 15:
        return 5 * (1 << n) + 6 * n + 6
    return (1 << n) + (1 << 17) + n + (1 << (n - 15)) + 143


FORMULAS = {
    "scaling": (_characters, True, (3, 4, 5, 15, 16, 17, 18, 19, 20, 21, 22)),
    "execution": (_commands, True, (3, 4, 5)),
}
