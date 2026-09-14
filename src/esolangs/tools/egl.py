"""Boolean-function generator for EGL."""

from esolangs.tools.helpers import _validate_truth_table


def egl(truth_table: str, width: int | None = None) -> str:
    """Build an EGL program computing ``truth_table``.

    Each input becomes adjacent ``not-bit`` and ``bit`` one-hot cells.  A
    folded decision tree consumes exactly one of those cells at each level;
    its selected leaf prints from the otherwise-unused final cell.
    """
    n = _validate_truth_table(truth_table)
    origin = 3 * n

    # At X,N,P = input,1,0, the loop maps 0 -> 0,1,0 and 1 -> 0,0,1.
    reads = "".join("x>+<(>>+<-<-)>>>" for _ in range(n))

    def guard(cell: int, body: str) -> str:
        distance = origin - cell
        left, right = "<" * distance, ">" * distance
        return left + "(-" + right + body + left + ")" + right

    def tree(table: str, depth: int) -> str:
        if table == table[0] * len(table):
            return "+=-" if table[0] == "1" else "="
        half = len(table) // 2
        zero = guard(3 * depth + 1, tree(table[:half], depth + 1))
        one = guard(3 * depth + 2, tree(table[half:], depth + 1))
        return zero + one

    header = f"{origin + 1},1:"
    body = reads + tree(truth_table, 0)
    if width is None:
        return header + body
    room = max(1, width)
    first = max(0, room - len(header))
    rows = [header + body[:first]]
    rows.extend(body[start : start + room] for start in range(first, len(body), room))
    return "\n".join(rows)
