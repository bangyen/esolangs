"""Boolean-function generator for Algebraic Programming Language."""

from itertools import pairwise
from string import ascii_uppercase

from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
    in_input_order,
    short_name,
    subtree_ids,
)

#: Input variable names in harness order; a variable is bound by being
#: named on an executed line, so these must be codepoint-ascending
#: (the input prefix names variables in this order).  The wiki allows accented
#: Latin, Cyrillic and Greek; accented Latin is appended (past any reachable
#: arity), Cyrillic and Greek left out as confusable (RUF001).
_NAMES = "abcdefghijklmnopqrstuvwxyzàáâãäåæçèéêëìíîïñòóôõöøùúûüý"

#: The complement operator, spelled exactly as the wiki spells it.
_NOT = "!x = {\nx & $0\n$1\n}"
_NOT_TIGHT = _NOT.replace(" ", "")


def _reads(n: int, sep: str) -> str:
    """Join the input names ``a``.. in order, then ``0``."""
    return sep.join([*_NAMES[:n], "0"])


def _span(program: str) -> int:
    return max(map(len, program.splitlines()))


def algebraic_programming_language(truth_table: str, width: int | None = None) -> str:
    """Build an APL program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  A
    variable is read from stdin by appearing on an executed line, and the
    line's result is printed.  A folded decision tree selects subtrees with
    ``!x`` and ``x``; the harness feeds 0 or 1, so every value stays 0 or 1.
    A zero-valued prefix names every input first, preserving binding under
    folds; O(T) size.  With ``width``, the tree splits into definitions,
    since APL cannot continue an expression across lines.
    """
    if width is not None:
        return in_input_order(
            truth_table, lambda table, perm: _apl_narrow_layout(table, perm, width)[0]
        )
    return in_input_order(truth_table, _apl_reduced_ordered)


