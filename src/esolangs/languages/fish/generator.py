"""Fish Boolean program generator: the truth table sits in the codebox.

Plain lookup normalizes ASCII bits with ``68*-`` and folds them into a row
(``$2*+``). Packed lookup instead folds raw ASCII from -48, leaving row-48;
coordinate offsets restore the address. ``g`` reads and ``n`` prints.
For table 0010 at n=2 and width=80:

    0i68*-$2*+i68*-$2*+1g68*-n;
    0010

Narrow widths fold the table into a block of columns, which the fish reaches
by snaking down.  A parity table needs no table at all, and another symmetric
one adds its bits over m + 1 entries ([ablations.symmetric_count]).  From n=3 the
generic default is one row while coordinates are exact: the code, six powers of
two, and six entries a cell ([ablations.packed_row]).

Size:
    O(T) generic default: about T/6 cells while packed coordinates are exact,
    then 2T cells with integer addressing; n=16 parity: 71 chars,
    n=10 random 1847: 267 chars.
    Constants use 2n+3 cells/commands in one row, with
    7+bl(2n+3)+bl(n) written bits; narrow requests snake or use one column.

Decisions:
    A table has no subtrees to fold or share.  ``balance=True`` also folds the
    packed row into a snake over a block of cells
    ([ablations.balance_packed_fold]). Beyond binary64 coordinate precision,
    plain lookup or integer-coordinate folds preserve correctness.
"""

from math import isqrt

from esolangs.generation.algebraic import parity_bias
from esolangs.generation.helpers import (
    _validate_truth_table,
    grid_rank,
    input_weights,
    symmetric_weights,
)
from esolangs.generation.wrap import balance_score


def fish(truth_table: str, width: int | None = None) -> str:
    """Return a Fish lookup grid; lookup folds need three columns; parity uses one."""
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        return _constant(n, truth_table[0], width)
    # A one-column parity program fits any width; at n=10 it is 24 cells
    # against the lookup's 2,050 (default) and 3,435 (width 3).
    bias = parity_bias(truth_table)
    if bias is not None:
        return _parity(n, bias)
    # An ignored input is read and dropped; the table indexes the rest.
    original = truth_table
    weights, truth_table = input_weights(truth_table, n)
    reads = "".join("i68*-$2*+" if weight else "i~" for weight in weights)
    header = "0" + reads + "1g68*-n;"
    if width is None:
        plain, packed = header + "\n" + truth_table, _packed(reads, truth_table)
        symmetric = symmetric_weights(original, n)
        if symmetric is not None:
            # A symmetric table adds its bits and indexes m + 1 entries
            # ([ablations.symmetric_count]).
            counts = "".join(
                "i68*-+" if weight else "i~" for weight in symmetric.weights
            )
            plain = "0" + counts + "1g68*-n;\n" + symmetric.table
        # Area decides; packing can cost more text at low arities.
        return min(packed, plain, key=grid_rank)
    if max(len(header), len(truth_table)) <= width:
        return header + "\n" + truth_table
    columns = 1 << (min(max(1, width - 2), len(truth_table)).bit_length() - 1)
    return _folded(reads, truth_table, columns)


def _constant(inputs: int, bit: str, width: int | None) -> str:
    """Read/drop each byte, print the digit, and halt; fold only when needed."""
    code = "i~" * inputs + bit + "n;"
    if width is None or len(code) <= width:
        return code
    if width < 3:
        return "\n".join("v" + code)
    payload = width - 2
    rows = []
    for row, offset in enumerate(range(0, len(code), payload)):
        part = code[offset : offset + payload].ljust(payload)
        rows.append(">" + part + "v" if row % 2 == 0 else "v" + part[::-1] + "<")
    return "\n".join(rows)


#: Table entries a packed cell carries, and the code of its all-ones word:
#: 64 printable codes from 35 skip DEL ([ablations.packed_row]).
_WORD = 6
_BASE = 35
#: Every integer up to this magnitude is exact in the division result.
_EXACT = 1 << 53


