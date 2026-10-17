"""Forþ Boolean program generator: a heap of numbered scopes dispatched by index.

Scope ``m`` (children ``2m+1``, ``2m+2``) is a ``{...}`` labelled a step past
the previous one (definitions advance by ``1+``); ``{scope}`` stores its
unpopped key and ``;`` pops and calls.  Internal scopes share one dispatch,
``2*1++:;``, which consumes a bit and an index, keeps the callee's key and
calls the child; leaves push ``48+result`` for ``.``.
Constant subtrees collapse to a leaf; a same-level twin is called by distance
(``{}-:;``) when that beats inlining.  An ignored input is read and dropped.

Size:
    O(T) dense, near-linear in n for parity and and; n=10 parity: 444 chars,
    n=10 and: 292 chars, n=10 random 1847: 5,141 chars.
"""

from collections import deque

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    constant_span_test,
    input_weights,
    permute_truth_table,
    subtree_ids,
)
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._language import Language


def _forth_const(value: int) -> str:
    """Forþ code pushing ``value`` (base-15 digits built with Horner's rule)."""
    high, low = divmod(value, 15)
    digit = "0123456789ABCDE"[low]
    return _forth_const(high) + "F*" + digit + "+" if high else digit


def for_thorn(truth_table: str) -> str:
    """Build a Forþ program printing ``'0'``/``'1'``; ``2**n`` entries, MSB first."""
    n = _validate_truth_table(truth_table)
    weights, table = input_weights(truth_table, n)
    if len(table) == 1:
        # A constant already folds to one scope; it keeps every input.
        weights, table = [1] * n, truth_table
    # The linear tree tests the last bit first; same-level twins use _FORTH_SHARE.
    natural = tuple(reversed(range(len(table).bit_length() - 1)))
    reads = "".join(_FORTH_READ if weight else _FORTH_DROP for weight in weights)
    return _forth_ordered(permute_truth_table(table, natural), reads, share=True)


#: Read a bit: ``,`` then subtract 48 (``68*``).
_FORTH_READ = ",68*-"
#: The read that drops an ignored input: zero it and add it to the value
#: below, a bit or, under the first read, the last scope's label.
_FORTH_DROP = ",0*+"


#: Enter with ``.. bit, index``: ``2*1+`` finds children; ``+`` consumes the bit.
#: ``:`` duplicates the selected index; ``;`` calls. The cost is constant at
#: every depth, so the construction is linear.
_FORTH_DISPATCH = "2*1++:;"

#: A repeated node's body: ``-`` its distance back turns its index into its
#: twin's, whose dispatch reaches the twin's children, so none is re-emitted.
_FORTH_SHARE = "{}-:;"

#: A lower bound on a subtree's inline cost (a dispatch, two ``1+{0}`` scopes); a
#: call is kept only when shorter, the local rule.
_FORTH_SUBTREE_FLOOR = len(_FORTH_DISPATCH) + 2 * len("1+{0}")


def _forth_ordered(truth_table: str, reads: str, *, share: bool = False) -> str:
    """Emit a Forþ table whose inputs are read by ``reads``.

    Level ``k`` needs input ``n - 1 - k`` on top; the counter stays below the bits.
    Empty pops halt Forþ. Dispatch consumes bit and index, returning an index.
    Sharing calls the nearest emitted twin with equal subtable and level.
    """
    n = _validate_truth_table(truth_table)
    last_internal = 2**n - 2
    constant = constant_span_test(truth_table)

    prog = []
    pending = deque((1, 2))

    ids = subtree_ids(truth_table) if share else []
    # Heap order is level order, so a twin is at the same level; a folded
    # scope is never recorded, so a call lands on a defined one.
    emitted: dict[int, int] = {}
    previous = 0  # the index the accumulator holds; 0 before anything is pushed
    while pending:
        m = pending.popleft()
        if m <= last_internal:
            depth = (m + 1).bit_length() - 1
            index = m + 1 - (1 << depth)
            lo = index << (n - depth)
            hi = lo + (1 << (n - depth))
            key = ids[depth][index] if share else -1
            twin = emitted.get(key) if share else None
            call = _FORTH_SHARE.format(_forth_const(m - twin)) if twin else ""
            if constant(lo, hi):
                # Every row agrees: answer here.  The reads sit outside the
                # tree, so a folded program still consumes its input.
                body = _forth_const(_ASCII_ZERO + int(truth_table[lo]))
            elif call and len(call) < _FORTH_SUBTREE_FLOOR:
                body = call
            else:
                body = _FORTH_DISPATCH
                pending.extend((2 * m + 1, 2 * m + 2))
            emitted[key] = m
        else:
            body = _forth_const(_ASCII_ZERO + int(truth_table[m - last_internal - 1]))
        # The label is a step from the index on the stack, never the index
        # itself: ``{`` reads its key without popping, so the pushed number
        # survives the definition and the next one is ``+`` away.
        step = _forth_const(m - previous) + ("+" if previous else "")
        previous = m
        prog.append(step + "{" + body + "}")
    prog.append(reads)
    prog.append("1+:;.")
    return "".join(prog)


LANGUAGE = Language(
    "Forþ",
    "for_thorn",
    category="stack_based",
    boolean=for_thorn,
    wrap=wrap_chars,
)
