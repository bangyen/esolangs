"""brainfuck Boolean program generator: a flag-guarded tree or an affine stream.

Input bits sit at cells ``2i`` with flags at ``2i+1``; branches clear both and
one final print reads the result.  Equal sibling halves merge; repeated
residuals use one unused flag per level and emit once in depth order within
the command bound.  Affine tables stream through three cells instead, at
most 66 commands per selected input.  Every input is read with its ASCII
subtract into its own cell, ignored ones included.

Size:
    O(T) for dense tables, O(n) for affine ones; n=10 parity: 760 chars,
    n=12 parity: 902 chars, n=10 random 1847: 10,792 chars.

Decisions:
    Flags cut n=10 sparse from 2,646 to 754 chars; folding and shared output
    cut n=10 XOR from 77,939 to 18,495; the affine stream cut n=16 parity
    from 672,691 to 1,186.
"""

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    affine_form,
    decision_tree_body,
    in_input_order,
    move_text,
)
from esolangs.generation.shared_flag import shared_flag_tree
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

__all__ = ["bf_tree", "brainfuck"]


def brainfuck(truth_table: str) -> str:
    """Return a program for a binary, MSB-first ``2**n`` truth table."""
    return bf_tree(truth_table)


_RIGHT, _LEFT = ">", "<"


def bf_tree(truth_table: str) -> str:
    """Return a compact program, consuming every input unconditionally."""
    tree = in_input_order(truth_table, _bf_ordered)
    affine = _affine_stream(truth_table)
    return min((tree, affine), key=len) if affine is not None else tree


def _command_budget(n: int) -> int:
    """Return the command ceiling shared by the affine stream and shared body."""
    return 69 * n + 44


def _affine_stream(table: str) -> str | None:
    """Stream an admitted affine table through one bit and a toggle scratch."""
    n = _validate_truth_table(table)
    form = affine_form(table, n)
    if form is None:
        return None
    bias, coefficients = form
    # Input, accumulator, scratch occupy cells 0, 1, 2. Each selected read
    # costs at most 66 commands; a trailing ignored read must leave a bit
    # rather than ASCII beside the final ASCII output to retain workspace.
    parts = [">+<" if bias else ""]
    commands = 3 * bias + 50
    for i, coefficient in enumerate(coefficients):
        if coefficient:
            parts.append("," + "-" * _ASCII_ZERO + "[->>+<[->-<]>[-<+>]<<]")
            commands += 66
        elif i == n - 1:
            parts.append("," + "-" * _ASCII_ZERO)
            commands += 49
        else:
            parts.append(",")
            commands += 1
    if commands > _command_budget(n):
        return None
    parts.append(">" + "+" * _ASCII_ZERO + ".")
    return "".join(parts)


def _bf_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit a permuted table; node i tests cell 2*perm[i], reads stay ordered."""
    n = _validate_truth_table(truth_table)

    # read bits b_i at cell 2i, leaving the flag cells (1, 3, ...) zero
    header = (_RIGHT * 2).join("," + "-" * _ASCII_ZERO for _ in range(n))
    cells = [header]
    pos = 2 * max(n - 1, 0)
    tree_start = pos

    # The tree itself.
    body, pos = decision_tree_body(truth_table, _RIGHT, _LEFT, perm, pos)
    cells.append(body)

    # A shared print pays the ASCII offset once rather than at every leaf.
    cells.append(move_text(pos, 2 * n, _RIGHT, _LEFT))
    cells.append("+" * _ASCII_ZERO)
    cells.append(".")
    plain = "".join(cells)
    # The body's share of `_command_budget`.
    budget = _command_budget(n) - len(header) - _ASCII_ZERO - 1
    shared = shared_flag_tree(
        truth_table,
        perm,
        tree_start,
        2 * n,
        command_budget=budget,
    )
    if shared is not None and shared[1] <= budget:
        candidate = header + shared[0] + "+" * _ASCII_ZERO + "."
        if len(candidate) < len(plain):
            plain = candidate
    return plain


LANGUAGE = Language(
    "brainfuck",
    "brainfuck",
    category="tape_based",
    boolean=brainfuck,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
)
