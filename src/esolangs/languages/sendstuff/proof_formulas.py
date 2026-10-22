"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """A pending Input frame per 1 taken, at the largest node indices N_d."""
    bl = int.bit_length

    def nodes(j: int) -> int:
        """Most parser nodes at depth j: 4 per unequal-halves subtable, 1 else."""
        if j == n:
            return 4
        s, p = 1 << (n - j), 1 << j
        b = min(p, (1 << s) - (1 << (s // 2)))
        return 4 * b + min(p - b, 1 << (s // 2))

    ws = [nodes(j) for j in range(n + 1)]
    return bl(n) + 12 + sum(bl(1 + sum(ws[d + 1 :]) + ws[d] - 4) + 10 for d in range(n))
