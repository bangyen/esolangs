"""Minsky Swap's emitted characters: the commands line, then the jump targets."""

from esolangs.languages.minsky_swap.proof_formulas import workspace


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
    """Exact through five inputs; a global ceiling beyond the two-digit era."""
    # For n<=5 every variable target has two digits. With m essential bits,
    # q trailing ignored bits, K=2**(m-1), delta non-10 pairs, exact length is
    # 34+10n+2m+5K+30q-delta. q<=n-m and delta>=1 for m>=2 make
    # m=1,q=n-1,delta=0 maximal. The symmetric reader is <=17+16n.
    if n <= 5:
        return 40 * n + 11
    from esolangs.languages.minsky_swap.proof_formulas import commands

    bound = commands(n)
    return bound + (8 * n - 1) * (len(str(bound + 1)) + 1) + 7 + 3 * (1 << n) // 2


def witness(n: int) -> str:
    """The first-input projection attains the ignored-tail execution endpoint."""
    return "0" * (1 << (n - 1)) + "1" * (1 << (n - 1))


def source_witness(n: int) -> str:
    """The first-input negation attains the source maximum through n=5."""
    return "1" * (1 << (n - 1)) + "0" * (1 << (n - 1))


FORMULAS = {
    "scaling": (_chars, frozenset(range(1, 6)), (3, 4, 5)),
    "workspace": (workspace, frozenset({1, 2, 3, 6}), (3, 6)),
}
