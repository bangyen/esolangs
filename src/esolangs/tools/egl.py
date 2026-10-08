"""Boolean-function generator for EGL."""

from esolangs.tools.helpers import _validate_truth_table, input_weights


def egl(truth_table: str, width: int | None = None) -> str:
    """Build an EGL program computing ``truth_table``.

    Row 1 of a two-row grid holds the table, one cell an entry; ``%`` sends
    ``(1, T - 1)`` to ``(1, 1)`` and ``^<`` on to the origin.  Row 0 is
    scratch: each input is read under the pointer and its ``(-...)`` guard,
    run once exactly when the bit is 1, walks right by the input's Horner
    weight, so the weights accumulate into the index with no branch per
    level, and ``v=`` prints the cell below.  An ignored input is a bare
    ``x`` the next read overwrites, and the table is indexed by the rest.  A
    constant keeps its full table: one cell leaves ``^<`` no room.
    """
    n = _validate_truth_table(truth_table)
    weights, projected = input_weights(truth_table, n)
    if any(weights):
        truth_table = projected
    else:
        weights = [1 << (n - 1 - index) for index in range(n)]
    size = len(truth_table)

    # Paint row 1 left to right, then fold both axes back to the origin.
    cells = ["+" if bit == "1" else "" for bit in truth_table]
    pieces = [f"{size},2:", "v", ">".join(cells), "%^<"]

    # One read and one weighted guard an input; the weights sum to T - 1.
    pieces += [f"x{'-' * 48}(-{'>' * weight})" if weight else "x" for weight in weights]
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
