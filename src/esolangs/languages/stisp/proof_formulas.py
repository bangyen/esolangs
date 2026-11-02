"""Snapshot-bit bounds."""


def workspace(n: int, program: str) -> int:
    """16 bits a frame and the root id; constants use an input list and one frame."""
    if program.replace("\n", "").startswith(("x->s[]=0;", "x->s[]=1;")):
        return 8 * n + 9
    nodes = sum(min(1 << k, (1 << (1 << (n - k))) - 2) for k in range(n))
    return 16 * n + 8 * len(str(nodes + 1))
