"""Boolean-function generator for Eval.

Named ``eval_lang`` because the generator itself is called ``eval``, and a
module of that name reads as the builtin wherever it is imported.
"""

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    essential_inputs,
    permute_truth_table,
    read_at,
)

# Eval's two stacks and the ops that move values between them.  ``~`` swaps
# which stack is active, ``*`` reverses the active one, and ``=`` pops the
# active stack onto the other.  The pair is a spindle: moving values across
# reverses them (tests/tools/eval_reorders.py composes them).
_EVAL_TREE_STACK, _EVAL_READ_STACK = 0, 1

#: How each input is set: stage the bit on the tree stack (``0`` pushes a
#: zero, the backtick a one), then ``=`` moves it to the input stack.  The
#: template spells each input as a run of :data:`TEMPLATE_CHAR` this wide.
PAIR = ("0=", "`=")
_EVAL_INPUT = TEMPLATE_CHAR * len(PAIR[0])


def eval(truth_table: str) -> str:  # noqa: A001 - the language is named "Eval"
    """Build an Eval template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  The program prints ``'0'`` or ``'1'``.

    Each placeholder stages one equal-width bit on the input stack; the
    table's bits are pushed on the other stack and each input halves it (a
    zero discards the top half; a one reverses, discards, reverses back).
    Duplicating the input lets both branches share one semicolon run,
    totalling ``T/2 + T/4 + ... < T``; ignored inputs are drained after one
    bottom-up dependency pass.
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
            out.append("~;~")
            continue
        remaining //= 2
        out.extend(("~^=~?*", ";" * remaining, "~=~?*"))
    out.append(".")
    return "".join(out)
