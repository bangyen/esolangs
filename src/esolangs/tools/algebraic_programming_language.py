"""Boolean-function generator for Algebraic Programming Language."""

from itertools import pairwise

from esolangs.tools.helpers import (
    _validate_truth_table,
    best_input_order,
    subtree_ids,
)

#: Input variable names in harness order; a variable is bound by being
#: named on an executed line, so these must be codepoint-ascending
#: (:func:`_order_key` sorts by name).  The wiki allows accented Latin,
#: Cyrillic and Greek; accented Latin is appended (past any reachable
#: arity), Cyrillic and Greek left out as confusable (RUF001).
_NAMES = "abcdefghijklmnopqrstuvwxyzàáâãäåæçèéêëìíîïñòóôõöøùúûüý"

#: The complement operator, spelled exactly as the wiki spells it.
_NOT = "!x = {\nx & $0\n$1\n}"


def algebraic_programming_language(truth_table: str, width: int | None = None) -> str:
    """Build an APL program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  A
    variable is read from stdin by appearing on an executed line, and the
    line's result is printed.  A folded decision tree selects subtrees with
    ``!x`` and ``x``; the harness feeds 0 or 1, so an input needs no
    normalization and every value stays 0 or 1.  The split order is whichever is
    shortest (:func:`~esolangs.tools.helpers.best_input_order`); the reads
    are unaffected since the line names ``a`` before ``b``.  A zero-valued
    prefix names every input first, preserving binding under folds; O(T)
    size.  Width-constrained output keeps the definition-split minterm form,
    since APL cannot continue an expression across lines.
    """
    if width is not None:
        return best_input_order(
            truth_table, lambda table, perm: _apl_ordered(table, perm, width)
        )
    return best_input_order(truth_table, _apl_best_ordered)


def _apl_best_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Return the shorter of one order's inline tree and its reduced diagram."""
    inline = _apl_tree_ordered(truth_table, perm)
    reduced = _apl_reduced_ordered(truth_table, perm)
    return reduced if len(reduced) < len(inline) else inline


def _apl_tree_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order as a folded, linear-size Boolean tree.

    The pieces go into one flat list, joined once, so the build is O(T)
    rather than a copy of every subtree per level.
    """
    n = _validate_truth_table(truth_table)
    changes = [0]
    for previous, current in pairwise(truth_table):
        changes.append(changes[-1] + (previous != current))
    reads = " & ".join(_NAMES[index] for index in range(n)) + " & 0"
    pieces = [f"{_NOT}\n({reads}) | "]

    def constant(start: int, end: int) -> str | None:
        return truth_table[start] if changes[start] == changes[end - 1] else None

    def tree(start: int, end: int, depth: int) -> None:
        if (value := constant(start, end)) is not None:
            pieces.append(value)
            return
        half = (start + end) // 2
        name = _NAMES[perm[depth]]
        zero, one = constant(start, half), constant(half, end)
        # A constant arm needs no guard of its own: the literal alone when
        # both are, else ``x & f1``, ``!x & f0``, ``!x | f1`` or ``x | f0``.
        if zero is not None and one is not None:
            pieces.append(name if one == "1" else f"!{name}")
        elif zero is not None or one is not None:
            constant_one = (zero or one) == "1"
            literal = name if (one is None) != constant_one else f"!{name}"
            op = "|" if constant_one else "&"
            pieces.append(f"({literal} {op} ")
            if one is None:
                tree(half, end, depth + 1)
            else:
                tree(start, half, depth + 1)
            pieces.append(")")
        else:
            pieces.append(f"((!{name} & ")
            tree(start, half, depth + 1)
            pieces.append(f") | ({name} & ")
            tree(half, end, depth + 1)
            pieces.append("))")

    tree(0, 1 << n, 0)
    return "".join(pieces)


def _apl_name(index: int) -> str:
    """Return the ``index``-th function name: an uppercase run, A..Z, AA, AB.

    Names are uppercase runs, so they count in base 26.
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
    """Emit one input order's APL program (see the public function)."""
    n = _validate_truth_table(truth_table)
    rows = [row for row, bit in enumerate(truth_table) if bit == "1"]
    if not rows:
        # The constant-0 table must still name every input; the
        # expression yields 0.
        body = " & ".join(_NAMES[i] for i in range(n)) + " & 0"
        return f"{_NOT}\n{body}"
    terms = []
    for row in rows:
        literals = []
        for level in range(n):
            # ``perm`` says which input this level tests; the row index is
            # in the permuted frame, so the bit comes from the level.
            bit = (row >> (n - 1 - level)) & 1
            name = _NAMES[perm[level]]
            literals.append(name if bit else f"!{name}")
        terms.append(sorted(literals, key=_order_key))
    flat = " | ".join("(" + " & ".join(t) + ")" for t in terms)
    if width is None or len(flat) <= width:
        return f"{_NOT}\n{flat}"
    return f"{_NOT}\n" + _apl_narrowed(terms, n, width)


