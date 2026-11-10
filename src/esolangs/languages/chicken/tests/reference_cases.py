"""Unexecuted fixtures retaining all 102 old independently expected families."""

from itertools import product
from operator import add, eq, mul, sub

from .reference_model import _source


def corpus():
    for left, right, opcode in product((0, 1, 7, 65, 255), (0, 1, 2, 66), (2, 3, 4, 5)):
        result = {2: add, 3: sub, 4: mul, 5: eq}[opcode](left, right)
        yield (
            _source((left + 10, right + 10, opcode)),
            "unused",
            4,
            str(result).lower(),
            None,
        )
    for index, stdin in product(range(4), ("", "aΩz", "0123")):
        output = stdin[index] if index < len(stdin) else "undefined"
        yield _source((10 + index, 6, 1)), stdin, 12, output, None
    for scalar in (0, 65, 937):
        yield _source((10 + scalar, 9)), "", 12, chr(scalar), None
    for condition, offset in product((0, 1), (0, 1)):
        output = "0" if condition and offset else "chicken"
        yield _source((10 + condition, 10 + offset, 8, 1)), "", 12, output, None
    for counts, output in (
        ((11, 12, 8, 1, 0, 11, 10, 17, 3, 8), "chicken"),
        ((11, 15, 7, 10), "chicken"),
        ((12, 6, 0, 10, 2), "12"),
    ):
        yield _source(counts), "", 12, output, None
    # The first102 source/input families and their caps stay above this point.
    for counts, stdin, output, error in (
        ((), "", "0", None),
        ((1,), "", "chicken", None),
        ((12, 1, 2), "", "2chicken", None),
        ((11, 1, 2, 11, 4), "", "NaN", None),
        ((12, 1, 5), "", "false", None),
        ((10, 6, 0, 10, 6, 0, 5), "", "true", None),
        ((10, 6, 0, 11, 5), "", "", "halt"),
        ((10, 6, 0, 1, 2), "", "", "halt"),
        ((10, 6, 99, 1), "", "", "halt"),
        ((10, 10, 11, 3, 7), "", "", "halt"),
        ((11, 1, 8), "", "", "halt"),
        ((15, 30, 7, 30, 6, 0), "", "5", None),
        ((15, 30, 7, 29, 6, 0), "", "undefined", None),
        ((11, 6, 0), "", "", None),
        ((11, 6, 0), "0", "0", None),
        ((11, 6, 0), "😀\r\n", "😀\r\n", None),
        ((11, 6, 0), "&#65;&#66;", "AB", None),
        ((11, 6, 0), "&#65;&#55296;", "", "halt"),
        ((10, 11, 3, 9), "", "&#-1;", None),
        ((11, 19, *((19, 4) * 7), 7), "", "", "limit"),
        ((12, 1, 2, 1, 2), "", "2chickenchicken", None),
        ((11, 13, 8), "", "0", None),
    ):
        yield _source(counts), stdin, 64, output, error
    for source in ("chicken hen\n", "chicken\tchicken", "CHICKEN"):
        yield source, "unread", 64, "", "syntax"
    # Named back-jump: push cond1, compute0-5, jump to the first push.
    yield _source((11, 10, 15, 3, 8)), "", 64, "", None
