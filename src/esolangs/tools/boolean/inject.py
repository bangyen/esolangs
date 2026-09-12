r"""Boolean-function generator for Inject."""

from esolangs.tools.boolean.helpers import _validate_truth_table, best_input_order

__all__ = ["inject"]


def _leaf(bit: str, escape: str) -> list[str]:
    r"""Emit a leaf: send the answer's constant block, then jump clear."""
    return [f"send {'one' if bit == '1' else 'zero'}", "skip", f"{escape};"]


def _tree(
    table: str, depth: int, n: int, state: dict[str, int], perm: tuple[int, ...]
) -> list[str]:
    r"""Emit the decision tree for ``table``, testing input ``perm[depth]``."""
    # A constant subtree needs no.
    # bits are, the answer is the.
    # This is what makes a table.
    # rather than ``n`` of them.
    if depth == n or table == table[0] * len(table):
        state["leaves"] += 1
        return _leaf(table[0], f"e{state['leaves'] - 1}")

    half = len(table) // 2
    zeros = _tree(table[:half], depth + 1, n, state, perm)
    ones = _tree(table[half:], depth + 1, n, state, perm)

    # ``skipq`` fires when the bit.
    # the one-subtree: it is.
    # by falling through when the.
    block = f"b{depth}_{state['blocks']}"
    state["blocks"] += 1
    return [
        f"skipq i{perm[depth]} zero",
        f"{block};",
        *ones,
        f"{block};",
        *zeros,
    ]


def inject(truth_table: str) -> str:
    r"""Build an Inject program computing ``truth_table``."""
    return best_input_order(truth_table, _inject_ordered)


def _inject_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Emit one input order's Inject program; see :func:`inject`."""
    n = _validate_truth_table(truth_table)

    state = {"leaves": 0, "blocks": 0}
    body = [f"readto i{d}" for d in range(n)]
    body += _tree(truth_table, 0, n, state, perm)

    # Every escape block has to.
    # the closes come after the.
    # emitted innermost-last: a.
    # leaf's code too, and closing.
    tail = [f"e{i};" for i in range(state["leaves"])]

    # The constants.
    # node and the answer for a 0.
    # after the escape closes, so.
    tail += ["zero;", "0", "zero;", "one;", "1", "one;"]

    # The input blocks start empty:.
    # block is two adjacent.
    head = [f"i{d};\n i{d};".replace(" ", "") for d in range(n)]
    return "\n".join([*head, *body, *tail])
