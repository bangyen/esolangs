"""Boolean-function generator for Circlefuck."""

from itertools import pairwise

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.tools.wrap import wrap_chars

#: Bits an index digit carries: seven is the widest power of two a byte can
#: also count out (:func:`_deleter` plants that many in the digit below).
_DIGIT_BITS = 7

#: One input: read, subtract ``"0"``, clamp to 0 or 1, bank.  The clamp is
#: load-bearing: an underfed ``,`` is a no-op, so the cell keeps the source
#: character and the index would delete past the table.
_READ = "," + "-" * _ASCII_ZERO + ">[-]<[[-]>+<]>[-<+>]"


def circlefuck(truth_table: str) -> str:
    """Build a Circlefuck program computing the given truth table.

    Horner's rule folds the essential bits into an index, which is spent
    deleting the entries before the one it names; ``.`` prints what is left
    under the pointer.  One character an entry.

    The tape is the program: the table is its tail, backwards past the ``@``,
    so entry 0 abuts the index cells, which ``<`` reaches from cell 0 (the
    tape is a ring).  Only the table grows.  A literal deleted into by index:
    no entry can drop without clamping the index, and it has no subtrees to
    share.
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
            # Horner: double the bank onto the next bit's cell.
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

    ``<}`` deletes the entry ahead of the digits and puts the digit back
    under the pointer, so one loop counts down and walks.  A higher digit
    plants a full low digit underneath and spends that.
    """
    if digit == 0:
        return "[-<}]"
    return f"[-<{'+' * (1 << _DIGIT_BITS)}{_deleter(digit - 1)}>]"


LANGUAGE = Language(
    "Circlefuck",
    "tape_based.circlefuck",
    boolean=circlefuck,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
)
