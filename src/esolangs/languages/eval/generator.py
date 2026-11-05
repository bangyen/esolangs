"""Eval Boolean program generator: a literal table halved once per input.

The table is stored in Gray order. A zero discards the top half; a one
reverses then discards it, leaving that half reversed. Carried reversals
complement the lower index bits, which the Gray layout compensates. Each
halving consumes its input copy without a restoring reversal.

When enough inputs are essential (from n=6), the top input selects a stack:
the lower half goes on one stack and the upper on the other. Each half has
its own Gray layout. Every input is staged on both stacks, and a conditional
``~`` exposes the chosen half. A one on the second stack costs ``0+``;
``^`` extends a run, since backtick pushes zero there.

Size:
    About 1.75T chars from n=6 (2T below), no subtrees to fold or share;
    n=10 random 1847: 1,754 chars, n=16 and: 98,450 chars.
    Constants: n + 2 chars, n + 3 commands including frame completion.
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
from esolangs.registry._language import Language, TemplateSpec

# ``~`` swaps the active stack, ``*`` reverses it, ``=`` pops it onto the
# other.  Moving values across reverses them (tests/eval_support.py).
_EVAL_TREE_STACK, _EVAL_READ_STACK = 0, 1

#: Stage the bit on the tree stack (``0`` or backtick), ``=`` moves it to the
#: input stack.  Each input is a run of :data:`TEMPLATE_CHAR` this wide.
PAIR = ("0=", "`=")
_EVAL_INPUT = TEMPLATE_CHAR * len(PAIR[0])

#: The two-stack build stages each bit on both stacks (``^`` copies it).
DUAL_PAIR = ("0^=", "`^=")
_DUAL_INPUT = TEMPLATE_CHAR * len(DUAL_PAIR[0])
_DUAL_SELECT = "~;~?~"


def eval(truth_table: str) -> str:  # noqa: A001 - the language is named "Eval"
    """Build an Eval template for the given truth table.

    Inputs index the table most significant first; the program prints
    ``'0'`` or ``'1'``.

    Each placeholder stages one equal-width bit on the input stack; ignored
    inputs are drained, except a constant's, which no halving step reads.
    """
    n = _validate_truth_table(truth_table)
    if truth_table.count(truth_table[0]) == len(truth_table):
        return TEMPLATE_CHAR * n + ("0" if truth_table[0] == "0" else "`") + "."
    table = permute_truth_table(truth_table, tuple(reversed(range(n))))
    used = essential_inputs(table, n)
    # With carried orientation, the two-stack saving is R/2-runs-2n-1.
    # At most R/4 one-runs makes R>=8n+4 sufficient, without a program race.
    if 0 in used and 2 ** len(used) >= 8 * n + 4:
        return _eval_dual(table, used, n)
    return _eval_ordered(table, "")


def eval_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Return the per-input pair: three wide in the two-stack build."""
    # Only the two-stack build holds ``~;~?~``; the one-stack drains are
    # followed by ``~=~?*`` or ``.``.
    clean = template.replace("\n", "")
    if (
        len(clean) == n + 2
        and clean[-2:] in ("0.", "`.")
        and not clean[:-2].strip("$0`")
    ):
        return (("0", "`"),) * n
    dual = _DUAL_SELECT in clean
    return ((DUAL_PAIR if dual else PAIR),) * n


def _gray_order(table: str) -> str:
    """Compensate prefix-XOR orientation by storing table[Gray(i)] at i."""
    # [ablations.trick_prototype_20261102_orientation_carry]
    return "".join(table[i ^ (i >> 1)] for i in range(len(table)))


def _eval_dual(table: str, used: list[int], n: int) -> str:
    """Emit the two-stack lookup: the top input picks the stack holding its half."""
    reduced = read_at(table, used, n)
    half = len(reduced) // 2
    lower, upper = _gray_order(reduced[:half]), _gray_order(reduced[half:])
    out = ["".join("`" if bit == "1" else "0" for bit in lower), "~"]
    previous = "0"
    for bit in upper:
        out.append("0" if bit == "0" else "^" if previous == "1" else "0+")
        previous = bit
    out.extend(("~", _DUAL_INPUT * n, _DUAL_SELECT, ";" * (n - 1)))
    used_set = set(used)
    remaining = half
    for level in range(1, n):
        if level not in used_set:
            out.append("~;~")
            continue
        remaining //= 2
        out.extend(("~=~?*", ";" * remaining))
    out.append(".")
    return "".join(out)


def _eval_ordered(truth_table: str, ops: str) -> str:
    """Emit one input order's linear lookup; see :func:`eval`."""
    n = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, n)
    reduced = read_at(truth_table, used, n)
    bits = _EVAL_INPUT * n
    values = "".join("`" if bit == "1" else "0" for bit in _gray_order(reduced))
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
        out.extend(("~=~?*", ";" * remaining))
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
    template=TemplateSpec(setters=eval_setters),
)
