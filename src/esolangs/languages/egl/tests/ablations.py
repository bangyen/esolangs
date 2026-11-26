"""Independent EGL rows with the block layout disabled."""

from typing import Literal

from esolangs.generation.projection import input_weights, symmetric_lookup


def _grid(weights: list[int], table: str, *, folded: bool) -> str:
    m = len(table).bit_length() - 1
    columns = 1 << min(m, (m + 3) // 2) if folded else len(table)
    rows = len(table) // columns
    parts = [f"{columns},{3 * rows}:vv"]
    for r in range(rows):
        bits = table[r * columns : (r + 1) * columns]
        bits = bits if r % 2 == 0 else bits[::-1]
        parts.append((">" if r % 2 == 0 else "<").join("+" * int(b) for b in bits))
        if r + 1 != rows:
            parts.append("vvv")
    parts.append("%^<" if rows == 1 else "_^")
    for weight in weights:
        if weight == 0:
            parts.append("x")
        else:
            walk = ">" * weight if weight < columns else "v" * (3 * weight // columns)
            parts.append("xv++++++(-^--------v)^(-" + walk + ")")
    return "".join(parts) + "vv="


def ablate(table: str, rule: Literal["default", "folded_rows"]) -> str:
    """Return the binary/count reader with or without three-row blocks."""
    n = len(table).bit_length() - 1
    if len(set(table)) == 1:
        return "2,1:" + "x" * n + ">" + "+" * int(table[0]) + "="
    projected = input_weights(table, n)
    builds = (projected, symmetric_lookup(projected))
    return min(
        (
            _grid(*build, folded=k == 0 and rule == "default")
            for k, build in enumerate(builds)
            if build is not None
        ),
        key=len,
    )
