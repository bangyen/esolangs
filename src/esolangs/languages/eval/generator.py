"""Eval Boolean program generator: a literal table halved once per input.

The table's bits are pushed on one stack and each input halves it (a zero
discards the top half; a one reverses, discards, reverses back).  The halves
are `;` runs totalling T/2 + T/4 + ... < T, shared by both branches by
duplicating the input.

Size:
    About 2T chars, no subtrees to fold or share; n=10 random 1847: 2,178
    chars, n=16 and: 131,280 chars.
"""

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    essential_inputs,
    permute_truth_table,
    read_at,
)
from esolangs.generation.wrap import _quote_literal
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

# ``~`` swaps the active stack, ``*`` reverses it, ``=`` pops it onto the
# other.  Moving values across reverses them (tests/eval_support.py).
_EVAL_TREE_STACK, _EVAL_READ_STACK = 0, 1

#: Stage the bit on the tree stack (``0`` or backtick), ``=`` moves it to the
#: input stack.  Each input is a run of :data:`TEMPLATE_CHAR` this wide.
PAIR = ("0=", "`=")
_EVAL_INPUT = TEMPLATE_CHAR * len(PAIR[0])


def eval(truth_table: str) -> str:  # noqa: A001 - the language is named "Eval"
    """Build an Eval template for the given truth table.

    Inputs index the table most significant first; the program prints
    ``'0'`` or ``'1'``.

    Each placeholder stages one equal-width bit on the input stack; ignored
    inputs are drained, except a constant's, which no halving step reads.
    """
    n = _validate_truth_table(truth_table)
    table = permute_truth_table(truth_table, tuple(reversed(range(n))))
    return _eval_ordered(table, "")


def _eval_ordered(truth_table: str, ops: str) -> str:
    """Emit one input order's linear lookup; see :func:`eval`."""
    n = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, n)
    reduced = read_at(truth_table, used, n)
    bits = _EVAL_INPUT * n
    values = "".join("`" if bit == "1" else "0" for bit in reduced)
    out = [bits, ops, values]
    remaining = len(reduced)
    used_set = set(used)
    for level in range(n):
        if level not in used_set:
            # A constant's drains are dead weight: no halving step swaps
            # back to the read stack, so staged inputs sit until ``.``
            # (5n+2 -> 2n+2, measured n = 2..8).  With an essential input
            # the drains stay -- dropping them would let a reordered
            # build win (n = 3, 00001111: 24 vs 27), breaking no-reorder.
            if used_set:
                out.append("~;~")
            continue
        remaining //= 2
        out.extend(("~^=~?*", ";" * remaining, "~=~?*"))
    out.append(".")
    return "".join(out)


LANGUAGE = Language(
    "Eval",
    "eval",
    category="stack_based",
    boolean=eval,
    contract=BooleanContract(),
    # Print through a literal that must not be broken.
    wrap=_quote_literal,
    example=Example(pair=PAIR),
)
