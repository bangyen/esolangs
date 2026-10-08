"""Boolean-function generator for Circlefuck."""

from itertools import pairwise

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    read_at,
)

#: Bits an index digit carries.  A cell is a byte, so one counter stops
#: addressing at 256 entries; the index is base ``2**_DIGIT_BITS``, one cell
#: a digit, and seven is the widest power of two a byte can also *count out*
#: -- :func:`_deleter` plants that many in the digit below and spends them.
_DIGIT_BITS = 7

#: One input: read it, subtract ``"0"``, clamp what is left to 0 or 1, and
#: bank it back.  The clamp is load-bearing -- an underfed ``,`` is a no-op,
#: so the cell keeps the source character, and an index built from that byte
#: would delete past the table and eat the program.  The scratch cell is the
#: next input's, which has not been read yet.
_READ = "," + "-" * _ASCII_ZERO + ">[-]<[[-]>+<]>[-<+>]"


def circlefuck(truth_table: str) -> str:
    """Build a Circlefuck program computing the given truth table.

    ``,`` reads each input and 48 ``-``s normalize it; Horner's rule folds
    the essential bits into an index, and the index is spent deleting the
    entries before the one it names, so ``.`` prints the entry the deletions
    leave under the pointer.  One character an entry.

    The tape is the program, so the table is the program's tail, laid out
    backwards past the ``@`` that stops the run: entry 0 abuts the index
    cells, which are the last cells of all and which ``<`` reaches from cell
    0 in one step because the tape is a ring.  The decoder is then a fixed
    number of characters and the table is the only part that grows.  Entries
    are the digits themselves, so none needs an escape.
    """
    _validate_truth_table(truth_table)
    n = len(truth_table).bit_length() - 1
    essential = essential_inputs(truth_table, n)
    width = len(essential)
    cells = max(1, -(-width // _DIGIT_BITS))
    prog = ["<[-]" * cells + ">" * cells]  # the index cells are the last cells
    prog.append(_READ * n)
    at = n
    for digit in range(cells):
        top = max(0, width - _DIGIT_BITS * (digit + 1))
        places = essential[top : width - _DIGIT_BITS * digit]
        if not places:
            continue
        prog.append("<" * (at - places[0]))
        for below, here in pairwise(places):
            # Horner: double what is banked and land it on the next bit's
            # own cell, which already holds that bit.
            gap = here - below
            prog.append(f"[-{'>' * gap}++{'<' * gap}]{'>' * gap}")
        at = places[-1]
        reach = at + cells - digit
        prog.append(f"[-{'<' * reach}+{'>' * reach}]")
    prog.append("<" * (at + cells))
    prog.append(">".join(_deleter(digit) for digit in range(cells)))
    prog.append("<" * cells + ".@")
    prog.append(read_at(truth_table, essential, n)[::-1])
    prog.append("0" * cells)  # the index cells, cleared by the leading `[-]`s
    return "".join(prog)


def _deleter(digit: int) -> str:
    """Spend digit ``digit``, deleting ``128**digit`` entries per unit.

    ``}`` removes the cell under the pointer and slides the tape down into
    it, so ``<}`` deletes the entry ahead of the digits *and* puts the digit
    back under the pointer -- one loop that both counts down and walks.  A
    higher digit has no step of its own, so it plants a full low digit
    underneath and spends that.
    """
    if digit == 0:
        return "[-<}]"
    return f"[-<{'+' * (1 << _DIGIT_BITS)}{_deleter(digit - 1)}>]"
