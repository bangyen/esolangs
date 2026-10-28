"""Snapshot-bit bounds."""


def _forbin(n: int, _: str) -> int:
    """Main's locals twice (frame and scope) and G, the loop cursor's peak.

    G grows with the tree depth h, so the narrowest block (3 inputs) is the peak.
    """
    bl = int.bit_length
    h = max(n - 3, 0)
    loop = [bl(j + 1) + max(1, bl(h - 1 - j)) + 10 for j in range(h)]
    return 32 * n + 71 + 2 * bl(n) + max([bl(h + 1) + 4, *loop])


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    return _forbin(n, p)
