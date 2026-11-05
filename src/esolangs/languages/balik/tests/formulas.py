"""A compositional full-depth attainer after projection-leaf folding."""


def execution_witness(n: int) -> str:
    """One exceptional pair keeps every input essential; the last path is full."""
    return "10" if n == 1 else "00" + "10" * ((1 << (n - 1)) - 1)
