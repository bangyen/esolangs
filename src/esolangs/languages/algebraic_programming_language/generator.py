"""Algebraic Programming Language Boolean program generator: a reduced ``!x`` diagram.

A zero-valued reads prefix names every input in order, since a variable is
bound by appearing on an executed line; the rest is a reduced decision
diagram selecting subtrees with ``x`` and ``!x``, so every value stays 0 or
1.  Default compares inline text, repeated expressions and bounded shared
frames; with ``width`` the tree splits into definitions, since APL cannot
continue an expression across lines.

Size:
    O(T) chars.  n=10 parity: 254 chars, n=10 and: 120 chars, n=10 random
    1847: 3,047 chars.

Decisions:
    A greedy input order saves 4.8% at n=8, under the 10% bar, so the order
    stays the identity.  The inline tree stays a candidate beside the
    reduced diagram since ``!`` sharing grew XOR-like n=3 tables by 1-3
    characters.
"""

from collections.abc import Callable
from string import ascii_uppercase

from esolangs.generation.helpers import (
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    grid_width,
    in_input_order,
    read_at,
    short_name,
    subtree_ids,
)
from esolangs.generation.wrap import balance_score
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

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


def algebraic_programming_language(truth_table: str, width: int | None = None) -> str:
    """Return an APL program for ``truth_table`` (``2**n`` bits, MSB first).

    ``width`` splits the tree into definitions; the harness feeds 0 or 1.
    """
    if width is not None:
        return in_input_order(
            truth_table, lambda table, perm: _apl_narrow_layout(table, perm, width)[0]
        )
    return in_input_order(truth_table, _apl_shared_ordered)


def _apl_shared_ordered(table: str, perm: tuple[int, ...]) -> str:
    """Compare inline text, repeated expressions and bounded shared frames."""
    plain = _apl_reduced_ordered(table, perm)
    shared, _ = _apl_split(table, perm, 40, _apl_reduced_ordered, require_share=True)
    return min(plain, shared, _apl_repeated_expressions(plain), key=len)


def _render_dag(
    nodes: list[tuple[str | int, ...]], names: dict[int, str], index: int
) -> str:
    """Render one expression-DAG node, emitting calls for named shared nodes.

    ``nodes`` is the deduplicated DAG built by
    :func:`_apl_repeated_expressions`; ``names`` maps node indexes to their
    definition names.
    """
    out: list[str] = []
    pending = list(reversed(nodes[index]))
    while pending:
        part = pending.pop()
        if isinstance(part, str):
            out.append(part)
        elif part in names:
            out.append(f"{names[part]}()")
        else:
            pending.extend(reversed(nodes[part]))
    return "".join(out)


def _split_reads(program: str) -> tuple[str, str]:
    """Return a tree program's spaceless reads prefix, through ``)|``, and rest."""
    source = program.removeprefix(_NOT + "\n").replace(" ", "")
    prefix, rest = source.split(")|", 1)
    return prefix + ")|", rest


def _apl_repeated_expressions(program: str) -> str:
    """Name profitable repeated groups, with one linear scan of the expression DAG."""
    prefix, source = _split_reads(program)
    nodes: list[tuple[str | int, ...]] = []
    sizes: list[int] = []
    made: dict[tuple[str | int, ...], int] = {}
    frames: list[list[str | int]] = [[]]
    for char in source:
        if char == "(":
            frames.append([char])
        elif char == ")":
            parts = (*frames.pop(), char)
            if parts not in made:
                made[parts] = len(nodes)
                nodes.append(parts)
                sizes.append(sum(sizes[p] if isinstance(p, int) else 1 for p in parts))
            frames[-1].append(made[parts])
        else:
            frames[-1].append(char)
    nodes.append(tuple(frames[0]))
    # Equal-width names make every substitution's cost exact before rendering.
    # Start at the first bijective-base name of that width, avoiding padding aliases.
    capacity, offset = 26, 0
    while capacity < len(nodes):
        offset += capacity
        capacity *= 26
    name_width = len(short_name(offset, ascii_uppercase))
    call_width = name_width + 2
    copies = [0] * len(nodes)
    copies[-1] = 1
    names: dict[int, str] = {}
    for index in range(len(nodes) - 1, -1, -1):
        count = copies[index]
        if index < len(sizes) and (count - 1) * sizes[index] > (
            count * call_width + name_width + 2
        ):
            names[index] = short_name(offset + len(names), ascii_uppercase)
            count = 1
        # A definition writes its body once. An inline group keeps every copy.
        # Descendants have not been named yet, so each accepted gain is exact.
        for part in nodes[index]:
            if isinstance(part, int):
                copies[part] += count
    if not names:
        return program

    definitions = [
        f"{names[index]}={_render_dag(nodes, names, index)}"
        for index in range(len(nodes))
        if index in names
    ]
    return "\n".join(
        [_NOT_TIGHT, *definitions, prefix + _render_dag(nodes, names, len(nodes) - 1)]
    )


