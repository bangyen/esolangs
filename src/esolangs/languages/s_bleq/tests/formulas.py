"""S*bleq's emitted characters: the packed decoder, n = 11..18."""


def _chars(n: int, _: str) -> int:
    """P: 175n + 719, then each chunk's widest decimal.

    Two more once N and COUNT take two digits.
    """
    t = 1 << n
    full, rest = divmod(t, n)
    total = 175 * n + 719 + 2 * (n >= 10) + full * (2 + len(str((1 << n) - 1)))
    if rest:
        total += 2 + len(str((1 << rest) - 1))
    return total


FORMULAS = {"scaling": (_chars, True, (11, 12, 13))}
