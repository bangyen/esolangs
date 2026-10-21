"""Executed command bounds."""


def execution(n: int, _: str) -> int:
    r"""A one-row header: ``0``, ``&\2*+`` an input, 27 index commands.

    An ignored input reads as ``&$``, so ``k`` essential inputs run
    ``28 + 2n + 3k``; the worst table has every input essential.
    """
    if n <= 10:
        return 5 * n + 28
    return 5 * n + 67
