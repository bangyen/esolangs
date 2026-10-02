"""Boolean generator for qoibl."""

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["qoibl"]


def _qoibl_enc(n: int) -> str:
    """Qoibl binary literal for ``n`` (e is 0, y is 1)."""
    return f"{n:b}".replace("0", "e").replace("1", "y")


_QOIBL_POWER, _QOIBL_ROW = 0, 1


def qoibl(truth_table: str, width: int | None = None) -> str:
    """Build a Qoibl program computing the given truth table.

    ``truth_table`` has length ``2**n``, most significant input first.  The
    Whole-table literals expand into O(T) binary Horner steps when narrow.
    The whole table rides in one binary literal, bit ``k`` holding row ``k``, so
    ``table // 2**index`` then ``r - 2 * (r // 2)`` reads that row off.
    """
    n = _validate_truth_table(truth_table)
    power = _qoibl_enc(_QOIBL_POWER)
    row = _qoibl_enc(_QOIBL_ROW)
    zero = _qoibl_enc(_ASCII_ZERO)
    packed = sum(int(bit) << index for index, bit in enumerate(truth_table))

    # ``p = p * (p * (et - 47))``: the digit is 48 or 49, so that factor is
    # the bit plus one and squaring makes the reads Horner's rule.
    bit = f"et ry ey ry {_qoibl_enc(_ASCII_ZERO - 1)}"
    lines = [f"we {power} we {bit} we"]
    lines += (n - 1) * [
        f"we {power} we qe {power} qe ry ye ry qe {power} qe ry ye ry {bit} we"
    ]
    lines.append(f"we {row} we {_qoibl_enc(packed)} ry yy ry qe {power} qe we")
    lines.append(
        f"tt qe {row} qe ry ee ry {zero} ry ey ry ye ry ye ry "
        f"qe {row} qe ry yy ry ye tt"
    )
    program = "\n".join(lines)
    if width is None or width <= 0:
        return program
    from esolangs.tools.wrap import _qoibl, wrap_space_delimited

    previous = _qoibl(program, width)
    if max(map(len, previous.splitlines())) <= width:
        return previous
    limit = max(2, width)
    output: list[str] = []
    scratch = _qoibl_enc(2)
    for line in lines:
        tokens = line.split()
        for at, token in enumerate(tokens):
            if len(token) <= limit:
                continue
            # Each statement has one long literal. Binary Horner steps use
            # spare variable 2; separate multiply/add respect right association.
            chunks = [token[i : i + limit - 1] for i in range(0, len(token), limit - 1)]
            output.append(f"we {scratch} we {chunks[0]} we")
            for chunk in chunks[1:]:
                factor = _qoibl_enc(1 << len(chunk))
                output.append(f"we {scratch} we qe {scratch} qe ry ye ry {factor} we")
                output.append(f"we {scratch} we qe {scratch} qe ry ee ry {chunk} we")
            tokens[at] = f"qe {scratch} qe"
        output.append(" ".join(tokens))
    return "\n".join(wrap_space_delimited(line, limit) for line in output)
