"""Source ceiling for input buffering and shared residual cases."""

from esolangs.languages.switchcase.proof_formulas import diagram_cap


def _chars(n: int, _: str) -> int:
    """Input names and bounded-address residuals; O(T) characters in all."""
    nodes = diagram_cap(n)
    name = len(f"x{n - 1}")
    digits = len(str(n + nodes + 4))
    return 34 + n * (2 * name + 10) + nodes * (name + 10 + 2 * digits) + digits


def workspace_witness(n: int) -> str:
    """Parity at small rungs; all eight unequal-half residuals at n=5."""
    if n == 5:
        # First eight lexicographic two-bit functions depending on their
        # first bit. All upper nodes differ; last01 shares the first leaf.
        return "".join(f"{v:04b}" for v in range(16) if v >> 2 != v & 3)[:32]
    return "".join(str(row.bit_count() % 2) for row in range(1 << n))
