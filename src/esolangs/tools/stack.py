"""Boolean-function generators for stack-based languages."""

from functools import cache
from itertools import product

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    permute_truth_table,
    read_at,
)

Sinks = tuple[tuple[int, str], ...]


def _sink_top(stack: tuple[int, ...], places: int) -> tuple[int, ...]:
    """Move the top bit down by ``places``, leaving the others in order."""
    *below, top = stack
    at = len(below) - places
    return (*below[:at], top, *below[at:])


def stack_programs(n: int, sinks: Sinks, read: str) -> dict[tuple[int, ...], str]:
    """Read-and-sink program for each reachable stack arrangement.

    Maps each arrangement (bottom to top, by input index) to its program,
    Forþ passing its own ``sinks`` (``(places, ops)``) and ``read``.  A
    product, not a search: a read leaves its bit on top and the only lasting
    choice is how far it sinks (0, 1 or 2), so there are ``2 * 3**(n - 2)``
    arrangements, which a test pins.
    """
    reached: dict[tuple[int, ...], str] = {}
    for combination in product(sinks, repeat=n):
        stack: tuple[int, ...] = ()
        text = ""
        for read_index, (places, ops) in enumerate(combination):
            stack = (*stack, read_index)
            text += read
            if places >= len(stack):
                break  # nothing below to sink under
            stack = _sink_top(stack, places)
            text += ops
        else:
            # 162 completions at n == 6, no two sharing a shape, so the
            # tie-break never fires; it stays because the table is keyed by
            # shape and a future sink could repeat one.
            if (  # pragma: no branch - no two combinations share a shape
                stack not in reached or len(text) < len(reached[stack])
            ):
                reached[stack] = text
    return reached


#: Int-mode digits: ``Z`` is 0 and ``A``-``Y`` are 1 to 25, so the one value
#: with no letter is 6 -- ``F`` closes the mode.  16 with a borrow spells it.
_GRAPHEME_DIGITS = "ZABCDE?GHIJKLMNOPQRSTUVWXY"

#: Holds 65.  A literal is worth ten times its digits, so ``9`` names key 90.
_GRAPHEME_CONST = 9


def _grapheme_push65() -> str:
    """Grapheme code pushing 65 (``ord('A')``), spelled ``70 - (50 / 10)``."""
    return "FAF" + "FEF" + "R" + "FGF" + "B"


def _grapheme_literal(value: int) -> str:
    """Return an int-mode literal pushing ``10 * value``, for ``value >= 0``."""
    digits = [int(c) for c in str(value)]
    if digits[0] == 6:
        raise AssertionError("a leading 6 has nothing to borrow from")
    for at in range(len(digits) - 1, 0, -1):
        if digits[at] != 6:
            continue
        digits[at] = 16
        lend = at - 1
        while digits[lend] == 0:
            digits[lend] = 9
            lend -= 1
        digits[lend] -= 1
    return "F" + "".join(_GRAPHEME_DIGITS[digit] for digit in digits) + "F"


def _grapheme_table(table: str) -> int:
    """Pack entry ``i`` at bit ``len(table) - 1 - i``, lifted to lead with 1."""
    span = 1 << len(table)
    value = int(table, 2)
    lift: int = 10 ** (len(str(span)) + 1)
    return value + -(-(lift - value) // span) * span


def grapheme(truth_table: str) -> str:
    """Build a Grapheme program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first; prints
    ``'0'`` or ``'1'``.  The table is one int-mode literal, ~0.302 letters an
    entry, indexed by Horner's rule run on the complemented input bits.
    """
    n = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, n) or [0]
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    reading = set(used)

    ten = _grapheme_literal(1)
    one = ten * 2 + "R"
    two = ten + _grapheme_literal(2) + "R"
    store65 = _grapheme_push65() + _grapheme_literal(_GRAPHEME_CONST) + "C"
    read_bit = "W" + _grapheme_literal(_GRAPHEME_CONST) + "D" + "B" + "T"
    drop_unread_line = "WM"
    square = "KS"
    double_unless_set = two + "B" + "S"
    match_the_literal_scale = ten + "S"
    shift = "R"
    low_bit = "K" + two + "LR" + two + "SLB"

    pieces = [store65, one]
    for input_index in range(n):
        if input_index in reading:
            pieces.append(square + read_bit + double_unless_set)
        else:
            pieces.append(drop_unread_line)
    pieces.append(match_the_literal_scale)
    pieces.append(_grapheme_literal(_grapheme_table(table)))
    pieces.append(shift + low_bit + "Y")
    return "".join(pieces)


