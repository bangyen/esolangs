"""SwitchCase's emitted characters: jump loops per input, an arm a minority row."""


def _digits(x: int) -> int:
    return len(str(x))


def _chars(n: int, _: str) -> int:
    """N: 14 header, 71 + jump digits per input, 36 + digits(7n + 4) closing, arms.

    At most T/2 minority rows, each at most digits(k) + 4, the top half of
    the rows costing most.
    """
    jumps = sum(
        71 + 2 * _digits(7 + 7 * i) + _digits(4 + 7 * i) + _digits(10 + 7 * i)
        for i in range(n)
    )
    t = 1 << n
    arms = sum(_digits(k) + 4 for k in range(t // 2, t))
    return 14 + jumps + 36 + _digits(7 * n + 4) + arms


FORMULAS = {"scaling": (_chars, False, (1, 2, 3, 4, 5, 6, 8, 9, 10, 12))}
