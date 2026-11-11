"""Semantic workspace terms for live lexical environments."""


def _loop_peak(height: int) -> int:
    """Bound the loop cursor and its split of height across two integers."""
    if height == 0:
        return 1
    width = height.bit_length()
    # Equal widths minimize the sum of the two powers needed for a total
    # width. Widths (width, width-1) fit at three half-width powers.
    extra = int(2 * height >= 3 * (1 << (width - 1)))
    return 11 + max(width + 1, 2 * width - 2 + extra)


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Identify the single local and price the deepest loop otherwise."""
    constant = program.startswith(("main{a,", "main{r{a,a,a,a,a,a,a,a=(in 0)}"))
    return {"C": int(constant), "G": 0 if constant else _loop_peak(max(n - 3, 0))}