def _column(least: int) -> tuple[int, str]:
    """Return the first closed-form column at or past ``least`` and its literal.

    ``f*k`` reaches 225 in three characters; past it, a power of two.
    """
    k = -(-least // 15)
    if k <= 15:
        return 15 * k, f"f{k:x}*"
    m = least.bit_length()
    return 1 << m, "1" + "2*" * m


def _packed_reads(reads: str) -> str:
    """Leave row-48: each ASCII read cancels one doubled -48 offset."""
    return "068*-" + reads.replace("i68*-$2*+", "2*i+")


def _packed(reads: str, truth_table: str) -> str:
    """Return one row: the code, then six powers of two, then the packed table.

    Cell ``q`` holds entries ``6q`` to ``6q + 5`` complemented, so the row
    splits into the cell and a bit ``b``; the cell over ``2**b``, mod 2, is
    under 1 exactly when the entry is 1.  The cells sit past ``;``, unrun.
    """
    # The raw index is r-48: mod6 is unchanged, quotient is q-8.
    head = f"{_packed_reads(reads)}:{_WORD}%:@-{_WORD},"
    # ``57*`` is _BASE, ``88*`` the powers' 64.
    # 14 = the six power cells plus the eight-word coordinate offset.
    middle, tail = "e++0g57*-$", "+0g88*-,2%1(n;"
    bare = len(head) + len(middle) + len(tail)
    # The literal appears twice, and its length can move the column.
    start, literal = _column(bare + 6)
    if bare + 2 * len(literal) > start:
        start, literal = _column(bare + 2 * len(literal))
    code = head + literal + middle + literal + tail
    # Both the converted offset and every float coordinate must stay exact.
    if max(start + 14, start + 6 + (len(truth_table) - 1) // _WORD) > _EXACT:
        return "0" + reads + "1g68*-n;\n" + truth_table
    cells = "".join(
        chr(_BASE + sum((ch == "0") << j for j, ch in enumerate(word)))
        for word in (
            truth_table[i : i + _WORD] for i in range(0, len(truth_table), _WORD)
        )
    )
    powers = "".join(chr(64 + (1 << bit)) for bit in range(_WORD))
    return code.ljust(start) + powers + cells


def _parity(n: int, bias: int) -> str:
    """Return the sum of the inputs mod 2, one command per row.

    ASCII ``0`` is even, so the characters' sum already has the bits' parity.
    """
    return "\n".join("vi" + "i+" * (n - 1) + "2%" + ("0=" if bias else "") + "n;")


def _integer_coordinates(reads: str, columns: int) -> str:
    """Split essential bits at a power-of-two column into integer coordinates."""
    tokens = ["i" + part for part in reads.split("i")[1:]]
    count = sum(token != "i~" for token in tokens)
    high = max(0, count - (columns.bit_length() - 1))
    code = ["0"]
    done = 0
    split = False
    for token in tokens:
        if token != "i~":
            if done == high and not split:
                code.append("0")
                split = True
            done += 1
        code.append(token)
    if not split:
        code.append("0")
    return "".join(code) + "$"


def _folded(reads: str, truth_table: str, columns: int) -> str:
    """Return the program as a snake of ``columns`` cells over the table's block.

    Row ``r`` of the block holds entries ``r*c`` to ``r*c + c - 1``, so index
    ``i`` is at ``(i % c, height + i // c)``.  The rows of code alternate
    ``>...v`` and ``v...<``, so the fish swims down through them.
    """
    divisor = "1" + "2*" * (columns.bit_length() - 1)
    # i -> i%c, i//c: the column, then (i - i%c) / c, exact as c divides it.
    body = "0" + reads + ":" + divisor + "%$:" + divisor + "%-" + divisor + ","
    tail = "+g68*-n;"
    # The height literal pushes h, so the code (literal included) must fit h rows.
    # One hex digit up to 15 rows, else a*b with a = ceil(sqrt(rows)) up to 225,
    # else a doubling literal at a power of two.

    def plan(prefix: str) -> tuple[int, str]:
        def rows_for(extra: int) -> int:
            return -(-(len(prefix) + extra + len(tail)) // columns)

        if rows_for(1) <= 15:
            height = rows_for(1)
            return height, f"{height:x}"
        if rows_for(3) <= 225:
            need = rows_for(3)
            first = isqrt(need - 1) + 1
            second = -(-need // first)
            return first * second, f"{first:x}{second:x}*"
        height = 1 << (2 * len(prefix) // columns + 32).bit_length()
        return height, "1" + "2*" * (height.bit_length() - 1)

    height, literal = plan(body)
    if height + (len(truth_table) - 1) // columns > _EXACT:
        body = _integer_coordinates(reads, columns)
        height, literal = plan(body)
    body += literal + tail
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


def _number(value: int) -> str:
    """Return a Fish literal for ``value``: a hex digit, else doubling."""
    if value <= 15:
        return f"{value:x}"
    return _number(value // 2) + "2*" + ("1+" if value % 2 else "")


def _packed_folded(reads: str, truth_table: str, columns: int) -> str:
    """Return the packed table folded: a snake of code over a ``columns`` block.

    The six powers of two sit in the row below the code, the packed cells in
    ``columns``-wide rows under them; an index ``i`` of a cell is at
    ``(i % c, rows + 1 + i // c)``.  Rows of code alternate as in :func:`_folded`.
    """
    width = _number(columns)
    rows = 1
    while True:
        # Cell i -> (i % c, rows + 1 + i // c); a power b -> (b, rows).
        coordinates = f":{width}%:@-{width},{_number(rows + 1)}+g"
        # Undo the eight-word offset before splitting the cell coordinates.
        body = (
            f"{_packed_reads(reads)}:{_WORD}%:@-{_WORD},8+{coordinates}"
            f"57*-${_number(rows)}g88*-,2%1(n;"
        )
        if -(-len(body) // columns) <= rows:
            break
        rows += 1
    quotient = (len(truth_table) - 1) // _WORD
    if max(quotient, columns, rows + 1 + quotient // columns) > _EXACT:
        # The packed float is no longer exact; an unpacked power-of-two fold
        # can split its integer index before converting a smaller quotient.
        return _folded(reads, truth_table, 1 << (columns.bit_length() - 1))
    cells = "".join(
        chr(_BASE + sum((ch == "0") << j for j, ch in enumerate(word)))
        for word in (
            truth_table[i : i + _WORD] for i in range(0, len(truth_table), _WORD)
        )
    )
    powers = "".join(chr(64 + (1 << bit)) for bit in range(_WORD))
    snake: list[str] = []
    for offset in range(0, len(body), columns):
        chunk = body[offset : offset + columns].ljust(columns)
        snake.append(
            ">" + chunk + "v" if len(snake) % 2 == 0 else "v" + chunk[::-1] + "<"
        )
    snake.extend([""] * (rows - len(snake)))
    snake.append(powers)
    snake.extend(
        cells[offset : offset + columns] for offset in range(0, len(cells), columns)
    )
    return "\n".join(snake)


def balance_fish(truth_table: str, default: str) -> str:
    """Minimize rendered side over four packed or precision-safe folds.

    Widths lie near ``sqrt(2 * length)`` ([ablations.balance_packed_fold]);
    unpacked folds are reserved for coordinates beyond binary64 precision.
    """
    n = _validate_truth_table(truth_table)
    candidates = [default]
    if len(set(truth_table)) == 1:
        # W = 2*ceil(L/(W-2)); the crossing is 1+sqrt(1+2L).
        side = 1 + isqrt(1 + 2 * (2 * n + 3))
        candidates.append(fish(truth_table, 1))
        candidates.extend(
            fish(truth_table, max(3, width)) for width in range(side - 1, side + 4)
        )
        return min(candidates, key=balance_score)
    weights, table = input_weights(truth_table, n)
    reads = "".join("i68*-$2*+" if weight else "i~" for weight in weights)
    root = (2 * len(_packed(reads, table))) ** 0.5
    candidates.extend(
        _packed_folded(reads, table, max(4, round(root * scale)))
        for scale in (0.9, 1.0, 1.1, 1.2)
    )
    return min(candidates, key=balance_score)
