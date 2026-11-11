"""The shift-register term of Forbin's seven-input block ceiling."""


def scaling_terms(n: int, _: str) -> dict[str, int]:
    """Price a register whose live prefix halves at each shift."""
    depth = min(n, 7)
    block = 1 << depth
    high = n - depth
    # Cell names start at index n+2. Each live prefix pays one extra
    # letter for each cell beyond the one-letter alphabet.
    short = max(0, 50 - n)
    first = min(depth + 1, max(1, short.bit_length()))
    shift_extras = 2 * block - (1 << first) - (depth - first + 1) * short
    register = (
        19
        + (n >= 51)
        + (n >= 50)
        + 6 * block
        + max(0, block - short)
        + 11 * depth
        + max(0, n - max(high, 51))
        + shift_extras
    )
    return {"G": register}
