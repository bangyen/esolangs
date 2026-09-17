"""Boolean-function generator for Eval.

Named ``eval_lang`` because the generator itself is called ``eval``, and a
module of that name reads as the builtin wherever it is imported.
"""

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    permute_truth_table,
    read_at,
)

# Eval's two stacks and the ops that move values between them.  ``~`` swaps
# which stack is active, ``*`` reverses the active one, and ``=`` pops the
# active stack onto the other.  The pair is a spindle: moving values across
# reverses them, so composing the three reaches essentially any arrangement.
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


def _eval_dependencies(truth_table: str) -> list[int]:
    """Return essential levels in one bottom-up pass over the table."""
    n = _validate_truth_table(truth_table)
    nodes = [int(bit) for bit in truth_table]
    used: list[int] = []
    ids: dict[tuple[int, int], int] = {}
    next_id = 2
    for level in reversed(range(n)):
        parents: list[int] = []
        matters = False
        for index in range(0, len(nodes), 2):
            pair = (nodes[index], nodes[index + 1])
            matters |= pair[0] != pair[1]
            node = ids.get(pair)
            if node is None:
                node = next_id
                ids[pair] = node
                next_id += 1
            parents.append(node)
        if matters:
            used.append(level)
        nodes = parents
    return list(reversed(used))


def _eval_ordered(truth_table: str, ops: str) -> str:
    """Emit one input order's linear lookup; see :func:`eval`."""
    n = _validate_truth_table(truth_table)
    used = _eval_dependencies(truth_table)
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
