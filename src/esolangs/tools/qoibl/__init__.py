"""Boolean generator for qoibl.

A packed literal has no subtrees to fold or share.
"""

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table, input_weights

__all__ = ["qoibl"]


def _qoibl_enc(n: int) -> str:
    """Qoibl binary literal for ``n`` (e is 0, y is 1)."""
    return f"{n:b}".replace("0", "e").replace("1", "y")


def qoibl(truth_table: str, width: int | None = None) -> str:
    """Build a Qoibl program computing the given truth table.

    ``truth_table`` has length ``2**n``, most significant input first.  The
    whole table rides in one binary literal, bit ``k`` holding row ``k``, so
    ``table // 2**index`` then ``r - 2 * (r // 2)`` reads that row off.
    """
    n = _validate_truth_table(truth_table)
    # An ignored input is read into ``p`` until the first essential read sets
    # it, then into ``row``, which the packed literal overwrites: it costs no
    # variable, and the table is packed over the rest.  It is stored as the
    # bit plus one: a raw 49 beside a live ``p`` broke the workspace bound
    # (17 > 16 bits on ``00111100``).
    weights, projected = input_weights(truth_table, n)
    if any(weights):
        truth_table = projected
    else:
        # A constant still needs the first read to set ``p``, so the first input
        # stands as a two-row table; the rest are ignored reads.
        weights = [1] + [0] * (n - 1)
        truth_table = truth_table[0] * 2
    # Variables 0 and 1; variable 2 is the Horner scratch when narrow.
    power = _qoibl_enc(0)
    row = _qoibl_enc(1)
    zero = _qoibl_enc(_ASCII_ZERO)
    packed = sum(int(bit) << index for index, bit in enumerate(truth_table))

    # ``p = p * (p * (et - 47))``: the digit is 48 or 49, so that factor is
    # the bit plus one and squaring makes the reads Horner's rule.  Essential,
    # not an optimisation: the operators are + - * / only, so ``p`` must reach
    # ``2**index`` by squaring for the packed literal's division.
    bit = f"et ry ey ry {_qoibl_enc(_ASCII_ZERO - 1)}"
    lines = []
    counted = False
    for weight in weights:
        if not weight:
            lines.append(f"we {row if counted else power} we {bit} we")
        elif counted:
            lines.append(
                f"we {power} we qe {power} qe ry ye ry qe {power} qe ry ye ry {bit} we"
            )
        else:
            lines.append(f"we {power} we {bit} we")
            counted = True
    lines.append(f"we {row} we {_qoibl_enc(packed)} ry yy ry qe {power} qe we")
    lines.append(
        f"tt qe {row} qe ry ee ry {zero} ry ey ry ye ry ye ry "
        f"qe {row} qe ry yy ry ye tt"
    )
    program = "\n".join(lines)
    if width is None or width <= 0:
        return program
    from esolangs.tools.wrap import _qoibl

    # Fits as-is: no Horner expansion needed.
    wrapped = _qoibl(program, width)
    if max(map(len, wrapped.splitlines())) <= width:
        return wrapped
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
    return _qoibl("\n".join(output), limit)
