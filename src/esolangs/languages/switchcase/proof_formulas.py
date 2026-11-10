"""Execution and snapshot bounds for buffered residual dispatch."""


def diagram_cap(n: int) -> int:
    """A cap on distinct internal residuals, summed by depth."""
    # Avoid constructing the double-exponential term when the prefix cap wins.
    return sum(
        1 << depth if depth <= (1 << (n - depth)) else 1 << (1 << (n - depth))
        for depth in range(n)
    )


def workspace(n: int, _p: str) -> int:
    """Buffered names/bytes plus a default-arm branch; exact at n=1,2,3,5."""
    # Full input environment: B+18 bits for buffers, a and _. A branch's
    # default key costs8, cursor0 costs1, and case index is <=n+node_cap.
    # Other phases have numeric keys; ignored reads add5 to _ but remove
    # at least22 buffer bits. Their longer cursors fit the saved arm bits.
    buffered = sum(8 * len(f"x{i}") + 6 for i in range(n))
    return buffered + 27 + (n + diagram_cap(n)).bit_length() + n.bit_length()
