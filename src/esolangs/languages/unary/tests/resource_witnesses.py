"""Named witnesses for the generated resource bounds."""


def resource_corpus(n: int) -> tuple[str, ...]:
    """Every table a nine-command source admits: constants and single inputs.

    Constant 0 is n commands, constant 1 n + 3, input i alone n + 2 if last
    else n + 4, one more negated; two or more essential inputs need 4n - 2 or
    more (AND 5n - 2, n = 2 only).
    """
    width = 1 << n

    def single(i: int, flip: int) -> str:
        return "".join(str((r >> (n - 1 - i) & 1) ^ flip) for r in range(width))

    shapes = {"0" * width: n, "1" * width: n + 3}
    for i in range(n):
        for flip in (0, 1):
            shapes[single(i, flip)] = n + (2 if i == n - 1 else 4) + flip
    tables = [table for table, commands in shapes.items() if commands <= 9]
    return (*tables, *(("0001",) if n == 2 else ()))
