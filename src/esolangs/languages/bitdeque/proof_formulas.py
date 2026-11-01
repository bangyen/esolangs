"""Snapshot-bit bounds."""


def workspace(n: int, program: str) -> int:
    """N deque bits, a register bit and the cursor's bits of the token cap U."""
    if not program.startswith("GOTO "):
        bit = program.split()[-2] == "INVERT"
        return n + 1 + (3 * n + 2 + bit).bit_length()
    # c[d]: the most distinct nonconstant subtrees level d can emit; a node
    # costs 2 tokens and so does a repeated child at a zero position.
    c = [min(1 << d, (1 << (1 << (n - d))) - 2) for d in range(n)]
    tree = sum(2 * c[d] + 2 * min(c[d], 2 * c[d] - c[d + 1]) for d in range(n - 1))
    return n + 1 + (4 * n + 25 + tree).bit_length()
