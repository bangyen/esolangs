"""Fish Boolean program generator: the truth table sits in the codebox.

Each input is read and turned into a bit (``68*-`` subtracts ASCII ``0``),
folded into a row number most significant first (``$2*+``); ``g`` fetches the
answer from the table's digits by coordinates and ``n`` prints it.  For n=2:

    0i68*-$2*+i68*-$2*+1g68*-n;
    0110

Narrow widths fold the table into a block of columns, which the fish reaches
by snaking down.  A parity table needs no table at all.  From n=6 the
default is one row: the code, six powers of two, and the table packed six
entries a cell ([ablations.packed_row]).

Size:
    O(T), independent of the table at default width: about T/6 cells past
    n=5; n=16 parity: 71 chars, n=10 random 1847: 312 chars.

Decisions:
    A table has no subtrees to fold or share.
"""

from math import isqrt

from esolangs.generation.helpers import (
    _parity_bias,
    _validate_truth_table,
    input_weights,
)
from esolangs.generation.wrap import balance_score
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape


def fish(truth_table: str, width: int | None = None) -> str:
    """Return a Fish lookup grid; lookup folds need three columns; parity uses one."""
    n = _validate_truth_table(truth_table)
    # A one-column parity program fits any width; at n=10 it is 24 cells
    # against the lookup's 2,050 (default) and 3,435 (width 3).
    bias = _parity_bias(truth_table)
    if bias is not None:
        return _parity(n, bias)
    # An ignored input is read and dropped; the table indexes the rest.
    weights, truth_table = input_weights(truth_table, n)
    reads = "".join("i68*-$2*+" if weight else "i~" for weight in weights)
    header = "0" + reads + "1g68*-n;"
    if width is None:
        plain, packed = header + "\n" + truth_table, _packed(reads, truth_table)
        # Packed wins on area from n=4 but costs characters below n=6.
        smaller = _area(packed) <= _area(plain) and len(packed) <= len(plain)
        return packed if smaller else plain
    if max(len(header), len(truth_table)) <= width:
        return header + "\n" + truth_table
    columns = 1 << (min(max(1, width - 2), len(truth_table)).bit_length() - 1)
    return _folded(reads, truth_table, columns)


#: Table entries a packed cell carries, and the code of its all-ones word:
#: 64 printable codes from 35 skip DEL ([ablations.packed_row]).
_WORD = 6
_BASE = 35


def _area(program: str) -> int:
    """Return the codebox area, rows times the longest row."""
    rows = program.split("\n")
    return len(rows) * max(map(len, rows))


def _column(least: int) -> tuple[int, str]:
    """Return the first closed-form column at or past ``least`` and its literal.

    ``f*k`` reaches 225 in three characters; past it, a power of two.
    """
    k = -(-least // 15)
    if k <= 15:
        return 15 * k, "f" + "0123456789abcdef"[k] + "*"
    m = least.bit_length()
    return 1 << m, "1" + "2*" * m


def _packed(reads: str, truth_table: str) -> str:
    """Return one row: the code, then six powers of two, then the packed table.

    Cell ``q`` holds entries ``6q`` to ``6q + 5`` complemented, so the row
    splits into the cell and a bit ``b``; the cell over ``2**b``, mod 2, is
    under 1 exactly when the entry is 1.  The cells sit past ``;``, unrun.
    """
    cells = "".join(
        chr(_BASE + sum((ch == "0") << j for j, ch in enumerate(word)))
        for word in (
            truth_table[i : i + _WORD] for i in range(0, len(truth_table), _WORD)
        )
    )
    powers = "".join(chr(64 + (1 << bit)) for bit in range(_WORD))
    head = f"0{reads}:{_WORD}%:@-{_WORD},"
    # ``57*`` is _BASE, ``88*`` the powers' 64.
    middle, tail = f"{_WORD}++0g57*-$", "+0g88*-,2%1(n;"
    bare = len(head) + len(middle) + len(tail)
    # The literal appears twice, and its length can move the column.
    start, literal = _column(bare + 6)
    if bare + 2 * len(literal) > start:
        start, literal = _column(bare + 2 * len(literal))
    code = head + literal + middle + literal + tail
    return code.ljust(start) + powers + cells


def _parity(n: int, bias: int) -> str:
    """Return the sum of the inputs mod 2, one command per row.

    ASCII ``0`` is even, so the characters' sum already has the bits' parity.
    """
    return "\n".join("vi" + "i+" * (n - 1) + "2%" + ("0=" if bias else "") + "n;")


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

    def rows_for(extra: int) -> int:
        return -(-(len(body) + extra + len(tail)) // columns)

    if rows_for(1) <= 15:
        height = rows_for(1)
        literal = "0123456789abcdef"[height]
    elif rows_for(3) <= 225:
        need = rows_for(3)
        first = isqrt(need - 1) + 1
        second = -(-need // first)
        height = first * second
        literal = "0123456789abcdef"[first] + "0123456789abcdef"[second] + "*"
    else:
        height = 1 << (2 * len(body) // columns + 32).bit_length()
        literal = "1" + "2*" * (height.bit_length() - 1)
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


def balance_fish(truth_table: str, default: str) -> str:
    """Minimize the rendered side over every power-of-two fold and the parity column.

    Fold c=2^k gives W=c+2, H=h+ceil(T/c), where h is the code height, about
    (9n+11+6k)/c rows.  Folds run to the code's length, so about log2(9n)+1.
    """
    n = _validate_truth_table(truth_table)
    candidates = [default]
    weights, table = input_weights(truth_table, n)
    reads = "".join("i68*-$2*+" if weight else "i~" for weight in weights)
    # Folds wider than the table leave it one row; they pay off for short tables.
    candidates.extend(
        _folded(reads, table, 1 << k) for k in range(len(reads).bit_length() + 1)
    )
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Fish",
    "fish",
    category="grid_based",
    random=True,
    boolean=fish,
    # Not a tree: an indexed table read.
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
