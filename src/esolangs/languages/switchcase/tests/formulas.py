"""Witness for buffered input and shared residual cases."""


def workspace_witness(n: int) -> str:
    """Parity at small rungs; all eight unequal-half residuals at n=5."""
    if n == 5:
        # First eight lexicographic two-bit functions depending on their
        # first bit. All upper nodes differ; last01 shares the first leaf.
        return "".join(f"{v:04b}" for v in range(16) if v >> 2 != v & 3)[:32]
    return "".join(str(row.bit_count() % 2) for row in range(1 << n))
