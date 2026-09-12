r"""Retired constructions, kept as oracles for the generators that."""

# pylint: disable=duplicate-code
# pylint: disable=duplicate-code

from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table
from esolangs.tools.boolean.register import _polynomial_states

# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
_SOPHIE_BANDS = ((1, 20), (21, 40))


def _polynomial_tree(truth_table: str) -> list[list[int]]:
    r"""Emit the decision-tree instructions; see :func:`polynomial`."""
    n = _validate_truth_table(truth_table)
    instrs: list[list[int]] = []

    def emit_delta(delta: int) -> None:
        if delta > 0:
            instrs.append([delta, 1])
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        elif delta < 0:  # pragma: no cover - the tree only ever steps upward
            instrs.append([-delta, 2])

    def build(rows: list[int], bit: int, last: int) -> None:
        vals = {truth_table[r] for r in rows}
        if len(vals) == 1:
            v = int(vals.pop())
            emit_delta(_ASCII_ZERO + v - last)
            instrs.append([0, 1])  # output.
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            for _ in range(bit, n):
                instrs.extend([[0, 2], [_ASCII_ZERO, 2]])  # input; -= 48.
            emit_delta(1)  # reg back to nonzero so the.
            return
        instrs.extend([[0, 2], [_ASCII_ZERO, 2]])  # input; -= 48.
        g1 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 1]
        g0 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 0]
        instrs.append([1])  # if reg > 0 -> the one-bit.
        build(g1, bit + 1, 1)
        instrs.append([2])
        instrs.append([4])  # if reg == 0 -> the zero-bit.
        build(g0, bit + 1, 0)
        instrs.append([2])

    build(list(range(2**n)), 0, 0)
    return instrs


def _sophie_tree(truth_table: str) -> str:
    r"""Emit the nested-branch Sophie program; see :func:`sophie`."""
    n = _validate_truth_table(truth_table)

    def build(path: list[int]) -> str:
        depth = len(path)
        row = 0
        for bit in path:
            row = row * 2 + bit
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        row <<= n - depth
        if depth == n or len(set(truth_table[row : row + 2 ** (n - depth)])) == 1:
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            reads = ";" * (n - depth)
            return f"{reads}#${_ASCII_ZERO + int(truth_table[row])},&"
        return ";" + "@$48{" + build([*path, 0]) + "}" + "{" + build([*path, 1]) + "}"

    return build([])


def _sophie_dag(truth_table: str) -> str:
    r"""Emit the state-machine Sophie program; see :func:`sophie`."""
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
                # pylint: disable=duplicate-code
                body = (
                    f";@$48{{#${_ASCII_ZERO + int(zero)},&}}"
                    f"{{#${_ASCII_ZERO + int(one)},&}}"
                )
            elif zero == one:
                # pylint: disable=duplicate-code
                # pylint: disable=duplicate-code
                body = f";#${label(k + 1, zero)}"
            else:
                body = f";@$48{{#${label(k + 1, zero)}}}{{#${label(k + 1, one)}}}"
            blocks.append(body if k == 0 else f"@${label(k, state)}{{{body}}}")
        out.append("".join(blocks))
    return "".join(out)
