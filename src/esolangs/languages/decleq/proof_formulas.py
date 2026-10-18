"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    k = (2 * n - 1).bit_length()
    return 49 * n + 3 * (1 << k) + 2 + n - k


def _decleq(n: int, _: str) -> int:
    """The memory tuple and registers; the letters are the ledger's."""
    bl = int.bit_length

    def ones(x: int) -> int:
        return bin(x).count("1")

    k = min(n, bl(2 * n - 1))
    s, m, c = 1 << k, n - k, -(-(n + 18) // 3) * 3
    p = c + 144 * n + 3 * k + 3 * s - 3
    b = sum(bl(18 + i) for i in range(n))
    d = sum(
        2 * bl(18 + m + j) + bl(p + 3 * (j - k + 2) - 3 * (1 << (k - 1 - j)))
        for j in range(k)
    )
    e = sum(
        2 * bl(18 + lv)
        + bl(p + 3 * lv + (2 * u + 1) * (1 << (m - lv - 1)) * (s + 18) - 3 * ones(u))
        for lv in range(m)
        for u in range(1 << lv)
    )
    xs = [p + 3 * m + j * (s + 18) - 3 * ones(j) for j in range(1 << m)]
    f = sum(
        22 + 6 * s + bl(x) + bl(x + 9) + 2 * bl(x + 10) + bl(x + 14 + s) for x in xs
    )
    r = 3 * bl(p - 3 + (1 << m) * (s + 18)) + bl(n) + bl(c) + c + k + 8
    return 55 * n + 11 * s + 95 * b + d + e + f + r


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    return _decleq(n, p)
