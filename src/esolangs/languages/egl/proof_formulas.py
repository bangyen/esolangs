"""Exact default maxima and wrapped bounds for the painted grid."""


def workspace(n: int, p: str) -> int:
    """Grid bits, one counter/guard frame, coordinates and two input cursors."""
    if n <= 3:
        # R=1 retains every old public byte. Its loop row is 0/1, not 2;
        # the last guard frame is six characters short of the body cursor.
        digits = len(str(1 << n))
        return (
            3 * (1 << n)
            + 2 * n
            + 10
            + (len(p) - digits - 3).bit_length()
            + (len(p) - digits - 9).bit_length()
            + 2 * n.bit_length()
        )
    dimensions, body = p.split(":", 1)
    w, h = map(int, dimensions.split(","))

    def b(value: int) -> int:
        return max(1, value.bit_length())

    # Read49 and counter6 add at most seven bits above the one-bit grid.
    return w * h + 7 + 2 * b(w - 1) + 2 * b(h - 1) + 2 * b(len(body)) + 2 * b(n)


def execution(n: int, p: str) -> int:
    """Paint T-1 ones and take every guard; wrapped no-ops retain a safe bound."""
    size = 1 << n
    if n <= 3:
        bound = 3 * size + 85 * n + 5
    else:
        columns = 1 << min(n, (n + 3) // 2)
        bound = 2 * size + columns + 5 * (size // columns) + 85 * n - 1
    return 2 * bound + 1 if "\n" in p else bound
