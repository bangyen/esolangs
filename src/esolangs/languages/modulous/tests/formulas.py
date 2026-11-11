"""Modulous's emitted characters: packed pairs and one ordered read per input."""


def resource_witness(n: int) -> str:
    """Use decoder code3 at the final pair to attain its long one-input arm."""
    return "0" * ((1 << n) - 2) + "10"
