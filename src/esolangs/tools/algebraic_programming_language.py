"""Boolean-function generator for Algebraic Programming Language."""

from itertools import pairwise

from esolangs.tools.helpers import (
    _validate_truth_table,
    best_input_order,
    subtree_ids,
)

#: Input variable names in harness order; a variable is bound by being
#: named on an executed line, so these must be codepoint-ascending
#: (the interpreter sorts by name).  The wiki allows accented Latin,
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
    size.  Width-constrained output splits the compact tree into definitions,
    since APL cannot continue an expression across lines.
    """
    if width is not None:
        return best_input_order(
            truth_table, lambda table, perm: _apl_tree_narrow(table, perm, width)
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
    digits = []
    while True:
        digits.append(chr(ord("A") + index % 26))
        index = index // 26 - 1
        if index < 0:
            return "".join(reversed(digits))


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


def _apl_tree_narrow(table: str, perm: tuple[int, ...], width: int) -> str:
    """Split a compact tree into definitions with bounded fresh text per call."""
    n = _validate_truth_table(table)
    source = _apl_tree_ordered(table, perm).removeprefix(_NOT + "\n").replace(" ", "")
    prefix, source = source.split(")|", 1)
    prefix += ")|"
    # There are fewer definitions than source characters, bounding name width.
    name_width = len(_apl_name(len(source)))
    call_width = name_width + 2
    limit = max(width, 4 * call_width + 6, 2 * n + call_width + 4)
    definitions: list[str] = []
    # A frame's pieces carry their fresh source-character count; references
    # carry zero. Every definition consumes at least one call-width of fresh
    # text, so O(T / n) names of O(n) characters keep total source O(T).
    frames: list[list[tuple[object, int, int]]] = [[]]

    def render(node: object) -> str:
        pieces: list[str] = []
        pending = [node]
        while pending:
            current = pending.pop()
            if isinstance(current, str):
                pieces.append(current)
            else:
                assert isinstance(current, tuple)
                pending.extend(reversed(current))
        return "".join(pieces)

    def define(part: tuple[object, int, int]) -> tuple[object, int, int]:
        name = _apl_name(len(definitions))
        definitions.append(f"{name}={render(part[0])}")
        call = f"{name}()"
        return call, len(call), 0

    def trim(parts: list[tuple[object, int, int]], budget: int) -> None:
        while sum(length for _, length, _ in parts) > budget:
            eligible = [
                (length, index)
                for index, (_, length, fresh) in enumerate(parts)
                if fresh >= call_width
            ]
            if not eligible:
                raise AssertionError("tree frame cannot be split")
            _, index = max(eligible)
            parts[index] = define(parts[index])

    for char in source:
        if char == "(":
            frames.append([("(", 1, 1)])
        elif char == ")":
            parts = frames.pop()
            parts.append((")", 1, 1))
            trim(parts, limit - name_width - 1)
            frames[-1].append(
                (
                    tuple(node for node, _, _ in parts),
                    sum(length for _, length, _ in parts),
                    sum(fresh for _, _, fresh in parts),
                )
            )
        else:
            frames[-1].append((char, 1, 1))
    parts = frames[0]
    if sum(length for _, length, _ in parts) + len(prefix) > limit:
        parts = [
            define(
                (
                    tuple(node for node, _, _ in parts),
                    sum(length for _, length, _ in parts),
                    sum(fresh for _, _, fresh in parts),
                )
            )
        ]
    complement = _NOT.replace(" ", "")
    return "\n".join(
        [complement, *definitions, prefix + render(tuple(node for node, _, _ in parts))]
    )
