"""Executed command bounds."""


def execution(_: int, p: str) -> int:
    """Every instruction runs once, then the EOF read stops the second pass."""
    return len(p) + p.index(",") + 1


def workspace(n: int, p: str) -> int:
    """Old sweep envelope plus binary storage and its pointer growth."""
    if n >= 11:
        return (
            (len(p) - 1).bit_length()
            + max(6, n - 1)
            + max(19, 4 * n - 1)
            + n.bit_length()
            + 4
        )
    return (
        (len(p) - 1).bit_length()
        + max(6, n - 1)
        + max(19, 4 * n - 1)
        + 6
        + max(0, n - 6)
        + n.bit_length()
        + max(7, n + 1).bit_length()
        + 1
    )