def _forth_const(value: int) -> str:
    """Forþ code pushing ``value`` (base-15 digits built with Horner's rule)."""
    digits = "0123456789ABCDEF"
    if value == 0:
        return "0"
    ds: list[int] = []
    v = value
    while v:
        ds.append(v % 15)
        v //= 15
    ds.reverse()
    prog = digits[ds[0]]
    for d in ds[1:]:
        prog += "F*" + digits[d] + "+"
    return prog


def forth(truth_table: str) -> str:
    """Build a Forþ program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first; prints
    ``'0'`` or ``'1'``.  A decision tree of functions: ``{ scope }`` stores,
    ``;`` calls; inputs normalized with ``,68*-``; a leaf pushes
    ``48 + result`` for the final ``.``.  Heap indices (children of ``m`` at
    ``2m + 1``, ``2m + 2``) are never spelled: ``{`` reads its key without
    popping, so definitions are emitted in index order introduced by
    ``1+``, and ``;`` pops, so a node that dups its key leaves the callee
    its own index -- an internal node is the fixed ``2*1++:;``.  Linear in
    the table.  ``;`` pops, so the last input is tested first, and that
    order is kept.
    """
    n = _validate_truth_table(truth_table)
    natural = tuple(reversed(range(n)))
    return _forth_ordered(permute_truth_table(truth_table, natural), natural)


# The read that pushes one normalized input bit.
_FORTH_READ = ",68*-"


#: One internal node, whole.  Entering it the stack is ``.. bit, index``:
#: ``2*1+`` turns the index into the base of its two children, ``+`` adds the
#: bit (selecting one, and consuming it), ``:`` keeps a copy so the callee can
#: do the same, and ``;`` calls -- constant at every depth, which is why the
#: construction is linear.
_FORTH_DISPATCH = "2*1++:;"


# How far a freshly-read bit can sink, and the ops that put it there.  ``v``
# swaps the top two and ``c`` rotates the third up, so two ``c``s bury the new
# bit under the two below it.  ``o`` is absent deliberately: it reverses the
# *whole* stack, dragging the scope indices under the bits up with them.
_FORTH_SINKS = ((0, ""), (1, "v"), (2, "cc"))


@cache
def _forth_stack_programs(n: int) -> dict[tuple[int, ...], str]:
    """Read-and-rotate program for each reachable stack arrangement.

    ``2 * 3**(n - 2)`` arrangements, as :func:`stack_programs`: sinking each
    bit as it arrives reaches 18 at n == 4 and 54 at n == 5, where sinking
    after all the reads permutes only the last three (2.4% at n == 4, none
    at n == 5).  A BFS finds shorter op strings on some arrangements (a late
    ``c`` composes across reads); not used, the natural order is kept.
    """
    return stack_programs(n, _FORTH_SINKS, _FORTH_READ)


