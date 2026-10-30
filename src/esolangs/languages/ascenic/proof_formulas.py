"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """Line index, the larger of the Horner and scaled stacks, the input cursor.

    The larger of the forward and mirrored scans, each at its worst table
    (a constant prefix then alternating: the most lines, the last Horner
    push ``a``, the largest scaled product).  Mirrored, the Horner value
    ends at ``r - T``, one bit wider than the forward ``-r``; the pushes
    are ``8n - 5``, ``8n - 3``, the base is ``8n + 3`` and the program has
    ``2T + 6n + 5 - n mod 2`` lines.
    The mirror is one bit over the forward scan from n = 2, but wins no table
    at n = 2, so the bound is exact from n = 3.
    """
    bl = int.bit_length
    t = 1 << n

    def scan(lines: int, a: int, b: int, sign: int) -> int:
        return (
            bl(lines)
            + max(bl(a) + bl(a + 2) + n + sign, bl((b + 2 * t - 2) * (b + 2 * t - 1)))
            + bl(2 * n - 1)
        )

    a = 8 * n - 7 + 2 * (n % 2)
    return max(
        scan(2 * t + 6 * n + 3 + n % 2, a, a + 6, 1),
        scan(2 * t + 6 * n + 5 - n % 2, 8 * n - 5, 8 * n + 3, 2),
    )
