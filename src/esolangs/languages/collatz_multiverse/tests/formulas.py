"""Collatz Multiverse's emitted characters: m distinct cells, the largest popcounts."""

from esolangs.languages.collatz_multiverse.proof_formulas import _constants

_PAD = len("z=z x+z,NOT PRINT.")


def _popcounts(m: int) -> int:
    """The m largest popcounts of 0..15, summed: one 4, four 3s, six 2s, four 1s."""
    total, left = 0, m
    for weight, count in ((4, 1), (3, 4), (2, 6), (1, 4)):
        take = min(left, count)
        total += weight * take
        left -= take
    return total


def _chars(n: int, _: str) -> int:
    """N: the line lengths summed, plus a newline between lines.

    A cell line is 31 characters, 30 for codes 1 and 2 and a pad for code 0;
    the decoder takes 31 characters a set bit of the m largest popcounts.
    """
    cells, high = 1 << (n - 2), n - 2
    m = min(16, cells)
    lens = [
        len("k1 = negativeOne x + negativeOne, NOT PRINT."),
        len("k1 = negativeOne x + z, NOT PRINT."),
        len("k2 = negativeOne x + negativeOne, NOT PRINT."),
        len("k2 = negativeOne x + k1, NOT PRINT."),
    ]
    for k in _constants(n):
        c = (k - 2) % 4
        lens.append(len(f"k{k} = negativeOne x + k{(k - c) // 2}, NOT PRINT."))
        lens.append(len(f"k{k} = k2 x + {'k' + str(c) if c else 'z'}, NOT PRINT."))
    lens.append(len("t=z x+lineNumber,NOT PRINT."))
    pop = _popcounts(m)
    lens += [len("D[lineNumber]=z x+k1,NOT PRINT.")] * pop + [_PAD] * (4 * m - pop)
    # The cells block starts on an even line.
    lens += [_PAD, len("s=z x+lineNumber,NOT PRINT.")]
    # Code 0 is a pad, codes 1-2 are k4/k8 (30), the rest and every repeat 31.
    if m >= 4:
        lens += [_PAD, 30, 30] + [31] * (cells - 3)
    else:
        lens += [_PAD] + [30] * (cells - 1)
    lens += [len(f"w{i}=z x+input,NOT PRINT.") for i in range(n)]
    for k in range(high - 1):
        lens += [
            len(f"w{k}=k{2 ** (high - 1 - k)} x+z,NOT PRINT."),
            len(f"s=k1 x+w{k},NOT PRINT."),
        ]
    lens += [
        len(f"w{high - 1}=k1 x+k1,NOT PRINT."),
        len(f"s=k1 x+w{high - 1},NOT PRINT."),
        len("t=k1 x+A[s],NOT PRINT."),
        len(f"w{high}=k2 x+z,NOT PRINT."),
        len(f"t=k1 x+w{high},NOT PRINT."),
        len(f"w{high + 1}=k1 x+k1,NOT PRINT."),
        len(f"t=k1 x+w{high + 1},NOT PRINT."),
        len("o=z x+D[t],NOT PRINT."),
        len("o=k1 x+k48,DO PRINT."),
    ]
    return sum(lens) + len(lens) - 1


FORMULAS = {"scaling": (_chars, False, (3, 4, 5, 6, 7))}
