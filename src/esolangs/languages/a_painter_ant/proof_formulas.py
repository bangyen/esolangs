"""Executed command bounds."""


def execution(_: int, p: str) -> int:
    """Two passes of the whitespace-free program, the second proving the repeat."""
    return 2 * len("".join(p.split()))
