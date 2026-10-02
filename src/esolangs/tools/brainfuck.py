"""Build brainfuck Boolean programs with a folded decision tree."""

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    decision_tree_body,
    in_input_order,
    move_text,
)

__all__ = ["bf_tree", "brainfuck"]


def brainfuck(truth_table: str) -> str:
    """Return the folded tree for a binary, MSB-first ``2**n`` truth table.

    It beats minterm sums through n=4 except constants: 277 vs 253 chars
    (1.1x, formerly 2.5x), insufficient to retain a second construction.
    """
    return bf_tree(truth_table)


_RIGHT, _LEFT = ">", "<"


def bf_tree(truth_table: str) -> str:
    """Return the folded decision tree, consuming every input unconditionally.

    Bits use cells 2i, flags 2i+1; branches clear both, and one final print
    reads the result. Flags cut n=10 sparse from 2,646 to 754 chars;
    folding and shared output cut n=10 XOR from 77,939 to 18,495.
    """
    return in_input_order(truth_table, _bf_ordered)


def _bf_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit a permuted table; node i tests cell 2*perm[i], reads stay ordered."""
    n = _validate_truth_table(truth_table)

    cells: list[str] = []
    pos = 0

    def move(target: int) -> None:
        nonlocal pos
        delta = target - pos
        cells.append(_RIGHT * delta if delta >= 0 else _LEFT * -delta)
        pos = target

    # read bits b_i at cell 2i, leaving the flag cells (1, 3, ...) zero
    for i in range(n):
        cells.append(",")
        cells.append("-" * _ASCII_ZERO)
        if i < n - 1:
            move(pos + 2)

    # The tree itself, which Factor also builds around its own prologue.
    body, pos = decision_tree_body(truth_table, _RIGHT, _LEFT, perm, pos)
    cells.append(body)

    # A shared print pays the ASCII offset once rather than at every leaf.
    cells.append(move_text(pos, 2 * n, _RIGHT, _LEFT))
    cells.append("+" * _ASCII_ZERO)
    cells.append(".")
    return "".join(cells)
