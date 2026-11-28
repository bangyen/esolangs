"""Arity terms for the Pilas workspace formula."""


def workspace_terms(n: int, _program: str) -> dict[str, int]:
    """Price the retained input and the two constant-one pointers."""
    full = 3 * n + 10
    keep = min(n, max(0, (full - full.bit_length() - n.bit_length()) // 6))
    length = full - 2 * keep
    steps = 2 * n - keep + 10
    # The idle pointer cycles through 1, 2, 3. If it ends at 1, the
    # previous visit to 3 coincides with the main pointer at length-1.
    pointer = length.bit_length() + 2
    if steps % 3 == 2:
        pointer = max(length.bit_length() + 1, (length - 1).bit_length() + 2)
    return {"K": keep, "P": pointer}
