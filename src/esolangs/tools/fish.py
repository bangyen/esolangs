"""Fish boolean generator: a grid table read with ``g``."""

from esolangs.tools.helpers import _validate_truth_table


def fish(truth_table: str, width: int | None = None) -> str:
    """Return a Fish lookup grid; folded execution needs three columns."""
    n = _validate_truth_table(truth_table)
    # Read ASCII bits, fold the row number, then fetch the digit below.
    header = "0" + "i68*-$2*+" * n + "1g68*-n;"
    plain = header + "\n" + truth_table
    if width is None or width <= 0 or max(len(header), len(truth_table)) <= width:
        return plain
    columns = 1 << (min(max(1, width - 2), len(truth_table)).bit_length() - 1)
    divisor = "1" + "2*" * (columns.bit_length() - 1)
    body = "0" + "i68*-$2*+" * n + ":" + divisor + "%$:" + divisor + "%-"
    body += divisor + ","
    # Reserve a power-of-two height: its doubling literal fits even at width 3.
    height = 1 << (2 * len(body) // columns + 32).bit_length()
    body += "1" + "2*" * (height.bit_length() - 1) + "+g68*-n;"
    rows: list[str] = []
    for offset in range(0, len(body), columns):
        chunk = body[offset : offset + columns].ljust(columns)
        rows.append(
            ">" + chunk + "v" if len(rows) % 2 == 0 else "v" + chunk[::-1] + "<"
        )
    rows.extend([""] * (height - len(rows)))
    rows.extend(
        truth_table[offset : offset + columns]
        for offset in range(0, len(truth_table), columns)
    )
    return "\n".join(rows)
