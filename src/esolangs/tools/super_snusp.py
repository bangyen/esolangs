"""Boolean-function generator for Super SNUSP.

Wide tables use a linear packed-integer lookup.  Small tables retain the ANF
evaluator where its XOR of input products is shorter, at a per-input
polarity: a cell may hold an input or its complement at one command.  Neither uses the
language's random ``=`` opcode.
"""

from math import isqrt

from esolangs.tools.helpers import (
    _validate_truth_table,
    anf_coefficients,
    essential_inputs,
    input_weights,
    move_text,
    read_at,
)
from esolangs.tools.wrap import balance_score

__all__ = ["super_snusp"]


_TWO_INPUT_SHORT = {
    # These executed forms reuse 48 both to decode each input and to encode
    # the answer.  They beat the general ANF construction by keeping the
    # literal at the bottom of the stack rather than rebuilding it at the end.
    "0000": "48{,-> ,-<}.",
    "0011": "48{,-> ,-<^.",
    "0101": "48{,-> ,-<>^.",
    "0110": "48{,-> ,-<^{>^.",
    "0111": "48{,-> ,-<^{>|.",
}

# ANF wins on small sparse functions, but its input products are super-linear.
# Bound the comparison to keep those wins off the scaling path.
_ANF_MAX_INPUTS = 4


def _flip(truth_table: str, negated: int) -> str:
    """Return ``truth_table`` with the inputs set in ``negated`` inverted.

    ``negated`` is a row mask (most-significant input first), so row ``r``
    of the result is row ``r ^ negated`` of the table.
    """
    return "".join(truth_table[row ^ negated] for row in range(len(truth_table)))


def _decode_base(k: int, negated: int) -> int:
    """Return the decode constant, 48 or 49, for ``k`` retained inputs.

    ``,-`` against 48 stores an input as its bit (0 or 1); against 49 it
    stores ``bit - 1``, which is -1 for a 0 and 0 for a 1.  A product starts
    at 1 and ``&`` with -1 keeps it, so a -1/0 cell *is* the negated
    literal.  Whichever polarity is the majority rides on the constant for
    free and each minority input pays one ``(`` or ``)``.
    """
    return 49 if 2 * negated.bit_count() > k else 48


def _emit_anf(
    n: int,
    truth_table: str,
    used: list[int],
    *,
    negated: int = 0,
) -> str:
    """Emit a fixed-polarity ANF evaluator over ``used`` stream inputs.

    ``negated`` marks, as a row mask over ``truth_table``'s inputs, the
    retained inputs whose cells hold the complement; the terms are then the
    ANF of the table with those inputs flipped.
    """
    k = len(used)
    base = _decode_base(k, negated)
    program = ['"', f"{base}{{"]
    retained = 0
    for input_index in range(n):
        program.extend([",", "-"])
        if input_index in used:
            flipped = bool(negated >> (k - 1 - retained) & 1)
            retained += 1
            if flipped and base == 48:
                program.append("(")
            elif not flipped and base == 49:
                program.append(")")
            program.append(">")

    # A trailing ignored input occupies the accumulator cell.  Inputs that
    # are ignored earlier are overwritten by the next retained input, so a
    # clear is needed only when the last stream input is ignored (or none are
    # retained at all).
    if not used or used[-1] != n - 1:
        program.append("0")
    product = k + 1
    coefficients = anf_coefficients(_flip(truth_table, negated))
    if coefficients[0]:
        program.append(")")

    for mask, coefficient in enumerate(coefficients[1:], start=1):
        if not coefficient:
            continue
        program.extend([">", "1"])
        for input_index in range(k):
            table_bit = 1 << (k - 1 - input_index)
            if mask & table_bit:
                program.extend(
                    [
                        move_text(product, input_index, ">", "<"),
                        "{",
                        move_text(input_index, product, ">", "<"),
                        "&",
                    ]
                )
        program.extend(["{", "<", "^"])

    # The stack top is a term by now, so build a fresh ASCII offset in the
    # product cell and push it.  The accumulator is then exactly 48 or 49.
    program.extend([">", "48", "{", "<", "+", "."])
    return "".join(program)


