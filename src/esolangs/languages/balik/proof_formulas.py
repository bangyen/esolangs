"""Executed command bound: one path down the boxes, with every input essential.

A box's path minus its width is its child's plus 2r + 8 stacked, or 2r + 12
side by side, where r is the routing row; a leaf's is 0.  So the worst run
is the widest box with the tallest children: the parity table reaches it.
"""


def execution(n: int, _: str) -> int:
    """Even n, else odd n past 1; the 3n - 2 command prefix reads the inputs."""
    if n == 1:
        return 21
    if n % 2 == 0:
        return 38 * (1 << (n // 2)) + 7 * n - 44
    return 50 * (1 << ((n - 1) // 2)) + 7 * n - 42
