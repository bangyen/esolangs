r"""Boolean program generator for SStack: a decision tree of one-shot ifs.

Stacks ``b`` and ``c`` hold ``ord("1")`` and ``ord("0")``.  A node reads
its input onto ``a`` and runs ``[a\b/ one +a/a+][a\c/ zero +a/a+]~a~``: the
``+a/a+`` lifts the bit off its own constant so each loop runs at most
once, and a 0 lifted to 49 fails nothing, since the one-test already ran.
Subtrees keep ``a`` balanced, so a node's tests see its own bit.  A leaf
prints ``:b:`` or ``:c:``; a constant subtree reads its remaining inputs
onto ``d`` and prints once.  28 characters a node: O(T) size and build.
"""

from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
    subtree_ids,
)

_PROLOGUE = '"49/b""48/c"'
_LEAF = {"0": ":c:", "1": ":b:"}


def sstack(truth_table: str) -> str:
    """Build an SStack program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    constant = constant_span_test(truth_table)
    ids = subtree_ids(truth_table)
    out = [_PROLOGUE]

    def build(remaining: int, lo: int, hi: int) -> None:
        if constant(lo, hi):
            out.append(";d;" * remaining + _LEAF[truth_table[lo]])
            return
        mid = (lo + hi) // 2
        below = ids[n - remaining + 1]
        if below[lo >> (remaining - 1)] == below[mid >> (remaining - 1)]:
            out.append(";d;")  # halves agree: drop the bit, untested
            build(remaining - 1, lo, mid)
            return
        out.append(";a;[a\\b/")
        build(remaining - 1, mid, hi)
        out.append("+a/a+][a\\c/")
        build(remaining - 1, lo, mid)
        out.append("+a/a+]~a~")

    build(n, 0, len(truth_table))
    return "".join(out)
