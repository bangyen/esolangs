"""Boolean-function generator for Suffolk."""

from esolangs.tools.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    read_at,
)

#: The cell plan.  Cost here is a cell's *index* -- every read spends one
#: ``>`` per cell crossed -- so the countdown, which every sweep op reads,
#: takes cell 0 and spells that read ``<``.  Cell 1 carries the two the
#: countdown subtracts (and the raw input bit before the sweep starts), 2-5
#: count each half-table's falling and rising steps, and 6-7 hold the top
#: bit that picks between the halves.
_DOWN, _TWO = 0, 1
_COUNTS = ((2, 3), (4, 5))
_RAW, _NEGATED = 6, 7


def _write(cell: int) -> str:
    """``cell <- max(0, cell + 1 - acc)``, clearing pointer and accumulator."""
    return ">" * cell + "!"


def _read(cell: int) -> str:
    """Sum ``cell`` into the accumulator."""
    return ">" * cell + "<"


def _one(cell: int) -> str:
    """Set a cell to one whatever it held: reading it cancels the old value."""
    return _read(cell) + _write(cell)


def suffolk(truth_table: str) -> str:
    """Build Suffolk by one countdown sweep over the table's steps.

    ``!`` is the only write and computes ``max(0, cell + 1 - acc)``: a
    clamped subtraction, not a gate, so the table is evaluated by counting
    rather than by a tree of NOR muxes.  Cell 0 counts down from ``H - x``,
    and so reads zero on exactly the last ``x`` of the sweep's ``H`` rounds,
    which turns ``count <- max(0, count + 1 - cell0)`` into "add one if the
    row is below ``x``".  Counting the rows where the table steps up and
    where it steps down telescopes to ``f(x)``, since between two steps the
    table is constant.  The top input splits the table in half and each half
    gets its own pair of counters, halving the sweep.
    """
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        # A constant still drains the stream; those reads land on cell 0,
        # which nothing else uses on this branch.
        answer = _write(_TWO) * (_ASCII_ONE + int(truth_table[0]))
        return answer + ",!" * n + _read(_TWO) + "."

    used = essential_inputs(truth_table, n)
    reduced = truth_table if len(used) == n else read_at(truth_table, used, n)
    half = len(reduced) // 2
    halves = (reduced[:half], reduced[half:])
    out = [_write(_DOWN)]  # H - x = 1 + the weights of the zero bits

    for i in range(n):
        if i not in used:
            # Drain an input the table ignores.  Cell 3 is still zero and a
            # read leaves it there: 48 or 49 outruns the clamp.
            out.append(">" * _COUNTS[0][1] + ",!")
            continue
        # Reading adds the byte to the accumulator, so a cell holding 48
        # comes back holding the *negated* bit.
        out.append(_one(_COUNTS[0][0]) + _write(_COUNTS[0][0]) * (_ASCII_ZERO - 1))
        out.append(">" * _COUNTS[0][0] + ",!")
        if used.index(i):
            out.append(_read(_TWO) + _read(_COUNTS[0][0]) + _write(_TWO))
            out.append((_read(_TWO) + _write(_DOWN)) * (half >> used.index(i)))
        else:
            # The top bit steers the halves instead of the countdown.
            out.append(_read(_RAW) + _read(_COUNTS[0][0]) + _write(_RAW))
            out.append(_read(_NEGATED) + _read(_RAW) + _write(_NEGATED))

    out.append(_one(_TWO) + _write(_TWO))  # cell 1 <- 2
    out.append(_read(_TWO) + _write(_COUNTS[0][0]))  # and the read cell <- 0

    step = _read(_TWO) + _write(_DOWN)
    for round_ in range(half):
        if round_:
            out.append(step)
        row = half - 1 - round_
        for table, (falls, rises) in zip(halves, _COUNTS, strict=True):
            above = int(table[row + 1]) if row + 1 < half else 0
            rise = int(table[row]) - above
            if rise:
                out.append(_read(_DOWN) + _write(rises if rise > 0 else falls))

    for table, (falls, rises) in zip(halves, _COUNTS, strict=True):
        if table[0] == "1":
            out.append(_write(falls))  # f(0) rides on the falling count
        out.append(_read(rises) + _write(falls))  # falls <- f(x) + 1
    # Each half answers max(0, 2 - (f + 1) - 2 * bit), which is the other
    # half's answer or zero, so their sum is the complement of the one the
    # top bit selects and one more clamp turns it back into f + 1.
    out.append(_one(_COUNTS[0][1]) + _read(_COUNTS[0][0]))
    out.append(_read(_RAW) * 2 + _write(_COUNTS[0][1]))
    out.append(_one(_COUNTS[1][1]) + _read(_COUNTS[1][0]))
    out.append(_read(_NEGATED) * 2 + _write(_COUNTS[1][1]))
    out.append(_one(_COUNTS[0][0]) + _read(_COUNTS[0][1]) + _read(_COUNTS[1][1]))
    out.append(_write(_COUNTS[0][0]) + _write(_TWO) * (_ASCII_ZERO - 2))
    return "".join(out) + _read(_TWO) + _read(_COUNTS[0][0]) + "."
