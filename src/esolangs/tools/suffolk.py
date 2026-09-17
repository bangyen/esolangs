"""Boolean-function generator for Suffolk."""

from esolangs.tools.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    read_at,
)


def _suffolk_candidate_cost(truth_table: str, wanted: str, *, invert: bool) -> int:
    """Return the rendered length of one non-constant Suffolk polarity."""
    n = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, n) or [0]
    reduced = truth_table if len(used) == n else read_at(truth_table, used, n)
    width = len(used)

    # ``const(gap, value)`` is ``value`` copies of ``'>' * gap + '!'``.
    cost = 2 * _ASCII_ONE
    for i in range(n):
        gap = 2 + i
        cost += (gap + 1) * _ASCII_ZERO + gap + 2
    for i in range(n):
        gap = 2 + i
        raw_gap = 2 + n + i
        cost += gap + raw_gap + 2

    cells: list[int] = []
    next_cell = 2 + 2 * n
    for row in range(2**width):
        if reduced[row] != wanted:
            continue
        for slot in range(width):
            bit = (row >> (width - 1 - slot)) & 1
            literal = 2 + used[slot] if bit else 2 + n + used[slot]
            cost += literal + 1
        cost += next_cell + 1
        cells.append(next_cell)
        next_cell += 1

    cost += sum(cell + 1 for cell in cells)
    return cost + (5 if invert else 3)


def _suffolk_minterm(truth_table: str) -> str:
    """Build a Suffolk program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Suffolk has no branch and no data-dependent jump, so this is a
    branch-free sum of minterms, run at ``limit=1`` (a single pass, one
    read per input -- the default 10-pass rerun would replay every ``,``
    with no more input left).  The only nonlinearity is ``!``, which
    computes ``max(0, cell + 1 - acc)``: with a preloaded 48-cell and
    ``acc = 48 + bit`` (one ``,`` read), it yields the complement
    ``1 - bit``; a second ``!`` from a zero cell complements again to
    recover ``bit``.  Summing ``n`` literals (complement when the row wants
    a 0, raw bit when it wants a 1) into ``acc`` and applying ``!`` to a
    zero cell gives ``max(0, 1 - sum)``, which is 1 only when every literal
    matches (an AND of that row's minterm) and 0 otherwise.  Every row's
    minterm cell is 0 except the one matching the actual inputs, so summing
    all of them plus a preloaded 49-cell into ``acc`` and printing
    (``.`` emits ``chr(acc - 1)``) prints ``48`` or ``49``.

    Constant tables need no reads at all: ``.`` prints ``chr(acc - 1)``, so
    the accumulator only has to hold 50 (all-ones, prints ``49``) or 49
    (all-zeros, prints ``48``) at the print.

    A table can be evaluated from its zero rows and the answer inverted.
    The exact rendered cost of both polarities is counted first, so only the
    shorter program is built.  ``_maybe_complement`` is deliberately not
    used -- its all-ones case complements to *no* minterms, which the
    constant-table branch above already handles better.
    """
    n = _validate_truth_table(truth_table)

    def const(gap: int, value: int) -> str:
        """``(gap '>'s then '!') * value`` builds ``value`` at that cell.

        ``!`` resets the pointer to 0, so each repetition re-walks ``gap``
        steps out to the same cell before incrementing it.
        """
        return (">" * gap + "!") * value

    if len({*truth_table}) == 1:
        # A constant table needs no minterms, but the reads are the language's
        # interface: skipping them leaves the caller's bits unread on the input
        # stream.  Read each input into its own scratch cell and discard it.
        reads = "".join(
            const(2 + i, _ASCII_ZERO) + ">" * (2 + i) + "," + "!" for i in range(n)
        )
        return const(1, _ASCII_ONE + int(truth_table[0])) + reads + ">" + "<" + "."

    # A table that ignores some of its inputs is a smaller table, and a
    # minterm costs one literal walk *per input* on top of one block per
    # selected row -- so dropping an input removes rows and shortens the
    # rows that remain.  The reads stay, one ``,`` per input; an ignored one
    # is read into its own scratch cell and never used as a literal, which
    # is exactly what the constant branch above already does for *every*
    # input.  This is that branch generalized from "no essential inputs" to
    # "the ones that matter".
    used = essential_inputs(truth_table, n) or [0]
    reduced = truth_table if len(used) == n else read_at(truth_table, used, n)
    width = len(used)

    def evaluate(wanted: str, *, invert: bool) -> str:
        """Sum the minterms of the rows equal to ``wanted``, then print.

        With ``invert`` the sum answers the *complement* of the table, so
        the print stage has to flip it back.
        """
        # Cell 1 holds the print stage's additive constant.  ``const``
        # re-walks the gap once per unit, so this has to live at the
        # cheapest cell there is: 49 units at cell 1 costs 98 characters,
        # where the same constant out past the minterm cells would cost
        # several hundred and swamp what the complement saves.
        body = const(1, _ASCII_ONE)
        # cells 2..2+n-1: complement of each input bit (1 - bit)
        for i in range(n):
            gap = 2 + i
            body += const(gap, _ASCII_ZERO) + ">" * gap + "," + "!"
        # cells 2+n..2+2n-1: the raw bit, recovered from the complement
        for i in range(n):
            gap = 2 + i
            raw_gap = 2 + n + i
            body += ">" * gap + "<" + ">" * raw_gap + "!"

        cells: list[int] = []
        next_cell = 2 + 2 * n
        for row in range(2**width):
            if reduced[row] != wanted:
                continue
            # Slot ``s`` carries original input ``used[s]``, whose complement
            # and raw cells were laid down at the full arity above.
            bits = [(row >> (width - 1 - s)) & 1 for s in range(width)]
            literals = [
                (2 + used[s]) if v else (2 + n + used[s]) for s, v in enumerate(bits)
            ]
            body += "".join(">" * c + "<" for c in literals)
            body += ">" * next_cell + "!"
            cells.append(next_cell)
            next_cell += 1

        if not invert:
            body += "".join(">" * c + "<" for c in cells)
            body += ">" + "<"  # add the constant cell
            return body + "."
        # ``S`` is 1 exactly when the inputs match a row the table sends to
        # ``0``, so the answer is ``1 - S``.  ``.`` prints ``chr(acc - 1)``
        # and ``!`` computes ``max(0, cell + 1 - acc)``, so a cell preloaded
        # with 49 and hit with ``acc = S`` holds ``50 - S``; reading it back
        # makes ``acc = 50 - S`` and the print emits ``chr(49 - S)``.  The
        # clamp never bites, since ``S`` is 0 or 1.
        # ``S`` is 1 exactly when the inputs match a row the table sends
        # to ``0``, so the answer is ``1 - S``.  ``!`` computes
        # ``max(0, cell + 1 - acc)``, so cell 1's 49 becomes ``50 - S``;
        # reading it back makes ``acc = 50 - S`` and ``.`` (which emits
        # ``chr(acc - 1)``) prints ``chr(49 - S)`` -- ``'1'`` for S == 0 and
        # ``'0'`` for S == 1.  The clamp never bites, since ``S`` is 0 or 1.
        # Preloading 48 instead is the off-by-one that prints ``'/'``: the
        # print's ``- 1`` and ``!``'s ``+ 1`` both have to be counted.
        body += "".join(">" * c + "<" for c in cells)
        body += ">" + "!"
        body += ">" + "<"
        return body + "."

    plain_cost = _suffolk_candidate_cost(truth_table, "1", invert=False)
    flipped_cost = _suffolk_candidate_cost(truth_table, "0", invert=True)
    # ``min((plain, flipped), key=len)`` previously retained plain on ties.
    return (
        evaluate("1", invert=False)
        if plain_cost <= flipped_cost
        else evaluate("0", invert=True)
    )


