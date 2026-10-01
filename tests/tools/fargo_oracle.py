"""Retired positive factoring, retained for size comparisons."""


def _anf_expression(coeffs: list[int], n: int, at: tuple[int, ...]) -> str:
    """Return the retired positive ANF expression in a flat piece list."""
    nonzero = [0]
    for coefficient in coeffs:
        nonzero.append(nonzero[-1] + coefficient)
    pieces: list[str] = []

    def build(start: int, size: int, bit: int) -> None:
        """Emit the span, which is known to hold a nonzero coefficient."""
        if size == 1:
            pieces.append("1")
            return
        half = size // 2
        if nonzero[start + half] == nonzero[start + size]:
            build(start, half, bit - 1)
            return
        if nonzero[start] != nonzero[start + half]:
            pieces.append("^ ")
            build(start, half, bit - 1)
            pieces.append(" ")
        if nonzero[start + size] - nonzero[start + half] == 1 and coeffs[start + half]:
            pieces.append(f"@ {at[bit]:b}")
        else:
            pieces.append(f"& @ {at[bit]:b} ")
            build(start + half, half, bit - 1)

    if nonzero[-1] == 0:
        return "0"
    build(0, 1 << n, n - 1)
    return "".join(pieces)
