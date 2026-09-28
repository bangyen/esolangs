"""INTERCAL boolean generator: a fully grouped Shannon expression."""

from dataclasses import dataclass

from esolangs.tools.helpers import (
    _validate_truth_table,
    best_input_order,
    constant_span_test,
)

TEMPLATE_CHAR = "@"
PAIR = ("#0", "#1")


@dataclass(frozen=True)
class _Expr:
    op: str
    value: int = 0
    children: tuple["_Expr", ...] = ()

    def render(self, depth: int = 0) -> str:
        if self.op == "constant":
            return f"#{self.value}"
        if self.op == "input":
            return f".{self.value + 1}"
        outer, inner = ("'", '"') if depth % 2 == 0 else ('"', "'")
        if self.op == "not":
            children, operator = (*self.children, _Expr("constant", 1)), "?"
        else:
            children = self.children
            operator = "&" if self.op == "and" else "V"
        left, right = children
        mingled = (
            f"{inner}{operator}{left.render(depth + 2)}$"
            f"{right.render(depth + 2)}{inner}"
        )
        return f"{outer}{mingled}~#2{outer}"


def intercal(truth_table: str) -> str:
    """Return a polite C-INTERCAL template computing ``truth_table``.

    Every input is assigned to its own variable before the expression, so
    the Shannon levels may select them in any order: the shorter of the
    identity and greedy orders is kept (:func:`best_input_order`).
    """
    return best_input_order(truth_table, _intercal_ordered)


def _intercal_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one order's template; level ``k`` selects input ``perm[k]``.

    ``truth_table`` is already permuted.  The assignments stay in name
    order, input ``i`` in ``.{n - i}``.
    """
    n = _validate_truth_table(truth_table)
    constant = constant_span_test(truth_table)

    def tree(level: int, lo: int, hi: int) -> _Expr:
        if constant(lo, hi):
            return _Expr("constant", int(truth_table[lo]))
        mid = (lo + hi) // 2
        # In name order large variable numbers occur near the root, where
        # their decimal spelling is repeated least; this keeps source size
        # linear in T.  A reorder moves them only through the greedy cap
        # (n = 10), where no name is longer than two digits.
        selector = _Expr("input", n - 1 - perm[level])
        zero, one = tree(level + 1, lo, mid), tree(level + 1, mid, hi)
        left = _Expr("and", children=(_Expr("not", children=(selector,)), zero))
        right = _Expr("and", children=(selector, one))
        return _Expr("or", children=(left, right))

    statements = [f".{n - i} <- {TEMPLATE_CHAR * 2}" for i in range(n)]
    statements += [f".{n + 1} <- {tree(0, 0, len(truth_table)).render()}"]
    statements += [f"READ OUT .{n + 1}", "GIVE UP"]
    polite = max(1, (len(statements) + 4) // 5)
    return "\n".join(
        f"{'PLEASE' if i < polite else 'DO'} {statement}"
        for i, statement in enumerate(statements)
    )
