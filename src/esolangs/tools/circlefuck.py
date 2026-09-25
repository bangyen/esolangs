"""Boolean-function generator for Circlefuck."""

from collections.abc import Sequence
from itertools import pairwise

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table

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
    """
    _validate_truth_table(truth_table)
    return _circlefuck_table([_ASCII_ZERO + int(bit) for bit in truth_table])


def _essential_byte_inputs(truth_table: Sequence[int], n: int) -> list[int]:
    """Return the inputs the byte table depends on, ascending.

    One C-level slice compare per pair of sibling blocks, ``2**n`` steps in
    all; the bytes compared are ``n * 2**n / 2``, intrinsic to the check.
    """
    packed = bytes(truth_table)
    width = len(packed)
    essential = []
    for i in range(n):
        block = 1 << (n - 1 - i)
        if any(
            packed[lo : lo + block] != packed[lo + block : lo + 2 * block]
            for lo in range(0, width, 2 * block)
        ):
            essential.append(i)
    return essential


def _projected(
    truth_table: Sequence[int], n: int, essential: Sequence[int]
) -> list[int]:
    """Return the same function tabulated over ``essential`` alone.

    Every input is still read, but an inessential one picks no entry, so
    the table it would have doubled stays at ``2**len(essential)``.
    """
    rows = []
    for key in range(1 << len(essential)):
        row = 0
        for place, i in enumerate(essential):
            if (key >> (len(essential) - 1 - place)) & 1:
                row |= 1 << (n - 1 - i)
        rows.append(truth_table[row])
    return rows


def _cell(value: int) -> str:
    r"""Return one tape cell as source text.

    ``parse`` drops anything outside ``32 < ord < 127`` and reads ``\`` as
    an escape, so those spell themselves out instead.  :func:`circlefuck`
    only ever tabulates digits, so the character-counting wrapper never
    meets an escape it could split.
    """
    if 32 < value < 127 and value != 92:  # ord("\\")
        return chr(value)
    return f"\\x{value:02x}"


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


def _circlefuck_table(truth_table: Sequence[int]) -> str:
    """Emit the lookup for a byte-valued table; see :func:`circlefuck`.

    The tape is the program, so the table is the program's tail, laid out
    backwards past the ``@`` that stops the run: entry 0 abuts the digit
    cells, which are the last cells of all and which ``<`` reaches from cell
    0 in one step because the tape is a ring.  The decoder is then a fixed
    number of characters and the table is the only part that grows.
    """
    n = len(truth_table).bit_length() - 1
    essential = _essential_byte_inputs(truth_table, n)
    width = len(essential)
    digits = max(1, -(-width // _DIGIT_BITS))
    prog = ["<[-]" * digits + ">" * digits]  # the digits are the last cells
    prog.append(_READ * n)
    at = n
    for digit in range(digits):
        top = max(0, width - _DIGIT_BITS * (digit + 1))
        places = [essential[place] for place in range(top, width - _DIGIT_BITS * digit)]
        if not places:
            continue
        prog.append("<" * (at - places[0]))
        for below, here in pairwise(places):
            # Horner: double what is banked and land it on the next bit's
            # own cell, which already holds that bit.
            gap = here - below
            prog.append(f"[-{'>' * gap}++{'<' * gap}]{'>' * gap}")
        at = places[-1]
        reach = at + digits - digit
        prog.append(f"[-{'<' * reach}+{'>' * reach}]")
    prog.append("<" * (at + digits))
    prog.append(">".join(_deleter(digit) for digit in range(digits)))
    prog.append("<" * digits + ".@")
    rows = _projected(truth_table, n, essential)
    prog.extend(_cell(value) for value in reversed(rows))
    prog.append("0" * digits)  # the digit cells, cleared by the leading `[-]`s
    return "".join(prog)
