"""Boolean-function generator for EGL."""

from esolangs.tools.helpers import (
    _validate_truth_table,
    best_input_order,
    constant_span_test,
)


def _egl_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Build EGL for one tree order, keeping reads in stream order."""
    n = _validate_truth_table(truth_table)
    origin = 3 * n

    # At X,N,P = input,1,0, the loop maps 0 -> 0,1,0 and 1 -> 0,0,1.
    reads = "".join("x>+<(>>+<-<-)>>>" for _ in range(n))

    # Spans, an O(1) constant test and one flat piece list: O(2**n).
    constant = constant_span_test(truth_table)
    pieces = [f"{origin + 1},1:", reads]

    def guard(cell: int, lo: int, hi: int, depth: int) -> None:
        distance = origin - cell
        left, right = "<" * distance, ">" * distance
        pieces.append(left + "(-" + right)
        tree(lo, hi, depth)
        pieces.append(left + ")" + right)

    def tree(lo: int, hi: int, depth: int) -> None:
        if constant(lo, hi):
            pieces.append("+=-" if truth_table[lo] == "1" else "=")
            return
        mid = (lo + hi) // 2
        cell = 3 * perm[depth]
        guard(cell + 1, lo, mid, depth + 1)
        guard(cell + 2, mid, hi, depth + 1)

    tree(0, len(truth_table), 0)
    return "".join(pieces)


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