def _apl_tree_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order as a folded, linear-size Boolean tree.

    The pieces go into one flat list, joined once, so the build is O(T)
    rather than a copy of every subtree per level.
    """
    n = _validate_truth_table(truth_table)
    is_constant = constant_span_test(truth_table)
    reads = _reads(n, " & ")
    pieces = [f"{_NOT}\n({reads}) | "]

    def constant(start: int, end: int) -> str | None:
        return truth_table[start] if is_constant(start, end) else None

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
    :func:`~esolangs.generation.helpers.subtree_ids`, a dict lookup a node, and
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
    """Return the shorter split tree and its next frame-budget transition.

    The reduced diagram drops ignored inputs and repeated halves; the inline
    tree stays a candidate since ``!`` sharing grew XOR-like n=3 tables by
    1-3 characters.
    """
    laid = [
        _apl_split(table, perm, width, build)
        for build in (_apl_reduced_ordered, _apl_tree_ordered)
    ]
    shared = _apl_repeated_expressions(_apl_reduced_ordered(table, perm))
    span = grid_width(shared)
    laid.append((shared, span if span > width else None))
    events = [point for _, point in laid if point is not None]
    best = min(
        (program for program, _ in laid),
        key=lambda x: (max(grid_width(x), width), len(x)),
    )
    return best, min(events, default=None)


class _Splitter:
    """Split one Boolean tree's source into definitions under a width limit.

    Holds the layout state: the frame stack,
    the emitted definitions, the interned bodies, whether any body was
    shared, and the width-transition events.
    """

    def __init__(
        self,
        table: str,
        perm: tuple[int, ...],
        width: int,
        build: Callable[[str, tuple[int, ...]], str],
    ) -> None:
        self._n = _validate_truth_table(table)
        self._prefix, self._source = _split_reads(build(table, perm))
        # There are fewer definitions than source characters, bounding name width.
        self._name_width = len(short_name(len(self._source), ascii_uppercase))
        self._call_width = self._name_width + 2
        self._limit = max(
            width, 4 * self._call_width + 6, 2 * self._n + self._call_width + 4
        )
        self._definitions: list[str] = []
        self._made: dict[str, str] = {}
        self._reused = False
        self._events: set[int] = set()
        # A frame's pieces carry their fresh source-character count;
        # references carry zero. Every definition consumes at least one
        # call-width of fresh text, so O(T / n) names of O(n) characters
        # keep total source O(T).
        self._frames: list[list[tuple[_Rope, int, int]]] = [[]]

    @property
    def reused(self) -> bool:
        """Whether any emitted body was shared by more than one caller."""
        return self._reused

    def render(self, node: _Rope) -> str:
        """Flatten a rope of nested tuples into its source text."""
        pieces: list[str] = []
        pending = [node]
        while pending:
            current = pending.pop()
            if isinstance(current, str):
                pieces.append(current)
            else:
                pending.extend(reversed(current))
        return "".join(pieces)

    def define(self, part: tuple[_Rope, int, int]) -> tuple[_Rope, int, int]:
        """Name a frame piece, returning its call site: zero fresh text."""
        body = self.render(part[0])
        if body in self._made:
            self._reused = True
            call = self._made[body]
        else:
            name = short_name(len(self._definitions), ascii_uppercase)
            self._definitions.append(f"{name}={body}")
            call = self._made[body] = f"{name}()"
        return call, len(call), 0

    def trim(self, parts: list[tuple[_Rope, int, int]], budget: int) -> None:
        """Define the largest fresh pieces until the frame fits the budget."""
        while (span := sum(length for _, length, _ in parts)) > budget:
            self._events.add(span + self._name_width + 1)
            eligible = [
                (length, index)
                for index, (_, length, fresh) in enumerate(parts)
                if fresh >= self._call_width
            ]
            if not eligible:
                raise AssertionError("tree frame cannot be split")
            _, index = max(eligible)
            parts[index] = self.define(parts[index])

    def split(self) -> tuple[str, set[int]]:
        """Run the layout, returning the program and width-transition events."""
        for char in self._source:
            if char == "(":
                self._frames.append([("(", 1, 1)])
            elif char == ")":
                parts = self._frames.pop()
                parts.append((")", 1, 1))
                self.trim(parts, self._limit - self._name_width - 1)
                self._frames[-1].append(_join(parts))
            else:
                self._frames[-1].append((char, 1, 1))
        parts = self._frames[0]
        span = sum(length for _, length, _ in parts) + len(self._prefix)
        if span > self._limit:
            self._events.add(span)
            parts = [self.define(_join(parts))]
        tail = self._prefix + self.render(tuple(node for node, _, _ in parts))
        program = "\n".join([_NOT_TIGHT, *self._definitions, tail])
        return program, self._events


def _apl_split(
    table: str,
    perm: tuple[int, ...],
    width: int,
    build: Callable[[str, tuple[int, ...]], str],
    *,
    require_share: bool = False,
) -> tuple[str, int | None]:
    """Split ``build``'s tree into definitions under the frame budget."""
    splitter = _Splitter(table, perm, width, build)
    program, events = splitter.split()
    if require_share and not splitter.reused:
        return build(table, perm), None
    return program, min(events, default=None)


