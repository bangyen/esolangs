"""Independent retained Polynomial decision-tree construction."""

# These independent construction oracles deliberately mirror generated programs.
# pylint: disable=duplicate-code

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table


def _polynomial_tree(truth_table: str) -> list[list[int]]:
    """Emit the decision-tree instructions; see :func:`polynomial`.

    The generator emits this as ``_polynomial_hybrid`` at ``k == n``; this
    is the independent build that claim is checked against.

    A subtree whose rows are all the same value collapses to its single
    output, so constant and near-constant tables skip the tree that would
    otherwise isolate every leaf.  A collapsed leaf still drains the reads
    its untaken siblings would have made, so every path consumes ``n``.
    """
    n = _validate_truth_table(truth_table)
    instrs: list[list[int]] = []
    # Every arm leaves the register at or below this, so the ``+= 1; if > 0``
    # that guards the zero-bit arm never fires after a taken one-bit arm:
    # each level out adds one and there are at most ``n`` of them.
    park = n + 2

    def emit_delta(delta: int) -> None:
        # Subtraction is spelled ``+=`` with a negative operand: ``-=`` is
        # ``p**4`` where ``+=`` is ``p**2``.
        if delta:
            instrs.append([delta, 1])

    def build(rows: list[int], bit: int, last: int) -> None:
        vals = {truth_table[r] for r in rows}
        if len(vals) == 1:
            v = int(vals.pop())
            emit_delta(_ASCII_ZERO + v - last)
            instrs.append([0, 1])  # output
            # Drain the reads the untaken siblings would have made, *after*
            # printing so they cannot disturb the value being output: an
            # input-capable language reads each of its n inputs exactly once
            # per run whatever the table says, or the caller's remaining bits
            # are left on the input stream.  A bare read suffices; the park
            # below overwrites whatever it left.
            for _ in range(bit, n):
                instrs.append([0, 2])
            emit_delta(-(_ASCII_ZERO + 1 + park))
            return
        instrs.extend([[0, 2], [-_ASCII_ZERO, 1]])  # input; += -48
        g1 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 1]
        g0 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 0]
        instrs.append([1])  # if reg > 0 -> the one-bit subtree
        build(g1, bit + 1, 1)
        instrs.append([2])
        instrs.append([1, 1])  # += 1: a zero bit reads 1, a taken arm <= -1
        instrs.append([1])  # if reg > 0 -> the zero-bit subtree
        build(g0, bit + 1, 1)
        instrs.append([2])

    build(list(range(2**n)), 0, 0)
    return instrs
