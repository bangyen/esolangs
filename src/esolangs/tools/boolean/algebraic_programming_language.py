"""Boolean-function generator for Algebraic Programming Language."""

from esolangs.tools.boolean.helpers import _validate_truth_table, best_input_order

# : The variable names inputs.
# : them.
# : names must appear in.
# :.
# : The wiki allows "any.
# : Greek letters" as a.
# : letters.
# : covers any arity a minterm.
# : already a ``2**54``-row.
# : deliberately: they are.
# : confusable with Latin a and.
# : says so), and there is no.
# :.
# : The sequence is.
# : on: literals are sorted by.
# : ``b``, and a non-monotone.
_NAMES = "abcdefghijklmnopqrstuvwxyzàáâãäåæçèéêëìíîïñòóôõöøùúûüý"

# : The complement operator,.
_NOT = "!x = {\nx & $0\n$1\n}"


def algebraic_programming_language(truth_table: str, width: int | None = None) -> str:
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
    return best_input_order(
        truth_table, lambda table, perm: _apl_ordered(table, perm, width)
    )


def _apl_name(index: int) -> str:
    """Return the ``index``-th function name: an uppercase run, A..Z, AA, AB.

    A function name is a *run of uppercase letters* -- the parser takes the
    longest one -- so there are no digits to spell an index with and the
    names count in base 26 instead.
    """
    name = ""
    while True:
        name = chr(ord("A") + index % 26) + name
        index = index // 26 - 1
        if index < 0:
            return name


def _apl_ordered(
    truth_table: str, perm: tuple[int, ...], width: int | None = None
) -> str:
    """Emit one input order's APL program.

    See :func:`algebraic_programming_language`.
    """
    n = _validate_truth_table(truth_table)
    rows = [row for row, bit in enumerate(truth_table) if bit == "1"]
    if not rows:
        # The constant-0 table needs no.
        # generator must read its ``n``.
        # replaced by an expression.
        body = " & ".join(f"!!{_NAMES[i]}" for i in range(n)) + " & 0"
        return f"{_NOT}\n{body}"
    terms = []
    for row in rows:
        literals = []
        for level in range(n):
            # ``perm`` says which input.
            # in the permuted frame, so the.
            bit = (row >> (n - 1 - level)) & 1
            name = _NAMES[perm[level]]
            literals.append(f"!!{name}" if bit else f"!{name}")
        terms.append(sorted(literals, key=_order_key))
    flat = " | ".join("(" + " & ".join(t) + ")" for t in terms)
    if width is None or len(flat) <= width:
        return f"{_NOT}\n{flat}"
    return f"{_NOT}\n" + _apl_narrowed(terms, n, width)


def _apl_narrowed(terms: list[list[str]], n: int, width: int) -> str:
    """Spread the minterm sum over definitions until every line fits.

    An uppercase name defined without parentheses is a nullary function, so
    any subexpression can be given a line of its own and called back in
    four characters.  Definitions are not executed and so print nothing,
    which is what makes this legal at all: the language prints *every*
    executed line, so the sum cannot simply be split across several.

    What cannot move off the executed line is the *reading*.  A variable is
    read by appearing on an executed line, and the interpreter binds every
    unbound one there in a pre-scan before evaluating -- so a variable that
    only ever appeared inside a definition would be unbound when the call
    reached it.  The line therefore keeps a prefix naming every input in
    order.  ``a & b & ... & 0`` is always 0, whichever way it
    short-circuits, and ``0 | rest`` is ``rest``, so the prefix reads the
    inputs and contributes nothing to the answer.  That prefix is also the
    floor: it cannot be split, and it grows with ``n``.
    """
    named: list[str] = []
    reads = " & ".join(_NAMES[i] for i in range(n)) + " & 0"
    # Splitting below the floor.
    # names, and the executed line.
    # what a width under it is.
    # a *wider* program than asking.
    # it can build" should mean.
    limit = max(width, len(reads) + 9)
    # Definitions are bounded by.
    # and the prefix has to be.
    # can reach rather than the.
    # than it is built, so the.
    bound = 4 * len(terms) * (n + 1) + 4
    head = len(f"{_apl_name(bound)} = ")

    def define(text: str) -> str:
        """Bind ``text`` to a fresh nullary name and return the call."""
        name = _apl_name(len(named))
        named.append(f"{name} = {text}")
        return f"{name}()"

    def fold(parts: list[str], op: str) -> str:
        """Join ``parts`` with ``op``, halving into definitions until it fits.

        Splitting is what shortens a line, so a part that is still too long
        is named rather than joined -- and a name is four characters, which
        is why halving terminates.
        """
        if len(parts) == 1:
            return parts[0]
        text = op.join(parts)
        if head + len(text) <= limit:
            return text
        half = (len(parts) + 1) // 2
        left = define(fold(parts[:half], op))
        right = define(fold(parts[half:], op))
        return op.join([left, right])

    products = [fold(literals, " & ") for literals in terms]
    # A product that stayed inline.
    # it; one that became a call.
    summands = [part if part.endswith("()") else f"({part})" for part in products]
    body = fold(summands, " | ")
    if len(reads) + len(body) + 6 > limit and not body.endswith("()"):
        # The executed line carries the.
        # the one line ``fold`` cannot.
        body = define(body)
    return "\n".join([*named, f"({reads}) | {body}"])


def _order_key(literal: str) -> tuple[str, int]:
    """Sort literals by the variable they name, so reads stay ascending."""
    name = literal.lstrip("!")
    return (name, len(literal))
