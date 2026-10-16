"""Circlefuck Boolean program generator: the table is deleted down to the answer.

Horner's rule folds the essential bits into base-128 index cells that delete
the entries before the named one; ``.`` prints the rest, or a constant's tail.
One character an entry.

Size:
    O(T) chars; n=10 parity: 1,704 chars, n=16 and: 66,823 chars.

Decisions:
    No entry can drop without clamping the index, and a literal deleted into
    by index has no subtrees to share.
"""

from itertools import pairwise

from esolangs.generation.constant_projection import balanced_projection
from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.generation.wrap import balance_program, wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape

#: Bits an index digit carries: seven is the widest power of two a byte can
#: also count out (:func:`_deleter` plants that many in the digit below).
_DIGIT_BITS = 7

#: One input: read, subtract ``"0"``, clamp to 0 or 1, bank.  The clamp is
#: load-bearing: an underfed ``,`` is a no-op, so the cell keeps the source
#: character and the index would delete past the table.
#:
#: The 48 is not spelled out: a 6-count loop subtracts 8 from the read cell
#: per pass (the scratch cell is cleared first -- the tape holds program
#: text, not zeros).  This ends exactly where the straight version did
#: (bit banked, scratch zero, pointer one right), at 40 source characters a read
#: instead of 69.
_READ = ",>[-]++++++[<-------->-]<[[-]>+<]>[-<+>]"


def circlefuck(truth_table: str) -> str:
    """Return a Circlefuck program computing ``truth_table`` (MSB first)."""
    return _program(truth_table)


def _program(truth_table: str, *, keep_constant_index: bool = False) -> str:
    """Build the deleting index or a read-and-print literal constant."""
    _validate_truth_table(truth_table)
    n = len(truth_table).bit_length() - 1
    if len(set(truth_table)) == 1 and not keep_constant_index:
        # Reads rewrite cell zero after its instruction has run. The final
        # < wraps to the literal after @, clear of every rewritten cell.
        return "," * n + "<.@" + truth_table[0]
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
    # The tape is the program: the table is its tail, backwards past the
    # ``@``, so entry 0 abuts the index cells, which ``<`` reaches from cell 0
    # (the tape is a ring).  Only the table grows.
    prog.append(read_at(truth_table, essential, n)[::-1])
    prog.append("0" * cells)  # the index cells, cleared by the leading `[-]`s
    return "".join(prog)


def balance_circlefuck(table: str, default: str) -> str:
    """Keep the former constant index when it gives a better wrapped shape."""
    if len(set(table)) > 1:
        return balance_program(default, "circlefuck")
    return balanced_projection(
        default, _program(table, keep_constant_index=True), "circlefuck"
    )


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
    "circlefuck",
    category="tape_based",
    boolean=circlefuck,
    balance=balance_circlefuck,
    # A sum, not a tree: a lookup over the essential inputs only.
    shape=Shape.REDUCING,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
    eof="its input command is a no-op at EOF, as the spec says",
    empty_program="Circlefuck program cannot be empty",
)