#: Operator definitions computing XOR in five columns.  The generic
#: :func:`_apl_short_operators` spelling needs six columns for the XOR table
#: ``0110``.  This hand-rolled alternative spells XOR as ``a+b-2ab``: the
#: executed sum binds both globals before the unary calls, so every line
#: fits in five columns.
_XOR_OPERATORS = "!x={\nx*b\n}\n?x={\nx*2\n}\n~x={\na-x\n}\n^x={\n~?!x\n}\n^a+b"


def _apl_narrow_layout(
    table: str, perm: tuple[int, ...], width: int
) -> tuple[str, int | None]:
    """Return the chosen spelling and its next frame or format fit."""
    previous, next_width = _apl_tree_layout(table, perm, width)
    n = _validate_truth_table(table)
    if n > 3 or grid_width(previous) <= width:
        return previous, next_width
    events = [grid_width(previous)]
    if next_width is not None:
        events.append(next_width)
    # At most nine primitive definitions use one-character names below n=4.
    # Larger trees retain fresh-text splitting, avoiding O(T log T) names.
    reduced, selectors = _essential(table, perm)
    constant = constant_span_test(reduced)
    definitions: list[str] = []
    made: dict[str, str] = {}

    def combine(left: str, operator: str, right: str) -> str:
        body = f"{left}{operator}{right}"
        if body not in made:
            name = short_name(len(definitions), ascii_uppercase)
            definitions.append(f"{name}={body}")
            made[body] = f"{name}()"
        return made[body]

    def tree(start: int, end: int, depth: int) -> str:
        if constant(start, end):
            return reduced[start]
        half = (start + end) // 2
        selector = selectors[depth]
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

    result = tree(0, len(reduced), 0)
    # '&' binds before '|'; the zero prefix pre-binds every input without
    # parentheses, preserving input order even when a Boolean arm folds.
    reads = _reads(n, "&")
    candidate = "\n".join([_NOT_TIGHT, *definitions, f"{reads}|{result}"])
    chosen = min((previous, candidate), key=grid_width)
    span = grid_width(chosen)
    if span <= width:
        return chosen, min(events)
    events.append(span)
    operators = _apl_short_operators(table, perm)
    if width < 5 and table == "0110":
        events.append(5)
        # XOR's generic operator spelling cannot fit in five columns; the
        # hand-rolled a+b-2ab spelling can (see _XOR_OPERATORS).
        operators = _XOR_OPERATORS
    program = min((chosen, operators), key=grid_width)
    return program, min(events)


def _essential(table: str, perm: tuple[int, ...]) -> tuple[str, list[str]]:
    """Return the table over its essential inputs and their selector names.

    An ignored input is still named by the binding line, so it needs no test.
    """
    n = len(perm)
    used = essential_inputs(table, n)
    if not used:
        return table, [_NAMES[i] for i in perm]
    return read_at(table, used, n), [_NAMES[perm[i]] for i in used]


def _apl_short_operators(table: str, perm: tuple[int, ...]) -> str:
    """Return five-column operator definitions for at most three inputs."""
    inputs = len(perm)
    table, selectors = _essential(table, perm)
    constant = constant_span_test(table)
    symbols = iter("!?:;~^@")
    lines: list[str] = []
    made: dict[tuple[str, str], str] = {}

    def tree(start: int, end: int, depth: int) -> str:
        if constant(start, end):
            return table[start]
        half = (start + end) // 2
        zero = tree(start, half, depth + 1)
        one = tree(half, end, depth + 1)
        if (one, zero) not in made:
            symbol = next(symbols)
            lines.extend([f"{symbol}x={{", f"x&${one}", f"${zero}", "}"])
            made[one, zero] = symbol
        return made[one, zero] + selectors[depth]

    root = tree(0, len(table), 0)
    # The executed binding call names all inputs before any operator runs.
    # Its intermediate values are unused, so chaining binds three inputs.
    if inputs == 1:
        lines.extend(["]x={", f"${root}", "}", "]a"])
    else:
        lines.extend(["x`y={", f"${root}", "}", "`".join(_NAMES[:inputs])])
    return "\n".join(lines)


def balance_apl(table: str, default: str) -> str:
    """Compare reachable frame-budget and short-definition fit transitions."""
    perm = tuple(range(len(table).bit_length() - 1))
    candidates = [default]
    width: int | None = 1
    while width is not None:
        program, width = _apl_narrow_layout(table, perm, width)
        candidates.append(program)
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Algebraic Programming Language",
    "algebraic_programming_language",
    category="variable_based",
    boolean=algebraic_programming_language,
    contract=BooleanContract(
        note="an executed line prints its result, so the answer ends in a newline",
    ),
    balance=balance_apl,
    no_wrap="a line with '=' defines, one without runs",
    # An executed line prints its result and nothing else, so the
    # answer arrives with the newline that ends that line.
    example=Example(expected="0\n"),
)
