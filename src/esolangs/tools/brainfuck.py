"""Build brainfuck Boolean programs with folded trees or affine streams."""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.brainfuck_binary import binary_bank, larger_suffix_bank
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    decision_tree_body,
    essential_inputs,
    in_input_order,
    move_text,
)
from esolangs.tools.shared_flag import shared_flag_tree
from esolangs.tools.wrap import wrap_chars

__all__ = ["bf_tree", "brainfuck"]


def brainfuck(truth_table: str) -> str:
    """Return a program for a binary, MSB-first ``2**n`` truth table."""
    return bf_tree(truth_table)


_RIGHT, _LEFT = ">", "<"


def bf_tree(truth_table: str) -> str:
    """Return a compact program, consuming every input unconditionally.

    Tree bits use cells 2i, flags 2i+1; branches clear both, and one final print
    reads the result. Flags cut n=10 sparse from 2,646 to 754 chars;
    folding and shared output cut n=10 XOR from 77,939 to 18,495.  Equal
    sibling halves merge; repeated residuals use one unused flag per level
    and emit once in depth order, within the existing command bound.
    A bank can use several unused descendant flags instead: a same-level bank,
    or the union of the one-per-depth picks with the greatest bank, so blocks
    at several depths defer.
    Two-input banks also use four-bit labels, with a retired input holding
    the high bit; labels are consumed before their shared bodies execute.
    Affine tables also stream through three cells: n=16 parity falls from
    672,691 to 1,186 chars, with at most 66 commands per selected input.
    An ignored input before the last kept one is read bare into the next
    kept cell, whose read overwrites it: 1.9% smaller at n=8 with one ignored,
    6.7% with two. A trailing one keeps its subtract; left at 48/49 it breaks
    the Workspace bound, and ``,[-]`` the execution bound (289 > 251 steps).
    """
    tree = in_input_order(truth_table, _bf_ordered)
    affine = _affine_stream(truth_table)
    return min((tree, affine), key=len) if affine is not None else tree


def _affine_stream(table: str) -> str | None:
    """Stream an admitted affine table through one bit and a toggle scratch."""
    n = _validate_truth_table(table)
    bias = int(table[0])
    coefficients = [int(table[1 << (n - i - 1)]) ^ bias for i in range(n)]
    expected = [bias]
    for coefficient in reversed(coefficients):
        expected += [value ^ coefficient for value in expected]
    if any(str(value) != bit for value, bit in zip(expected, table, strict=True)):
        return None
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
    if commands > 69 * n + 44:
        return None
    parts.append(">" + "+" * _ASCII_ZERO + ".")
    return "".join(parts)


def _bf_ordered(
    truth_table: str, perm: tuple[int, ...], *, share: bool = True, bank: bool = True
) -> str:
    """Emit a permuted table; node i tests cell 2*perm[i], reads stay ordered."""
    n = _validate_truth_table(truth_table)

    # read bits b_i at cell 2i, leaving the flag cells (1, 3, ...) zero; an
    # ignored input is read into the next kept input's cell, which overwrites it
    kept = essential_inputs(truth_table, n)
    last = kept[-1] if kept else -1
    reads, pending = [], ""
    for i in range(n):
        if i in kept or i > last:
            reads.append(pending + "," + "-" * _ASCII_ZERO)
            pending = ""
        else:
            reads.append("")
            pending += ","
    cells = [(_RIGHT * 2).join(reads)]
    pos = 2 * max(n - 1, 0)
    header = cells[0]
    tree_start = pos

    # The tree itself.
    body, pos = decision_tree_body(truth_table, _RIGHT, _LEFT, perm, pos)
    cells.append(body)

    # A shared print pays the ASCII offset once rather than at every leaf.
    cells.append(move_text(pos, 2 * n, _RIGHT, _LEFT))
    cells.append("+" * _ASCII_ZERO)
    cells.append(".")
    plain = "".join(cells)
    if not share:
        return plain
    shared = shared_flag_tree(
        truth_table,
        perm,
        tree_start,
        2 * n,
        command_budget=69 * n + 44 - len(header) - _ASCII_ZERO - 1,
        bank=bank,
    )
    if shared is not None:
        body, commands = shared
        candidate = header + body + "+" * _ASCII_ZERO + "."
        if len(header) + commands + _ASCII_ZERO + 1 <= 69 * n + 44 and len(
            candidate
        ) < len(plain):
            plain = candidate
    if bank and perm == tuple(range(n)):
        binary = binary_bank(truth_table, 69 * n + 44 - len(header) - _ASCII_ZERO - 1)
        if binary is not None:
            body, _ = binary
            candidate = header + body + "+" * _ASCII_ZERO + "."
            if len(candidate) < len(plain):
                plain = candidate
        larger = larger_suffix_bank(
            truth_table, 69 * n + 44 - len(header) - _ASCII_ZERO - 1
        )
        if larger is not None:
            body, _ = larger
            candidate = header + body + "+" * _ASCII_ZERO + "."
            if len(candidate) < len(plain):
                plain = candidate
    return plain


LANGUAGE = Language(
    "brainfuck",
    "tape_based.brainfuck",
    weekly_mutation=("interpreter",),
    boolean=brainfuck,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
)
