"""Retired constructions, kept as oracles for the generators that replaced them."""

# These independent construction oracles deliberately mirror generated programs.
# pylint: disable=duplicate-code

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table
from esolangs.tools.polynomial import _polynomial_states

#: Label bands for the *pure* DAG below, which the shipped generator no
#: longer shares.
#:
#: Two bands by level parity are enough here and were not enough there, and
#: the difference is inlining.  This emits one block per state at every
#: level, in level order, so every jump goes from level k to level k + 1 and
#: the accumulator only ever holds a next-level label while control is
#: passing the current level's blocks -- which draw from the other band.
#: The shipped generator inlines unshared states, so one top-level block
#: carries jumps originating at many depths, two same-parity levels are both
#: targets from inside it, and the earlier one fires first.  See
#: :func:`~esolangs.tools.sophie.sophie_labels`.
_SOPHIE_BANDS = ((1, 20), (21, 40))


def _polynomial_tree(truth_table: str) -> list[list[int]]:
    """Emit the decision-tree instructions; see :func:`polynomial`."""
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


def _sophie_tree(truth_table: str) -> str:
    """Emit the nested-branch Sophie program; see :func:`sophie`."""
    n = _validate_truth_table(truth_table)

    def build(path: list[int]) -> str:
        depth = len(path)
        row = 0
        for bit in path:
            row = row * 2 + bit
        # A short path has its unconsumed bits still to come, so it names
        # the start of the run they span rather than a row outright.
        row <<= n - depth
        if depth == n or len(set(truth_table[row : row + 2 ** (n - depth)])) == 1:
            # Sophie reads inside the tree -- a node is ``;`` then its
            # branch -- so a folded leaf still spends the reads it skipped.
            # A program whose input count depended on its table would
            # desync a caller feeding several programs from one stream.
            reads = ";" * (n - depth)
            return f"{reads}#${_ASCII_ZERO + int(truth_table[row])},&"
        return ";" + "@$48{" + build([*path, 0]) + "}" + "{" + build([*path, 1]) + "}"

    return build([])


def _sophie_dag(truth_table: str) -> str:
    """Emit the state-machine Sophie program; see :func:`sophie`."""
    n = _validate_truth_table(truth_table)
    levels = _polynomial_states(truth_table, n)

    def label(level: int, state: str) -> int:
        return _SOPHIE_BANDS[level % 2][0] + levels[level].index(state)

    out: list[str] = []
    for k in range(n):
        width = 2 ** (n - k - 1)
        blocks: list[str] = []
        for state in levels[k]:
            zero, one = state[:width], state[width:]
            if k + 1 == n:
                # The children are single characters -- the answers.
                body = (
                    f";@$48{{#${_ASCII_ZERO + int(zero)},&}}"
                    f"{{#${_ASCII_ZERO + int(one)},&}}"
                )
            elif zero == one:
                # Merged children: this bit cannot change the answer, so the
                # read still happens and the label is set unconditionally.
                body = f";#${label(k + 1, zero)}"
            else:
                body = f";@$48{{#${label(k + 1, zero)}}}{{#${label(k + 1, one)}}}"
            blocks.append(body if k == 0 else f"@${label(k, state)}{{{body}}}")
        out.append("".join(blocks))
    return "".join(out)
