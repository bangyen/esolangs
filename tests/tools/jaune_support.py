"""A Jaune multiply program: two sentinel-delimited decimal operands, any length.

Test-only: it takes no truth table, so it is not a generator; it exercises
the interpreter's read loop, hold cell and unconditional jumps.
"""


def jaune_multiply() -> str:
    """Build a Jaune program reading two decimal numbers and printing their product.

    Digits MSB first, one per line, up to ``*`` for the first operand and
    ``#`` for the second; prints the product with no leading zeros, at any
    length (no ``n``).  Jaune's cells do not wrap (JauneJS uses JS numbers),
    so an operand is one cell and ``^`` prints it.  A read loop runs on an
    always-one cell so ``?``/``!`` jump unconditionally; a digit is folded
    with ``v+``, ``#`` (copy to hold) and nine ``&`` (x10); a sentinel is
    detected by ``6+`` zeroing ``*`` (42).  Cells 0-4: first operand, digit
    scratch, second operand, result, trigger.
    """
    out: list[str] = []
    pos = 0

    def move(target: int) -> None:
        nonlocal pos
        while pos < target:
            out.append(">")
            pos += 1
        while pos > target:
            out.append("<")
            pos -= 1

    def cmd(s: str) -> None:
        out.append(s)

    move(4)
    cmd("1+")  # cell 4 = 1: the unconditional loop-back trigger
    # read the first operand until '*': label 1 at cell 4
    cmd("1:")
    move(1)
    cmd("v")
    cmd("6+")  # '*' is 42, so ord-48 == -6; +6 zeroes it
    cmd("2!")  # a zero (the sentinel) exits to label 2
    cmd("6-")
    move(0)
    cmd("#")
    cmd("&" * 9)
    move(1)
    cmd("#")
    move(0)
    cmd("&")
    move(4)
    cmd("1?")  # always jump back to label 1
    cmd("2:")  # first operand done; the '*' was read at cell 1
    pos = 1
    move(4)
    # read the second operand until '#': label 4 at cell 4
    cmd("4:")
    move(1)
    cmd("v")
    cmd("13+")  # '#' is 35, so ord-48 == -13; +13 zeroes it
    cmd("3!")  # a zero (the sentinel) exits to label 3
    cmd("13-")
    move(2)
    cmd("#")
    cmd("&" * 9)
    move(1)
    cmd("#")
    move(2)
    cmd("&")
    move(4)
    cmd("4?")  # always jump back to label 4
    cmd("3:")  # second operand done; the '#' was read at cell 1
    pos = 1
    move(2)
    # multiply: while cell 2 != 0: cell 3 += cell 0; cell 2 -= 1
    cmd("5:")
    cmd("6!")
    move(0)
    cmd("#")
    move(3)
    cmd("&")
    move(2)
    cmd("1-")
    cmd("5?")
    cmd("6:")
    pos = 2
    move(3)
    cmd("^")
    cmd(".")
    return "".join(out)
