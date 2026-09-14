"""Boolean-function generator for EGL."""

from esolangs.tools.helpers import _validate_truth_table, best_input_order


def _egl_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Build EGL for one tree order, keeping reads in stream order."""
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
        cell = 3 * perm[depth]
        zero = guard(cell + 1, tree(table[:half], depth + 1))
        one = guard(cell + 2, tree(table[half:], depth + 1))
        return zero + one

    return f"{origin + 1},1:" + reads + tree(truth_table, 0)


def egl(truth_table: str, width: int | None = None) -> str:
    """Build an EGL program computing ``truth_table``.

    Each input becomes adjacent ``not-bit`` and ``bit`` one-hot cells.  A
    folded decision tree consumes exactly one of those cells at each level;
    its selected leaf prints from the otherwise-unused final cell.
    """
    program = best_input_order(truth_table, _egl_ordered)
    if width is None:
        return program
    header, body = program.split(":", 1)
    header += ":"
    room = max(1, width)
    first = max(0, room - len(header))
    rows = [header + body[:first]]
    rows.extend(body[start : start + room] for start in range(first, len(body), room))
    return "\n".join(rows)
