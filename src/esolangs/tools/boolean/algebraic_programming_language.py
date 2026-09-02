"""Boolean-function generator for Algebraic Programming Language."""

from esolangs.tools.boolean.helpers import _validate_truth_table, best_input_order

#: The variable names inputs are read into, in the order the harness feeds
#: them.  APL binds a variable by *naming* it on an executed line, so the
#: names must appear in ascending order in the program text.
_NAMES = "abcdefghijklmnopqrstuvwxyz"

#: The complement operator, spelled exactly as the wiki spells it.
_NOT = "!x = {\nx & $0\n$1\n}"


def algebraic_programming_language(truth_table: str) -> str:
    """Build an APL program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    APL has neither an input command nor an output command.  A variable is
    read from stdin by *appearing* on an executed line, and that line's
    result is printed, so the whole program is a header of definitions
    plus **one** executed expression -- the truth table as a sum of
    minterms over ``&``, ``|``, and the wiki's own ``!``.

    Every value stays 0 or 1: ``!`` returns exactly one of them, ``&``
    returns 0 or its right operand, and ``|`` returns its left operand or
    its right.  So the printed result is the table's bit, and nothing
    depends on how the language spells a non-zero truth value.

    A leading ``NORM`` normalizes each input to 0/1 (``!!a``) so an input
    fed as any non-zero number behaves the same; the harness feeds 0 and
    1, but the table's semantics should not rest on that.

    **The tree splits on its inputs in whichever order emits the shortest
    program** (:func:`~esolangs.tools.boolean.helpers.best_input_order`).
    The *reads* are unaffected: a variable is read when the line first
    names it, and the emitted line always names ``a`` before ``b``, so
    reordering changes which minterm literal comes first, never the input
    order.
    """
    return best_input_order(truth_table, _apl_ordered)


def _apl_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's APL program; see :func:`algebraic_programming_language`."""
    n = _validate_truth_table(truth_table)
    rows = [row for row, bit in enumerate(truth_table) if bit == "1"]
    if not rows:
        # The constant-0 table needs no inputs read at all... but every
        # generator must read its ``n`` inputs, so the minterms are
        # replaced by an expression that names each one and yields 0.
        body = " & ".join(f"!!{_NAMES[i]}" for i in range(n)) + " & 0"
        return f"{_NOT}\n{body}"
    terms = []
    for row in rows:
        literals = []
        for level in range(n):
            # ``perm`` says which input this level tests; the row index is
            # in the permuted frame, so the bit comes from the level.
            bit = (row >> (n - 1 - level)) & 1
            name = _NAMES[perm[level]]
            literals.append(f"!!{name}" if bit else f"!{name}")
        terms.append(" & ".join(sorted(literals, key=_order_key)))
    body = " | ".join(f"({t})" for t in terms)
    return f"{_NOT}\n{body}"


def _order_key(literal: str) -> tuple[str, int]:
    """Sort literals by the variable they name, so reads stay ascending."""
    name = literal.lstrip("!")
    return (name, len(literal))
