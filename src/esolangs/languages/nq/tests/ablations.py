"""Independent spelling of the NQ tree with isolated canonical ablations."""

from typing import Literal

from esolangs.generation.helpers import _validate_truth_table, subtree_ids


def ablate(
    table: str, rule: Literal["default", "constant_fold", "ignored_input"]
) -> str:
    """Disable exactly one fold, leaving input consumption intact."""
    n = _validate_truth_table(table)
    if rule != "constant_fold" and table.count(table[0]) == len(table):
        return "+" + ("2" if table[0] == "1" else "0") + "r" * n + "WH"
    bias = int(table[0])
    parity = all(
        int(bit) == ((row.bit_count() & 1) ^ bias) for row, bit in enumerate(table)
    )
    ids = subtree_ids(table)
    chunks: list[str] = []

    def emit(depth: int, k: int) -> None:
        node = ids[depth][k]
        if depth == n or (node < 2 and rule != "constant_fold"):
            chunks.extend(("r-" * (n - depth), "+2WH" if node else "+0WH"))
            return
        chunks.append("r-")
        if parity and depth + 1 == n:
            zero, one = ids[n][2 * k], ids[n][2 * k + 1]
            chunks.extend((f">1+{2 * one}", f">0+{2 * zero}", "WH"))
            return
        if (
            node >= 2
            and rule != "ignored_input"
            and ids[depth + 1][2 * k] == ids[depth + 1][2 * k + 1]
        ):
            emit(depth + 1, 2 * k)
        else:
            chunks.append(">1(")
            emit(depth + 1, 2 * k + 1)
            chunks.append(")")
            emit(depth + 1, 2 * k)

    emit(0, 0)
    return "".join(chunks)
