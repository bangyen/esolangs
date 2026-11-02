"""Written-state and command ceilings for the painted grid."""


def workspace(n: int, p: str) -> int:
    """Grid bits, one counter/guard frame, coordinates and two input cursors."""
    dimensions, body = p.split(":", 1)
    w, h = map(int, dimensions.split(","))

    def b(value: int) -> int:
        return max(1, value.bit_length())

    # Read49 and counter6 add at most seven bits above the one-bit grid.
    return w * h + 7 + 2 * b(w - 1) + 2 * b(h - 1) + 2 * b(len(body)) + 2 * b(n)


def execution(n: int, p: str) -> int:
    """The original row ceiling still bounds folded walks; count wrapping no-ops."""
    bound = 3 * (1 << n) + 85 * n + 5
    return 2 * bound + 1 if "\n" in p else bound
