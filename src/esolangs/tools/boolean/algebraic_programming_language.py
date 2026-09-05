"""Boolean-function generator for Algebraic Programming Language."""

from esolangs.tools.boolean.helpers import _validate_truth_table, best_input_order

#: The variable names inputs are read into, in the order the harness feeds
#: them.  APL binds a variable by *naming* it on an executed line, so the
#: names must appear in ascending order in the program text.
#:
#: The wiki allows "any lowercase Latin (including accents), Cyrillic, or
#: Greek letters" as a variable, so the alphabet is not the 26 ASCII
#: letters.  The accented Latin range is appended, which more than
#: covers any arity a minterm sum can materialize -- ``n == 54`` is
#: already a ``2**54``-row table.  Cyrillic and Greek are left out
#: deliberately: they are legal, but Greek alpha and Cyrillic u are
#: confusable with Latin a and y in a generated program (ruff's RUF001
#: says so), and there is no arity that needs them.
#:
#: The sequence is codepoint-ascending, which :func:`_order_key` relies
#: on: literals are sorted by name so the emitted line names ``a`` before
#: ``b``, and a non-monotone alphabet would put the reads out of order.
_NAMES = "abcdefghijklmnopqrstuvwxyzàáâãäåæçèéêëìíîïñòóôõöøùúûüý"

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

    Each literal carries its own normalization rather than a separate pass:
    a 1-bit is spelled ``!!a`` and a 0-bit ``!a``, so an input fed as any
    non-zero number behaves the same; the harness feeds 0 and 1, but the
    table's semantics should not rest on that.

    **The tree splits on its inputs in whichever order emits the shortest
    program** (:func:`~esolangs.tools.boolean.helpers.best_input_order`).
    The *reads* are unaffected: a variable is read when the line first
    names it, and the emitted line always names ``a`` before ``b``, so
    reordering changes which minterm literal comes first, never the input
    order.

    **The construction is total**, and structurally rather than by
    search.  Every table is the disjunction of one term per ``1`` row,
    each term the conjunction of ``n`` literals, and the choice of
    literal is decided bit by bit from the row index -- so there is no
    table shape that can fail to expand, no staging to miss a case, and
    no arity at which the emission stops working.  The two boundaries
    are handled explicitly: a table with no ``1`` rows takes the
    constant-zero branch below, and a table with every row set expands
    to ``2**n`` terms like any other.

    **What bounds it is size, not reach.**  The program is about
    ``n * 2**(n-1)`` characters, and the *table* is ``2**n`` -- so the
    arity that exhausts memory arrives far below the point where
    :data:`_NAMES` runs out.  Running out of names would need a table of
    ``2**55`` rows, which cannot be constructed to pass in, so there is
    no alphabet check here: it would be a guard no argument could reach.
    """
    return best_input_order(truth_table, _apl_ordered)


def _apl_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's APL program.

    See :func:`algebraic_programming_language`.
    """
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
