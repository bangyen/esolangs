"""Retired constructions, kept as oracles for the generators that replaced them.

These emitted production programs once.  The generators now reach the same
output through one construction each -- Polynomial's family at ``k == n``,
Sophie's hybrid -- and the tests assert that identity.  Deriving the oracle
from the code it is meant to justify would check that code against itself, so
the retired builds live here, where nothing ships them.

Their cost functions are *not* kept: those existed to choose between the
constructions without building them, and there is no longer a choice to make.
"""

# These independent construction oracles deliberately mirror generated programs.
# pylint: disable=duplicate-code

from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table
from esolangs.tools.boolean.register import _SOPHIE_BANDS, _polynomial_states


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

    def emit_delta(delta: int) -> None:
        if delta > 0:
            instrs.append([delta, 1])
        # The tree walks the accumulator up from zero and every answer is 0
        # or 1, so the deltas the builder emits are never negative; the
        # subtract instruction is here for a builder that needs one.
        elif delta < 0:  # pragma: no cover - the tree only ever steps upward
            instrs.append([-delta, 2])

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
            # are left on the input stream.
            for _ in range(bit, n):
                instrs.extend([[0, 2], [_ASCII_ZERO, 2]])  # input; -= 48
            emit_delta(1)  # reg back to nonzero so the enclosing else skips
            return
        instrs.extend([[0, 2], [_ASCII_ZERO, 2]])  # input; -= 48
        g1 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 1]
        g0 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 0]
        instrs.append([1])  # if reg > 0 -> the one-bit subtree
        build(g1, bit + 1, 1)
        instrs.append([2])
        instrs.append([4])  # if reg == 0 -> the zero-bit subtree
        build(g0, bit + 1, 0)
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
    """Emit the state-machine Sophie program; see :func:`sophie`.

    Each level is a *flat chain* of ``@$L{...}`` blocks, one per live state,
    and the read happens inside whichever block fires.  Nesting the blocks
    would restate the tree -- what makes this a DAG is that two prefixes
    leaving the same residual subfunction get the same label and so the same
    block.

    Re-fire needs no arithmetic here, unlike :func:`_polynomial_dag`: Sophie
    tests equality against an arbitrary literal, so consecutive levels
    drawing labels from disjoint bands is enough.  A fired block leaves the
    accumulator holding a *next*-level label, which no remaining test in the
    current chain can match.

    Level 0 has one state and the accumulator starts at 0, so its dispatch is
    skipped.  Leaves halt inside their block, so the last level cannot
    re-fire whatever the labels.
    """
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
