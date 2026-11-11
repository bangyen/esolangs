"""Executed command bounds."""


def execution(_: int, p: str) -> int:
    """Every instruction runs once, then the EOF read stops the second pass."""
    return len(p) + p.index(",") + 1
