"""Fish boolean generator: a grid table read with ``g``.

A grid has no subtrees to fold or share.
"""

from math import isqrt

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape
from esolangs.tools.helpers import _parity_bias, _validate_truth_table, input_weights


def fish(truth_table: str, width: int | None = None) -> str:
    """Return a Fish lookup grid; lookup folds need three columns; parity uses one."""
    n = _validate_truth_table(truth_table)
    if width is not None and 0 < width < 3:
        bias = _parity_bias(truth_table)
        if bias is not None:
            # ASCII zero is even, so sums modulo two already normalize inputs.
            header = "vi" + "i+" * (n - 1) + "2%" + ("0=" if bias else "") + "n;"
            return "\n".join(header)
    # Read ASCII bits, fold the row number, then fetch the digit below; an
    # ignored input is read and popped, and the table indexes the rest.
    weights, truth_table = input_weights(truth_table, n)
    reads = "".join("i68*-$2*+" if weight else "i~" for weight in weights)
    header = "0" + reads + "1g68*-n;"
    plain = header + "\n" + truth_table
    if width is None or width <= 0 or max(len(header), len(truth_table)) <= width:
        return plain
    columns = 1 << (min(max(1, width - 2), len(truth_table)).bit_length() - 1)
    divisor = "1" + "2*" * (columns.bit_length() - 1)
    body = "0" + reads + ":" + divisor + "%$:" + divisor + "%-"
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


def balance_fish(truth_table: str, default: str) -> str:
    """Minimize imbalance over Fish's power-of-two folds and parity column.

    Each padding height h gives W=c+2, H=h+T/c. Its crossing is quadratic;
    padding boundaries lie within two powers of the header's constant part.
    """
    n = _validate_truth_table(truth_table)
    size = len(truth_table)
    # Before the height literal, the header has B=9n+11+6k cells for c=2^k.
    # A <= 2B < 2A for A=18n+22 and 0<=k<=n, bounding each padding transition.
    constant = 18 * n + 22
    maximum = 1 << (constant + 32).bit_length()
    exponents = {0, n}
    for power in range(6, maximum.bit_length()):
        height = 1 << power
        root = (height - 2 + isqrt((height - 2) ** 2 + 4 * size)) // 2
        crossing = root.bit_length() - 1
        exponents.update((crossing, crossing + 1))
        for threshold in (height - 32, height // 2 - 32):
            if threshold > 0:
                boundary = max(0, (constant // threshold).bit_length() - 1)
                exponents.update((boundary, boundary + 1, boundary + 2))
    from esolangs.tools.wrap import balance_score

    candidates = [default]
    candidates.extend(
        fish(truth_table, (1 << exponent) + 2)
        for exponent in sorted(exponents)
        if 0 <= exponent <= n
    )
    if _parity_bias(truth_table) is not None:
        candidates.append(fish(truth_table, 1))
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Fish",
    "grid_based.fish",
    boolean=fish,
    # Not a tree: an indexed table read, not a tree.
    shape=Shape.LOOKUP,
    split=True,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    balance=balance_fish,
    no_wrap="a row is a codebox row and the lookup table is indexed by column",
    eof="an exhausted 'i' is the spec's -1",
    empty_program="Fish program cannot be empty",
)