def _apl_narrowed(terms: list[list[str]], n: int, width: int) -> str:
    """Spread the minterm sum over definitions until every line fits.

    A nullary definition prints nothing, so a subexpression can be named and
    called in four characters.  Reading cannot move off the executed line
    (variables are bound by a pre-scan there), so the line keeps a prefix
    ``a & b & ... & 0 | rest`` naming every input, which is also the floor.
    """
    named: list[str] = []
    reads = " & ".join(_NAMES[i] for i in range(n)) + " & 0"
    # Below the floor splitting only lengthens names (asking for 1 gave a
    # wider program than 20), so a smaller width is raised to it.
    limit = max(width, len(reads) + 9)
    # Budget the prefix against the longest name the tree can reach, since
    # a subexpression is named later than it is built.
    bound = 4 * len(terms) * (n + 1) + 4
    head = len(f"{_apl_name(bound)} = ")

    def define(text: str) -> str:
        """Bind ``text`` to a fresh nullary name and return the call."""
        name = _apl_name(len(named))
        named.append(f"{name} = {text}")
        return f"{name}()"

    def fold(parts: list[str], op: str) -> str:
        """Join ``parts`` with ``op``, halving into definitions until it fits.

        A name is four characters, which is why halving terminates.
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
    # A product that stayed inline keeps the brackets the flat form gives
    # it; one that became a call does not need them.
    summands = [part if part.endswith("()") else f"({part})" for part in products]
    body = fold(summands, " | ")
    if len(reads) + len(body) + 6 > limit and not body.endswith("()"):
        # The executed line carries the prefix as well as the sum, so it is
        # the one line ``fold`` cannot have budgeted for.
        body = define(body)
    return "\n".join([*named, f"({reads}) | {body}"])


def _order_key(literal: str) -> tuple[str, int]:
    """Sort literals by the variable they name, so reads stay ascending."""
    name = literal.lstrip("!")
    return (name, len(literal))


Key = tuple[int, int]
#: A half as a node reached through it and whether it arrives complemented.
Ref = tuple[Key, bool]


def _apl_reduced_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order as a reduced diagram.

    The tree of :func:`_apl_tree_ordered`, reduced: a node whose halves
    agree is that half -- the reads prefix binds every input, so dropping a
    test drops no read -- and a node that complements one already built at
    its level is ``!`` of it.  Nodes are interned bottom-up from
    :func:`~esolangs.tools.helpers.subtree_ids`, a dict lookup a node, and
    each piece is emitted once per use as the inline tree emits it: O(T).
    """
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)
    reads = " & ".join(_NAMES[index] for index in range(n)) + " & 0"
    # A node's (test, zero half, one half); ``ref`` sends every subtable to
    # the node that spells it, and ``made`` finds a node by its halves.
    split: dict[Key, tuple[str, Ref, Ref]] = {}
    ref: dict[Key, Ref] = {}
    made: dict[tuple[int, Ref, Ref], Key] = {}

    def resolve(key: Key) -> Ref:
        return (key, False) if key[1] < 2 else ref[key]

    def flip(half: Ref) -> Ref:
        (level, node), negated = half
        return ((level, 1 - node), False) if node < 2 else (half[0], not negated)

    for depth in range(n - 1, -1, -1):
        for place, node in enumerate(ids[depth]):
            key = (depth, node)
            if node < 2 or key in ref:
                continue
            zero = resolve((depth + 1, ids[depth + 1][2 * place]))
            one = resolve((depth + 1, ids[depth + 1][2 * place + 1]))
            if zero == one:
                ref[key] = zero
            elif (twin := made.get((depth, flip(zero), flip(one)))) is not None:
                ref[key] = (twin, True)
            else:
                ref[key] = (key, False)
                made[depth, zero, one] = key
                split[key] = (_NAMES[perm[depth]], zero, one)

    def emit(half: Ref, out: list[str]) -> None:
        """Append a half's text: the inline tree's shapes, ``!`` if flipped."""
        (key, negated), bang = half, "!" * half[1]
        if key[1] < 2:
            out.append(str(key[1]))
            return
        name, zero, one = split[key]
        low, high = zero[0][1], one[0][1]
        if low < 2 and high < 2:
            # A literal complements by its own ``!``.
            out.append(name if bool(high) != negated else f"!{name}")
        elif low < 2 or high < 2:
            constant_one = min(low, high) == 1
            lit = name if (high >= 2) != constant_one else f"!{name}"
            op = "|" if constant_one else "&"
            out.append(f"{bang}({lit} {op} ")
            emit(one if high >= 2 else zero, out)
            out.append(")")
        else:
            out.append(f"{bang}((!{name} & ")
            emit(zero, out)
            out.append(f") | ({name} & ")
            emit(one, out)
            out.append("))")

    root: list[str] = []
    emit(resolve((0, ids[0][0])), root)
    return f"{_NOT}\n({reads}) | {''.join(root)}"
