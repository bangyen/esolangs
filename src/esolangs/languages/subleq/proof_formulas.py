"""Snapshot-bit bounds."""


def _subleq(n: int, _: str) -> int:
    """Payload bits, signed references, two patched operands and registers."""
    bl = int.bit_length
    i, chunks = 8 * n + 47, -(-(1 << n) // n)
    b = 3 * i
    registers = (
        bl(3 * i - 3) + 5 * bl(n) + 2 * n + 33 + max(n, bl(n) + 1) + max(1, n - 1)
    )
    packed = (
        (1 << n)
        + 2 * chunks
        + (chunks + 2) * bl(b + 17 + 2 * chunks)
        + i * bl(b)
        + (2 * i - 1) * bl(b + 17)
        + registers
    )

    residuals = sum(min(1 << k, (1 << (1 << (n - k))) - 2) for k in range(n))
    memory = 19 + 10 * n + 6 * residuals
    # The tree's image: prefix, n reads of nine cells, a branch, a jump and
    # pointers per residual; a run rewrites only the inputs and scratch.
    width, read = bl(memory), bl(n + 6)
    tree = (
        45
        + 15 * n
        + 4 * width
        + 3 * n * (read + width)
        + residuals * (4 + read + 2 * width)
        + bl(n)
    )
    return max(packed, tree)


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    return _subleq(n, p)
