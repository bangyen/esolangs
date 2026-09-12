r"""Boolean-function generator for Algebraic Programming Language."""

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
    r"""Build an APL program computing the given truth table."""
    return best_input_order(
        truth_table, lambda table, perm: _apl_ordered(table, perm, width)
    )


def _apl_name(index: int) -> str:
    r"""Return the ``index``-th function name: an uppercase run, A..Z, AA,."""
    name = ""
    while True:
        name = chr(ord("A") + index % 26) + name
        index = index // 26 - 1
        if index < 0:
            return name


def _apl_ordered(
    truth_table: str, perm: tuple[int, ...], width: int | None = None
) -> str:
    r"""Emit one input order's APL program."""
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
    r"""Spread the minterm sum over definitions until every line fits."""
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
        r"""Bind ``text`` to a fresh nullary name and return the call."""
        name = _apl_name(len(named))
        named.append(f"{name} = {text}")
        return f"{name}()"

    def fold(parts: list[str], op: str) -> str:
        r"""Join ``parts`` with ``op``, halving into definitions until it fits."""
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
    r"""Sort literals by the variable they name, so reads stay ascending."""
    name = literal.lstrip("!")
    return (name, len(literal))
