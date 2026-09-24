"""Boolean-function generator for EGL."""

from esolangs.tools.helpers import _validate_truth_table


def egl(truth_table: str, width: int | None = None) -> str:
    """Build an EGL program computing ``truth_table``.

    The grid is two rows of ``T`` cells.  Row 1 is painted with the table,
    one cell an entry, and ``%`` folds the painter back to the origin.  Row 0
    is a scratch track: each input is read onto the cell under the pointer and
    its ``(-...)`` guard, which runs once exactly when the bit is 1, walks the
    pointer right by that input's Horner weight.  The guard leaves the pointer
    wherever its body stopped, so the weights accumulate into the row index
    with no branch per level, and ``v=`` prints the cell below.
    """
    n = _validate_truth_table(truth_table)
    size = len(truth_table)

    # Paint row 1 left to right, then fold both axes back to the origin.
    cells = ["+" if bit == "1" else "" for bit in truth_table]
    pieces = [f"{size},2:", "v", ">".join(cells), "%"]

    # One read and one weighted guard an input; the weights sum to T - 1.
    pieces += [f"x(-{'>' * (1 << (n - 1 - index))})" for index in range(n)]
    pieces.append("v=")

    program = "".join(pieces)
    if width is None:
        return program
    header, rest = program.split(":", 1)
    header += ":"
    room = max(1, width)
    first = max(0, room - len(header))
    rows = [header + rest[:first]]
    rows.extend(rest[start : start + room] for start in range(first, len(rest), room))
    return "\n".join(rows)