def _forth_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's Forþ program; see :func:`forth`.

    ``truth_table`` is already permuted; ``perm`` surfaces only in the
    arrangement the reads must produce (level ``k`` needs ``perm[k]`` on
    top).  Returns ``""`` when unreachable.  The stack is balanced by
    construction and must be: an empty pop halts Forþ, and the definition
    counter sits under the bits.  Each dispatch consumes one bit and one
    index and produces one index.
    """
    n = _validate_truth_table(truth_table)
    wanted = tuple(reversed(perm))
    reads = (
        _FORTH_READ * n
        if wanted == tuple(range(n))
        else _forth_stack_programs(n).get(wanted)
    )
    if reads is None:
        return ""

    last_internal = 2**n - 2
    constant = constant_span_test(truth_table)

    def span_under(m: int) -> tuple[int, int]:
        """Return the table rows the subtree rooted at heap index ``m`` covers.

        Heap index ``m`` at depth ``d`` is the ``m - (2**d - 1)``-th node of
        its level, and covers that many spans of ``2**(n - d)`` rows in; the
        leaf at heap index ``m`` is row ``m - last_internal - 1``.  O(1), so
        the fold test over the whole heap is O(2**n).
        """
        depth = (m + 1).bit_length() - 1
        width = 1 << (n - depth)
        lo = (m - (1 << depth) + 1) * width
        return lo, lo + width

    prog = []
    folded: set[int] = set()
    previous = 0  # the index the accumulator holds; 0 before anything is pushed
    for m in range(1, 2 ** (n + 1) - 1):
        if m in folded:
            # An ancestor answered for this subtree, so its scope is never
            # called; Forþ looks scopes up by pushed number with a default,
            # so the gap in the numbering costs nothing.
            continue
        if m <= last_internal:
            lo, hi = span_under(m)
            if constant(lo, hi):
                # Every row under this node agrees, so answer here and drop
                # the whole subtree -- a grandchild is as unreachable as a
                # child, and marking one level leaves the deeper nodes
                # emitted but never called.  The reads are outside the tree,
                # so a folded program consumes its input as an unfolded one
                # does.
                body = _forth_const(_ASCII_ZERO + int(truth_table[lo]))
                below = [2 * m + 1, 2 * m + 2]
                while below:
                    child = below.pop()
                    folded.add(child)
                    if child <= last_internal:
                        below += [2 * child + 1, 2 * child + 2]
            else:  # internal node: dispatch on the top bit
                body = _FORTH_DISPATCH
        else:  # leaf: push the result byte
            body = _forth_const(_ASCII_ZERO + int(truth_table[m - last_internal - 1]))
        # The label is a step from the index on the stack, never the index
        # itself: ``{`` reads its key without popping, so the pushed number
        # survives the definition and the next one is ``+`` away.
        step = _forth_const(m - previous) + ("+" if previous else "")
        previous = m
        prog.append(step + "{" + body + "}")
    prog.append(reads)  # the reads, with this order's rotations woven in
    prog.append("1+:;.")  # root dispatch, then print the result
    return "".join(prog)


def modulous(truth_table: str) -> str:
    """Build a Modulous program: a table literal popped down to its row."""
    n = _validate_truth_table(truth_table)
    # ``PSH STR`` pushes the characters in reverse, so the leftmost entry is on
    # top and discarding ``index`` of them uncovers ``truth_table[index]`` --
    # the row index read MSB first, which is what the weights below build.  The
    # first read *is* the counter: a bit is already 0 or 1, so the top weight is
    # one conditional ``ADD`` away and no accumulator is pushed.
    top = 1 << (n - 1)
    reads = ["[INP INT]" + (f"[JMP F 2 IF 0][ADD {top - 1}]" if n > 1 else "")]
    reads += [
        f"[INP INT][JMP F 4 IF 0][POP][ADD {1 << (n - 1 - i)}][JMP F 2][POP]"
        for i in range(1, n)
    ]
    # ``SWP``/``POP`` discards the entry *under* the counter, which is what
    # keeps the counter reachable: nothing but the top two cells is.
    walk = "[JMP F 5 IF 0][SUB 1][SWP][POP][JMP B 4][POP][PRT][END]"
    return f'[PSH STR "{truth_table}"]{"".join(reads)}{walk}'


def _bfstack_encoder(n: int, *, preset: bool) -> str:
    """BFStack code turning the n inputs into the number ``1 + sum(bit*2^k)``.

    ``,`` reads, 48 ``-``s normalize, ``[<+w>]`` adds the weight.  The ``+1``
    keeps the result nonzero so the decoder's outer ``[`` always runs, and
    ``preset`` starts it at 1 for the subtracting decoder.
    """
    # Result cell (0, or 1 when the decoder subtracts) below the accumulator.
    prog = ">+>+" if preset else ">>+"
    for k in range(n):
        weight = 2 ** (n - 1 - k)
        prog += "," + "-" * _ASCII_ZERO + "[" + "<" + "+" * weight + ">" + "]" + "<"
    return prog


def _bfstack_cascade(rows: list[int], payload: str) -> str:
    """Nest subtractions over ``rows``, running ``payload`` off the list.

    Reaching zero on a listed row leaves that row's ``[`` unentered, so
    ``payload`` runs exactly when the encoded number is not in ``rows``.
    """
    if not rows:
        return payload
    prog = "["
    prev = 0
    for row in rows:
        prog += "-" * (row - prev) + "["
        prev = row
    return prog + payload + "]" * (len(rows) + 1)


def _bfstack_decoder(truth_table: str) -> tuple[str, bool]:
    """Return the decoder, and whether the result must start at 1.

    A listed row costs the gap to the one before it and two brackets, so
    listing the *zero* rows made a mostly-zero table the expensive case --
    backwards: at twelve inputs it cost 17,091 characters against 4,801 for
    the all-one table.  Listing the one rows inverts the cascade, which
    starting the result at 1 and subtracting undoes; ties keep the direct form.
    """
    zeros = [k + 1 for k, ch in enumerate(truth_table) if ch == "0"]
    ones = [k + 1 for k, ch in enumerate(truth_table) if ch == "1"]
    direct = _bfstack_cascade(zeros, "[<+>]")
    # One character dearer than it looks: the preset ``+`` in the encoder.
    inverted = _bfstack_cascade(ones, "[<->]")
    if len(inverted) + 1 < len(direct):
        return inverted, True
    return direct, False


def bfstack(truth_table: str) -> str:
    """Build a BFStack program computing the given truth table.

    No branching: encode the inputs as ``1 + sum(bit*2^k)``, then nested
    ``[`` loops single out the rows of whichever result value is rarer.
    """
    n = _validate_truth_table(truth_table)
    decoder, preset = _bfstack_decoder(truth_table)
    return _bfstack_encoder(n, preset=preset) + decoder + "<" + "+" * _ASCII_ZERO + "."


def unsquare(truth_table: str) -> str:
    """Build an Unsquare program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  The
    table goes on the stack as one ``O``/``I`` a row, reversed, so row ``r``
    sits ``r`` cells below the top, and each read pops its bit's weight off
    the top: two bytes a row, against 32.5 for routing a decision tree.

    ``>-<`` takes 2 off the accumulator while it is neither 0 nor 1, landing
    the input character on its parity; ``x`` doubles that bit, so ``>`` runs
    the pops only when it is 1 and ``OA`` zeroes the accumulator for the
    returning ``<``.  The pops cannot underflow: the largest index is
    ``2**m - 1`` against ``2**m`` cells.
    """
    n = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, n) or [0]
    reduced = read_at(truth_table, used, n)
    cells = "".join("I" if entry == "1" else "O" for entry in reversed(reduced))
    blocks: list[str] = []
    for index in range(n):
        if index in used:
            weight = 1 << (len(used) - 1 - used.index(index))
            blocks.append("iA>-<x>" + "A" * weight + "OA<")
        else:
            blocks.append("iA")  # consume the line, leave the stack alone
    return cells + "".join(blocks) + "A" + "+" * (_ASCII_ZERO // 2) + "Po"
