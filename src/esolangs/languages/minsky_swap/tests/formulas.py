"""Minsky Swap's emitted characters: the commands line, then the jump targets."""


def _full_chars(n: int, _: str) -> int:
    """Worst all-essential pair cascade, with every pair but one equal to 10."""
    if n == 1:
        return 51
    rows = 1 << (n - 1)
    end = 2 * rows + 6 * n + 13
    skips = [17 + 6 * (i + 1) + rows - (1 << (n - 2 - i)) for i in range(n - 1)]
    # All but one pair can target 13 while every high input stays essential.
    return (
        5 * rows
        + 8 * n
        + 23
        + 7 * len(str(end))
        + 2 * sum(len(str(skip)) for skip in skips)
    )


def _chars(n: int, _: str) -> int:
    """A global source ceiling, including arbitrary ignored input positions."""
    from esolangs.languages.minsky_swap.proof_formulas import commands

    bound = commands(n)
    return bound + (8 * n - 1) * (len(str(bound + 1)) + 1) + 7 + 3 * (1 << n) // 2


def witness(n: int) -> str:
    """The first-input projection attains the ignored-tail execution endpoint."""
    return "0" * (1 << (n - 1)) + "1" * (1 << (n - 1))


FORMULAS = {"scaling": (_chars, False, (3, 4, 5))}