def _anf_cost(
    n: int,
    truth_table: str,
    used: list[int],
    *,
    negated: int = 0,
) -> int:
    """Return the rendered length of :func:`_emit_anf` without emitting it."""
    k = len(used)
    flips = negated.bit_count()
    cost = 4 + 2 * n + k + 7 + min(flips, k - flips)
    if not used or used[-1] != n - 1:
        cost += 1
    coefficients = anf_coefficients(_flip(truth_table, negated))
    cost += coefficients[0]
    product = k + 1
    for mask, coefficient in enumerate(coefficients[1:], start=1):
        if not coefficient:
            continue
        cost += 5  # ``>1`` then ``{<^`` around the product.
        for input_index in range(k):
            table_bit = 1 << (k - 1 - input_index)
            if mask & table_bit:
                cost += 2 * (product - input_index) + 2
    return cost


def _polarity(n: int, truth_table: str, used: list[int]) -> tuple[int, int]:
    """Return a polarity and cost after one greedy pass from positive inputs."""
    mask = 0
    cost = _anf_cost(n, truth_table, used)
    for bit in range(len(used)):
        trial = _anf_cost(n, truth_table, used, negated=mask ^ 1 << bit)
        if trial < cost:
            mask, cost = mask ^ 1 << bit, trial
    return mask, cost


def _emit_lookup(truth_table: str) -> str:
    """Emit a linear-size integer lookup for ``truth_table``.

    The input row is accumulated by Horner's rule in cell 0.  Cell 1 then
    builds the reversed table as one binary integer at run time, shifts it by
    that row, and takes the low bit.  Each table entry emits one ``*`` and a
    one entry emits one extra ``)``, so generation and output are O(T).  An
    ignored input is read into cell 1 and left there for the next read, or
    for ``>0``, to overwrite; the table indexes the rest.
    """
    weights, truth_table = input_weights(
        truth_table, _validate_truth_table(truth_table)
    )
    out = ['"']
    for weight in weights:
        # acc *= 2; read and normalize the next ASCII bit; acc += bit.
        out.extend((">2{<*$", ">,>48{<-$", "{<+$") if weight else (">,<",))
    # Keep 2 on the value stack while cell 1 builds the packed table.  The
    # reversed source order makes truth_table[row] bit ``row`` of the integer.
    out.append(">0>2{<")
    out.extend("*)" if bit == "1" else "*" for bit in reversed(truth_table))
    # Shift by the row saved in cell 0, reduce modulo 2, encode as ASCII.
    out.append("<{>]$%$>48{<+$.")
    return "".join(out)


def _super_snusp_flat(truth_table: str) -> str:
    """Emit the shortest bounded-ANF or linear lookup program.

    Only essential inputs are retained, compactly, while every original input
    is still consumed in stream order.  The ANF is built over that projection
    or the full table, whichever is shorter at its :func:`_polarity`: for
    every nonzero coefficient the construction forms its input product
    beside the accumulator and xors it in.  Both reads happen before any
    evaluation, so every path consumes exactly ``n`` input lines, including
    constant and reduced functions.
    """
    n = _validate_truth_table(truth_table)
    if n == 2 and truth_table in _TWO_INPUT_SHORT:
        # An explicit START marker removes the spec's undocumented default
        # heading from generated programs; it is a no-op once execution begins.
        return '"' + _TWO_INPUT_SHORT[truth_table]

    lookup = _emit_lookup(truth_table)
    if n > _ANF_MAX_INPUTS:
        return lookup

    used = essential_inputs(truth_table, n)
    full = list(range(n))
    shapes = [(truth_table, full)]
    if len(used) < n:
        shapes.append((read_at(truth_table, used, n), used))
    # Price each shape at its chosen polarity and emit only the cheaper; the
    # full shape wins ties, as it did before polarity was chosen, because
    # ``min`` returns the first of equally cheap entries.
    priced = [
        (_polarity(n, table, retained), table, retained) for table, retained in shapes
    ]
    (negated, _cost), table, retained = min(priced, key=lambda shape: shape[0][1])
    anf = _emit_anf(n, table, retained, negated=negated)
    return min(lookup, anf, key=len)


def _super_snusp_tokens(program: str) -> list[str]:
    """Split ``program`` into the pieces a fold may not break apart.

    Every command is one cell except a run of digits: a digit multiplies
    what the cell already holds by ten, and *any* non-digit clears that, so
    the mirrors of a fold between ``4`` and ``8`` would leave 4 and 8
    instead of 48.
    """
    tokens: list[str] = []
    index = 0
    while index < len(program):
        if program[index].isdigit():
            end = index
            while end < len(program) and program[end].isdigit():
                end += 1
            tokens.append(program[index:end])
            index = end
        else:
            tokens.append(program[index])
            index += 1
    return tokens


