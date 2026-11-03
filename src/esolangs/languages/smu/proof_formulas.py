"""Snapshot-bit bounds."""


def workspace(n: int, p: str) -> int:
    """Generic n>=2: code E, stack E-78 and variables E-75 bytes at their peaks.

    E=93T-80; root child programs bound both variable values. The terminal
    empty-name store is smaller than this root peak, except for n=1 constants.
    """
    bl = int.bit_length
    if "".join(p.split()).startswith("k((())=())km"):
        # At n=1 the dead empty-name store exceeds the root variable peak.
        return 2688 * n - 1158 + 8 * (n == 1) + bl(84 * n + 13) + bl(n)
    return 24 * (93 * (1 << n) - 80) - 1214 + bl(93 * (1 << n) - 80) + bl(n)