def _apl_tree_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order as a folded, linear-size Boolean tree.

    The pieces go into one flat list, joined once, so the build is O(T)
    rather than a copy of every subtree per level.
    """
    n = _validate_truth_table(truth_table)
    changes = [0]
    for previous, current in pairwise(truth_table):
        changes.append(changes[-1] + (previous != current))
    reads = _reads(n, " & ")
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


_Key = tuple[int, int]
#: A half as a node reached through it and whether it arrives complemented.
_Ref = tuple[_Key, bool]


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
    reads = _reads(n, " & ")
    # A node's (test, zero half, one half); ``ref`` sends every subtable to
    # the node that spells it, and ``made`` finds a node by its halves.
    split: dict[_Key, tuple[str, _Ref, _Ref]] = {}
    ref: dict[_Key, _Ref] = {}
    made: dict[tuple[int, _Ref, _Ref], _Key] = {}

    def resolve(key: _Key) -> _Ref:
        return (key, False) if key[1] < 2 else ref[key]

    def flip(half: _Ref) -> _Ref:
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

    def emit(half: _Ref, out: list[str]) -> None:
        """Append a half's text: the inline tree's shapes, ``!`` if flipped."""
        (key, negated) = half
        bang = "!" * negated
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


type _Rope = str | tuple[_Rope, ...]


def _join(parts: list[tuple[_Rope, int, int]]) -> tuple[_Rope, int, int]:
    """Fold frame pieces into one (nodes, length, fresh) piece."""
    return (
        tuple(node for node, _, _ in parts),
        sum(length for _, length, _ in parts),
        sum(fresh for _, _, fresh in parts),
    )


def _apl_tree_layout(
    table: str, perm: tuple[int, ...], width: int
) -> tuple[str, int | None]:
    """Return the split tree and its next frame-budget transition."""
    n = _validate_truth_table(table)
    source = _apl_tree_ordered(table, perm).removeprefix(_NOT + "\n").replace(" ", "")
    prefix, source = source.split(")|", 1)
    prefix += ")|"
    # There are fewer definitions than source characters, bounding name width.
    name_width = len(short_name(len(source), ascii_uppercase))
    call_width = name_width + 2
    limit = max(width, 4 * call_width + 6, 2 * n + call_width + 4)
    definitions: list[str] = []
    events: set[int] = set()
    # A frame's pieces carry their fresh source-character count; references
    # carry zero. Every definition consumes at least one call-width of fresh
    # text, so O(T / n) names of O(n) characters keep total source O(T).
    frames: list[list[tuple[_Rope, int, int]]] = [[]]

    def render(node: _Rope) -> str:
        pieces: list[str] = []
        pending = [node]
        while pending:
            current = pending.pop()
            if isinstance(current, str):
                pieces.append(current)
            else:
                pending.extend(reversed(current))
        return "".join(pieces)

    def define(part: tuple[_Rope, int, int]) -> tuple[_Rope, int, int]:
        name = short_name(len(definitions), ascii_uppercase)
        definitions.append(f"{name}={render(part[0])}")
        call = f"{name}()"
        return call, len(call), 0

    def trim(parts: list[tuple[_Rope, int, int]], budget: int) -> None:
        while (span := sum(length for _, length, _ in parts)) > budget:
            events.add(span + name_width + 1)
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
            frames[-1].append(_join(parts))
        else:
            frames[-1].append((char, 1, 1))
    parts = frames[0]
    span = sum(length for _, length, _ in parts) + len(prefix)
    if span > limit:
        events.add(span)
        parts = [define(_join(parts))]
    program = "\n".join(
        [_NOT_TIGHT, *definitions, prefix + render(tuple(node for node, _, _ in parts))]
    )
    return program, min(events, default=None)


def _apl_narrow_layout(
    table: str, perm: tuple[int, ...], width: int
) -> tuple[str, int | None]:
    """Return the chosen spelling and its next frame or format fit."""
    previous, next_width = _apl_tree_layout(table, perm, width)
    n = _validate_truth_table(table)
    if n > 3 or _span(previous) <= width:
        return previous, next_width
    events = [_span(previous)]
    if next_width is not None:
        events.append(next_width)
    # At most nine primitive definitions use one-character names below n=4.
    # Larger trees retain fresh-text splitting, avoiding O(T log T) names.
    constant = constant_span_test(table)
    definitions: list[str] = []

    def combine(left: str, operator: str, right: str) -> str:
        name = short_name(len(definitions), ascii_uppercase)
        definitions.append(f"{name}={left}{operator}{right}")
        return f"{name}()"

    def tree(start: int, end: int, depth: int) -> str:
        if constant(start, end):
            return table[start]
        half = (start + end) // 2
        selector = _NAMES[perm[depth]]
        zero, one = tree(start, half, depth + 1), tree(half, end, depth + 1)
        if (zero, one) == ("0", "1"):
            return selector
        if (zero, one) == ("1", "0"):
            return f"!{selector}"
        if zero == "0":
            return combine(selector, "&", one)
        if one == "0":
            return combine(f"!{selector}", "&", zero)
        if zero == "1":
            return combine(f"!{selector}", "|", one)
        if one == "1":
            return combine(selector, "|", zero)
        low = combine(f"!{selector}", "&", zero)
        high = combine(selector, "&", one)
        return combine(low, "|", high)

    result = tree(0, len(table), 0)
    # '&' binds before '|'; the zero prefix pre-binds every input without
    # parentheses, preserving input order even when a Boolean arm folds.
    reads = _reads(n, "&")
    candidate = "\n".join([_NOT_TIGHT, *definitions, f"{reads}|{result}"])
    chosen = min((previous, candidate), key=_span)
    span = _span(chosen)
    if span <= width:
        return chosen, min(events)
    events.append(span)
    operators = _apl_short_operators(table, perm)
    if width < 5 and table == "0110":
        events.append(5)
        # a+b-2ab: the executed sum binds both globals before the unary calls.
        operators = "!x={\nx*b\n}\n?x={\nx*2\n}\n~x={\na-x\n}\n^x={\n~?!x\n}\n^a+b"
    program = min((chosen, operators), key=_span)
    return program, min(events)


def _apl_short_operators(table: str, perm: tuple[int, ...]) -> str:
    """Return five-column operator definitions for at most three inputs."""
    constant = constant_span_test(table)
    symbols = iter("!?:;~^@")
    lines: list[str] = []

    def tree(start: int, end: int, depth: int) -> str:
        if constant(start, end):
            return table[start]
        half = (start + end) // 2
        zero = tree(start, half, depth + 1)
        one = tree(half, end, depth + 1)
        symbol = next(symbols)
        lines.extend([f"{symbol}x={{", f"x&${one}", f"${zero}", "}"])
        return symbol + _NAMES[perm[depth]]

    root = tree(0, len(table), 0)
    # The executed binding call names all inputs before any operator runs.
    # Its intermediate values are unused, so chaining binds three inputs.
    if len(perm) == 1:
        lines.extend(["]x={", f"${root}", "}", "]a"])
    else:
        lines.extend(["x`y={", f"${root}", "}", "`".join(_NAMES[: len(perm)])])
    return "\n".join(lines)


def balance_apl(table: str, default: str) -> str:
    """Compare reachable frame-budget and short-definition fit transitions.

    Input order stays the identity (a greedy order saves 4.8% at n=8, under
    the 10% bar).
    """
    regimes = [(table, tuple(range(len(table).bit_length() - 1)))]
    candidates = [default]
    width: int | None = 1
    while width is not None:
        layouts = [
            _apl_narrow_layout(ordered, perm, width) for ordered, perm in regimes
        ]
        candidates.append(min((program for program, _ in layouts), key=len))
        width = min((point for _, point in layouts if point is not None), default=None)
    from esolangs.tools.wrap import balance_score

    return min(candidates, key=balance_score)
