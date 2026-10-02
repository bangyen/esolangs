"""Boolean program generator for Forþ."""

from functools import cache
from itertools import product

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    constant_span_test,
    permute_truth_table,
    subtree_ids,
)

Sinks = tuple[tuple[int, str], ...]


def _sink_top(stack: tuple[int, ...], places: int) -> tuple[int, ...]:
    """Move the top bit down by ``places``, leaving the others in order."""
    *below, top = stack
    at = len(below) - places
    return (*below[:at], top, *below[at:])


def stack_programs(n: int, sinks: Sinks, read: str) -> dict[tuple[int, ...], str]:
    """Map input-index stacks (bottom to top) to read-and-sink programs.

    ``sinks`` pairs places with ops; ``read`` pushes a bit. Each read can
    sink 0, 1 or 2 places, so the product yields ``2 * 3**(n - 2)``
    arrangements for ``n >= 2``; no search.
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

    Binary ``2**n`` entries, MSB first; prints ``'0'``/``'1'``. Reads use
    ``,68*-``; ``{scope}`` stores its unpopped key; ``;`` pops and calls.
    Heap children of ``m`` are ``2m+1``/``2m+2``; definitions advance by ``1+``.
    The linear tree tests the last bit first; ``2*1++:;`` keeps the callee's key.
    Leaves push ``48+result`` for ``.``; same-level twins use ``_FORTH_SHARE``.
    One removed scope pays for a merged step; two children pay for sharing.
    """
    n = _validate_truth_table(truth_table)
    natural = tuple(reversed(range(n)))
    table = permute_truth_table(truth_table, natural)
    return _forth_ordered(table, natural, share=True)


# The read that pushes one normalized input bit.
_FORTH_READ = ",68*-"


#: Enter with ``.. bit, index``: ``2*1+`` finds children; ``+`` consumes the bit.
#: ``:`` duplicates the selected index; ``;`` calls. The cost is constant at
#: every depth, so the construction is linear.
_FORTH_DISPATCH = "2*1++:;"

#: A repeated node's body: ``-`` its distance back turns its index into its
#: twin's, whose dispatch reaches the twin's children, so none is re-emitted.
_FORTH_SHARE = "{}-:;"

#: The least a subtree spends inline (a dispatch, two ``1+{0}`` scopes); a
#: call is kept only when shorter, the local rule.
_FORTH_SUBTREE_FLOOR = len(_FORTH_DISPATCH) + 2 * len("1+{0}")


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


def _forth_ordered(
    truth_table: str, perm: tuple[int, ...], *, share: bool = False
) -> str:
    """Emit a permuted Forþ table, or ``""`` if its input order is unreachable.

    Level ``k`` needs ``perm[k]`` on top; the counter stays below the bits.
    Empty pops halt Forþ. Dispatch consumes bit and index, returning an index.
    Sharing calls the nearest emitted twin with equal subtable and level.
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

    def fold_below(m: int) -> None:
        """Drop every scope under ``m``, grandchildren too, as unreachable."""
        below = [2 * m + 1, 2 * m + 2]
        while below:
            child = below.pop()
            folded.add(child)
            if child <= last_internal:
                below += [2 * child + 1, 2 * child + 2]

    ids = subtree_ids(truth_table) if share else []
    # Heap order is level order, so a twin is at the same level; a folded
    # scope is never recorded, so a call lands on a defined one.
    emitted: dict[int, int] = {}
    previous = 0  # the index the accumulator holds; 0 before anything is pushed
    for m in range(1, 2 ** (n + 1) - 1):
        if m in folded:
            # An ancestor answered for this subtree, so its scope is never
            # called; Forþ looks scopes up by pushed number with a default,
            # so the gap in the numbering costs nothing.
            continue
        if m <= last_internal:
            lo, hi = span_under(m)
            depth = (m + 1).bit_length() - 1
            key = ids[depth][m + 1 - (1 << depth)] if share else -1
            twin = emitted.get(key) if share else None
            call = _FORTH_SHARE.format(_forth_const(m - twin)) if twin else ""
            if constant(lo, hi):
                # Every row under this node agrees, so answer here.  The
                # reads are outside the tree, so a folded program consumes
                # its input as an unfolded one does.
                body = _forth_const(_ASCII_ZERO + int(truth_table[lo]))
                fold_below(m)
            elif call and len(call) < _FORTH_SUBTREE_FLOOR:
                # The twin's subtree already answers for this one.
                body = call
                fold_below(m)
            else:  # internal node: dispatch on the top bit
                body = _FORTH_DISPATCH
            emitted[key] = m
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
