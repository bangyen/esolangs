"""Executed command bounds the ledger notation cannot state."""


# The tree segment is a cell count, not a fit.  The reader costs
# 288n + 679: a fixed 8-pass multiply ring, a 3n - 1 reads run, and
# the retire ring's 48 passes, each crossing a 3n + 4 body and a
# 3n + 5 return leg.  The walk costs at most T + 9n + 1: five cells
# per level at a node, falls that telescope to under T rows in all
# (a row is appended per one edge), and a leaf sweep of at most
# 4n + 2.  Entry and the funnel add 7.  Constant tables land exactly
# 2 under the count at every arity; the parity witness reaches
# 2,194 of 2,204 at n = 5.
def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    if n < 7:
        return (1 << n) + 297 * n + 687
    return 18 * (1 << n) + 56 * n + 5