def _super_snusp_folded(program: str, width: int) -> str:
    r"""Fold ``program`` into a boustrophedon inside ``width`` columns.

    SNUSP's mirrors are what make this the cheapest fold of any generator
    here: ``\\`` sends an eastward pointer down and ``/`` sends a downward
    one west, so the pair stacked turns a row round in **one row and one
    column**.  At the west edge ``/`` then ``\\`` bring it back east.

    A westward row is written in the order the pointer meets its cells,
    which is right to left on the page.  Nothing is reversed; the row is.

    The mirrors sit at the far edges and the gap before them is left blank,
    since a blank is a cell the pointer walks over -- so unlike Alight,
    which has to pad with empty commands, this pads with nothing at all.
    Folding where the commands run out instead would leave the next row
    starting wherever that was, with less than a full row to work with.

    The floor is two columns wider than the longest token, and every token
    here is one cell but the ``48`` the decode leans on.  A width under the
    floor is raised to it.
    """
    tokens = _super_snusp_tokens(program)
    limit = max(width, max(len(token) for token in tokens) + 2)
    cells: dict[tuple[int, int], str] = {}
    row, col, step = 0, 0, 1
    index = 0
    # Each row consumes a token; the final row leaves through the break.
    while True:
        edge = limit - 1 if step == 1 else 0
        mirror, under = ("\\", "/") if step == 1 else ("/", "\\")
        room = abs(edge - col)
        taken: list[str] = []
        used = 0
        while index < len(tokens):
            token = tokens[index]
            if taken and used + len(token) > room:
                break
            taken.append(token)
            used += len(token)
            index += 1
        for i, char in enumerate("".join(taken)):
            cells[row, col + i * step] = char
        if index == len(tokens):
            break
        cells[row, edge] = mirror
        cells[row + 1, edge] = under
        row += 1
        step = -step
        col = edge + step
    height = max(r for r, _ in cells) + 1
    ends: dict[int, int] = {}
    for r, c in cells:
        ends[r] = max(ends.get(r, 0), c)
    return "\n".join(
        "".join(cells.get((r, c), " ") for c in range(ends.get(r, -1) + 1)).rstrip()
        for r in range(height)
    )


def super_snusp(truth_table: str, width: int | None = None) -> str:
    """Build a deterministic Super SNUSP program for ``truth_table``.

    Small functions keep the shorter of the ANF evaluator and an integer
    lookup.  Above four inputs only the lookup is built: it emits one or two
    commands per table entry and O(n) setup while consuming every input.

    ``width`` asks for a column count, and the straight line folds into a
    boustrophedon to meet one -- see :func:`_super_snusp_folded`, where the
    mirrors turn a row round in one row and one column.  A width under the
    floor returns the narrowest program rather than refusing.
    """
    return _super_snusp_layout(_super_snusp_flat(truth_table), width)


def _super_snusp_layout(flat: str, width: int | None) -> str:
    """Return the natural, vertical, or folded layout of ``flat``."""
    if width is None or len(flat) <= width:
        return flat
    if 0 < width < 3:
        # START may be absent (wiki); the bottom-right rightward entry
        # meets a slash and climbs the complete straight evaluator.
        return "\n".join(reversed("/" + flat[1:]))
    if width < 4:
        pieces = []
        for token in _super_snusp_tokens(flat):
            if len(token) == 1:
                pieces.append(token)
            else:
                # Both emitters use only 48/49 as multi-digit literals.
                pieces.append("6{8*" + (")" if token[-1] == "9" else ""))
        flat = "".join(pieces)
    return _super_snusp_folded(flat, width)


def balance_super_snusp(flat: str) -> str:
    """Return the best-balanced supported layout of a generated straight line.

    Tokens must have at most two cells. For s=ceil(sqrt(L)), the normal
    fold's W=H crossing lies at s+1 or s+2; s covers the preceding width.
    Row count decreases with width, so only crossing neighbors can win.
    """
    if any(len(token) > 2 for token in _super_snusp_tokens(flat)):
        raise ValueError("Super SNUSP balancing requires tokens of at most two cells")
    side = isqrt(len(flat) - 1) + 1
    # W rows hold at most (W-1)^2 cells and at least W*(W-3)+1:
    # first-row room is W-1, later room W-2, and each row wastes at most one.
    lower = _super_snusp_layout(flat, max(4, side))
    middle = _super_snusp_layout(flat, max(4, side + 1))
    upper = _super_snusp_layout(flat, max(4, side + 2))
    vertical = _super_snusp_layout(flat, 1)
    narrow = _super_snusp_layout(flat, 3)
    return min((flat, lower, middle, upper, vertical, narrow), key=balance_score)
