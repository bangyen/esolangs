"""Eval Boolean program generator: a literal table halved once per input.

The table's bits are pushed on one stack and each input halves it (a zero
discards the top half; a one reverses, discards, reverses back).  The halves
are `;` runs totalling T/2 + T/4 + ... < T, shared by both branches by
duplicating the input.

From n = 4, when enough inputs are essential, the top input selects a stack
instead of a half: the lower half goes on one stack and the upper on the
other, every input is staged on both, and a conditional `~` leaves the chosen
half exposed.  The first halving's T/2 discards become n-1 copy discards.  A
one on the second stack costs `0+` (`^` extends a run), since `` ` `` pushes
0 there.

Size:
    About 1.75T chars from n=4 (2T below), no subtrees to fold or share;
    n=10 random 1847: 1,814 chars, n=16 and: 98,540 chars.
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
    table = permute_truth_table(truth_table, tuple(reversed(range(n))))
    used = essential_inputs(table, n)
    # Never longer than the one-stack build: it saves 2**(k-2) - runs - 2n + 5
    # >= 0 when 2**k >= 8n - 20 (k essential inputs, top one among them).
    if n >= 4 and 0 in used and 2 ** len(used) >= 8 * n - 20:
        return _eval_dual(table, used, n)
    return _eval_ordered(table, "")


def eval_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Return the per-input pair: three wide in the two-stack build."""
    # Only the two-stack build holds ``~;~?~``; the one-stack drains are
    # followed by ``~^=~?*`` or ``.``.
    dual = _DUAL_SELECT in template.replace("\n", "")
    return ((DUAL_PAIR if dual else PAIR),) * n


def _eval_dual(table: str, used: list[int], n: int) -> str:
    """Emit the two-stack lookup: the top input picks the stack holding its half."""
    reduced = read_at(table, used, n)
    half = len(reduced) // 2
    lower, upper = reduced[:half], reduced[half:]
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
        out.extend(("~^=~?*", ";" * remaining, "~=~?*"))
    out.append(".")
    return "".join(out)


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
    example=Example(setters=eval_setters),
)