def suffolk(truth_table: str) -> str:
    """Build Suffolk by a one-pass Shannon fold of reusable NOR muxes."""
    n = _validate_truth_table(truth_table)

    def const(cell: int, value: int) -> str:
        return (">" * cell + "!") * value

    if len(set(truth_table)) == 1:
        reads = "".join(
            const(2 + i, _ASCII_ZERO) + ">" * (2 + i) + ",!" for i in range(n)
        )
        return const(1, _ASCII_ONE + int(truth_table[0])) + reads + "><."

    used = essential_inputs(truth_table, n) or [0]
    reduced = truth_table if len(used) == n else read_at(truth_table, used, n)
    width = len(used)
    body = const(1, 1)
    scratch = (2, 3)

    def cells(level: int) -> tuple[int, int, int, int]:
        base = 4 + 4 * level
        return base, base + 1, base + 2, base + 3

    selectors: list[tuple[int, int]] = []
    for original in range(n):
        level = n - 1 - original
        raw, negated, _, _ = cells(level)
        body += const(negated, _ASCII_ZERO) + ">" * negated + ",!"
        body += ">" * negated + "<" + ">" * raw + "!"
        if original in used:
            selectors.append((raw, negated))

    def read(cell: int) -> str:
        return ">" * cell + "<"

    def nor(target: int, left: int, right: int) -> None:
        nonlocal body
        body += read(target) + read(left) + read(right) + ">" * target + "!"

    stack: list[tuple[int, int]] = []
    for index, bit in enumerate(reduced):
        signal, level = int(bit), 0
        while stack and stack[-1][1] == level:
            zero, _ = stack.pop()
            selector, negated = selectors[width - 1 - level]
            if zero == 0 and signal == 1:
                signal = selector
            elif zero == 1 and signal == 0:
                signal = negated
            elif zero != signal:
                _, _, first, second = cells(level)
                target = (first, second)[(index >> (level + 1)) & 1]
                nor(scratch[0], zero, selector)
                nor(scratch[1], signal, negated)
                nor(target, scratch[0], scratch[1])
                signal = target
            level += 1
        stack.append((signal, level))
    [(result, _)] = stack
    body += const(1, _ASCII_ZERO) + read(1) + read(result) + "."
    return body
