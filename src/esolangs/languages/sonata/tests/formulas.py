"""Sonata's source maximum before pair packing, and its later ceiling."""


def _chars(n: int, _: str) -> int:
    """Full-support nonsymmetric doubling attains through six inputs."""
    # The n=1 identity stays on doubling: symmetric_weights requires m>=2.
    # A projection costs 2**m+2n+2m+80, plus21 if n=2. Pair packing
    # from m=7 instead costs <=2**(m-1)+2n+2m+115, below this ceiling.
    return (1 << n) + 4 * n + 101 - 21 * int(n != 2)
