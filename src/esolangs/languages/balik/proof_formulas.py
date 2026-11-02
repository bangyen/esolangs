"""Executed command bound: one path down the boxes, with every input essential.

A box's path minus its width is its child's plus 2r + 8 stacked, or 2r + 12
side by side, where r is the routing row; a leaf's is 0.  So the worst run
is the widest box with the tallest children: the parity table reaches it.
Two leaf children share the splitter row,
so a bottom box has height three and path excess ten, not twelve.
"""


def execution(n: int, _: str) -> int:
    """Even n, else odd n past 1; the 3n - 2 command prefix reads the inputs."""
    if n == 1:
        return 19
    if n % 2 == 0:
        return 34 * (1 << (n // 2)) + 7 * n - 40
    return 44 * (1 << ((n - 1) // 2)) + 7 * n - 38
