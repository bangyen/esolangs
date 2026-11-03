"""Snapshot-bit bounds."""


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    source = "".join(p.split())
    if source.startswith("+>" * n + "<" * n + "[,,,,,,,,>]"):
        return 12 + bl(len(p) - 1) + 2 * bl(n) + sum(map(bl, range(1, n)))
    if source.startswith("," * (8 * n)):
        return 13 + bl(len(p) - 1) + bl(n)
    return (
        bl(len(p) - 1)
        + max(12, bl(2 * n - 3) + 11)
        + n
        + sum(map(bl, range(1, n)))
        + bl(2 * n)
        + bl(n)
    )
