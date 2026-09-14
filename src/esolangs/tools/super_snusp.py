"""Boolean-function generator for Super SNUSP.

Wide tables use a linear packed-integer lookup.  Small tables retain the ANF
evaluator where its XOR of input products is shorter.  Neither uses the
language's random ``=`` opcode.
"""

from esolangs.tools.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)

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

# ANF can beat the lookup on small sparse functions, but its coefficient pass
# and input products are super-linear in the table.  Keeping that comparison
# finite preserves the small wins without putting it on the scaling path.
_ANF_MAX_INPUTS = 4


def _anf_coefficients(truth_table: str) -> list[int]:
    """Return ANF coefficients indexed by the ordinary truth-table rows."""
    coefficients = [int(bit) for bit in truth_table]
    n = len(truth_table).bit_length() - 1
    for bit in range(n):
        for mask in range(len(coefficients)):
            if mask & (1 << bit):
                coefficients[mask] ^= coefficients[mask ^ (1 << bit)]
    return coefficients


def _move(start: int, end: int) -> str:
    """Move the data pointer from ``start`` to ``end`` on the tape."""
    return (">" if end > start else "<") * abs(end - start)


def _emit_anf(
    n: int, truth_table: str, used: list[int], *, coefficients: list[int] | None = None
) -> str:
    """Emit an ANF evaluator over ``used`` stream inputs."""
    program = ['"', "48{"]
    for input_index in range(n):
        program.extend([",", "-"])
        if input_index in used:
            program.append(">")

    # A trailing ignored input occupies the accumulator cell.  Inputs that
    # are ignored earlier are overwritten by the next retained input, so a
    # clear is needed only when the last stream input is ignored (or none are
    # retained at all).
    if not used or used[-1] != n - 1:
        program.append("0")
    product = len(used) + 1
    coefficients = (
        _anf_coefficients(truth_table) if coefficients is None else coefficients
    )
    if coefficients[0]:
        program.append(")")

    for mask, coefficient in enumerate(coefficients[1:], start=1):
        if not coefficient:
            continue
        program.extend([">", "1"])
        for input_index in range(len(used)):
            table_bit = 1 << (len(used) - 1 - input_index)
            if mask & table_bit:
                program.extend(
                    [
                        _move(product, input_index),
                        "{",
                        _move(input_index, product),
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
    coefficients: list[int] | None = None,
) -> int:
    """Return the rendered length of :func:`_emit_anf` without emitting it."""
    cost = 4 + 2 * n + len(used) + 7
    if not used or used[-1] != n - 1:
        cost += 1
    coefficients = (
        _anf_coefficients(truth_table) if coefficients is None else coefficients
    )
    cost += coefficients[0]
    product = len(used) + 1
    for mask, coefficient in enumerate(coefficients[1:], start=1):
        if not coefficient:
            continue
        cost += 5  # ``>1`` then ``{<^`` around the product.
        for input_index in range(len(used)):
            table_bit = 1 << (len(used) - 1 - input_index)
            if mask & table_bit:
                cost += 2 * (product - input_index) + 2
    return cost


def _emit_lookup(truth_table: str) -> str:
    """Emit a linear-size integer lookup for ``truth_table``.

    The input row is accumulated by Horner's rule in cell 0.  Cell 1 then
    builds the reversed table as one binary integer at run time, shifts it by
    that row, and takes the low bit.  Each table entry emits one ``*`` and a
    one entry emits one extra ``)``, so generation and output are O(T).
    """
    n = _validate_truth_table(truth_table)
    out = ['"']
    for _ in range(n):
        # acc *= 2; read and normalize the next ASCII bit; acc += bit.
        out.extend((">2{<*$", ">,>48{<-$", "{<+$"))
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
    is still consumed in stream order.  The ANF is built over that projection:
    for every nonzero coefficient the construction forms its input product
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
    if len(used) == n:
        return min(lookup, _emit_anf(n, truth_table, full), key=len)
    reduced = read_at(truth_table, used, n)
    full_coefficients = _anf_coefficients(truth_table)
    reduced_coefficients = _anf_coefficients(reduced)
    anf = (
        _emit_anf(n, truth_table, full, coefficients=full_coefficients)
        if _anf_cost(n, truth_table, full, coefficients=full_coefficients)
        <= _anf_cost(n, reduced, used, coefficients=reduced_coefficients)
        else _emit_anf(n, reduced, used, coefficients=reduced_coefficients)
    )
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
    here: ``\\`` sends an eastward pointer down and a downward one west, so
    two stacked turn a row round in **one row and one column**.
    ``/`` does the mirror image, sending a westward pointer down and a
    downward one east, and brings it back.

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
    pending = list(tokens)
    # Every pass places at least one token and the pass that empties
    # ``pending`` leaves through the break below.
    while True:
        edge = limit - 1 if step == 1 else 0
        mirror = "\\" if step == 1 else "/"
        room = abs(edge - col)
        taken: list[str] = []
        used = 0
        while pending:
            token = pending[0]
            if taken and used + len(token) > room:
                break
            taken.append(token)
            used += len(token)
            pending.pop(0)
        for i, char in enumerate("".join(taken)):
            cells[row, col + i * step] = char
        if not pending:
            break
        cells[row, edge] = mirror
        cells[row + 1, edge] = mirror
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
    flat = _super_snusp_flat(truth_table)
    if width is None or len(flat) <= width:
        return flat
    return _super_snusp_folded(flat, width)
