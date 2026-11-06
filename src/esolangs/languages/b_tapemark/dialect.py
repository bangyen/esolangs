"""B-tapemark swap choices, independent of execution."""

#: The two readings of the post-swap step, named by whose marker moves.
SWAP_MARKERS = ("new", "old")


def validate_swap_marker(value: str) -> str:
    """Validate which grid's marker moves after a swap."""
    if value not in SWAP_MARKERS:
        raise ValueError("swap_marker must be new or old")
    return value
