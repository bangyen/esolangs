"""SwitchCase's emitted characters: jump loops per input, one arm a row."""


def _digits(x: int) -> int:
    return len(str(x))


def _chars(n: int, _: str) -> int:
    """N: header, 71 + jump digits per input, 24 a block, 2 digits(k) + 3 an arm."""
    jumps = sum(
        71 + 2 * _digits(6 + 7 * i) + _digits(3 + 7 * i) + _digits(9 + 7 * i)
        for i in range(n)
    )
    t = 1 << n
    m = t % 100
    arms = 680 * (t // 100) + 7 * m - 2 * min(m, 10)
    return 12 + jumps + 24 * -(-t // 100) + arms


FORMULAS = {"scaling": (_chars, True, (1, 2, 3, 4, 5, 6, 8, 9, 10, 12))}
