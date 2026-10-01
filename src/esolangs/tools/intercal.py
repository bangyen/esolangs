"""INTERCAL boolean generator: a fully grouped Shannon expression.

Subexpressions the expression would repeat are assigned once to spare
variables and named where they recur (:func:`_intercal_shared`).
"""

import re
from dataclasses import dataclass

from esolangs.tools.helpers import (
    _validate_truth_table,
    in_input_order,
)

TEMPLATE_CHAR = "@"
PAIR = ("#0", "#1")


@dataclass(frozen=True)
class _Expr:
    op: str
    value: int = 0
    children: tuple["_Expr", ...] = ()

    def render(self, depth: int = 0) -> str:
        if self.op == "constant":
            return f"#{self.value}"
        if self.op == "input":
            return f".{self.value + 1}"
        outer, inner = ("'", '"') if depth % 2 == 0 else ('"', "'")
        if self.op == "mingle":
            left, right = self.children
            return f"{outer}{'&V?'[self.value]}{left.render()}${right.render()}{outer}"
        if self.op == "select":
            return f"{outer}{self.children[0].render()}~#2{outer}"
        if self.op == "not":
            children, operator = (*self.children, _Expr("constant", 1)), "?"
        else:
            children = self.children
            operator = {"and": "&", "or": "V", "xor": "?"}[self.op]
        left, right = children
        mingled = (
            f"{inner}{operator}{left.render(depth + 2)}$"
            f"{right.render(depth + 2)}{inner}"
        )
        return f"{outer}{mingled}~#2{outer}"


def intercal(truth_table: str, width: int | None = None) -> str:
    """Return a polite C-INTERCAL template computing ``truth_table``.

    Every input is assigned to its own variable before the expression, so
    shared Shannon diagram tests them in input order. Retiring the greedy
    order adds 2.14% to the three-input total and 1.68% to the five-input
    sample.  Over-wide
    expressions name each Boolean operation; narrower layouts break between tokens.
    """
    natural = in_input_order(truth_table, _intercal_shared)
    if width is None or width <= 0 or max(map(len, natural.splitlines())) <= width:
        return natural
    previous = _intercal_narrow(truth_table, simplify=False)
    if max(map(len, previous.splitlines())) <= width:
        return previous
    narrow = _intercal_narrow(truth_table)
    if max(map(len, narrow.splitlines())) <= width:
        return narrow
    split = _intercal_narrow(truth_table, split=True)
    best = min((narrow, split), key=lambda program: max(map(len, program.splitlines())))
    chosen = (
        best
        if max(map(len, best.splitlines())) < max(map(len, natural.splitlines()))
        else natural
    )
    return _wrap_intercal(chosen, width)


_TOKEN = re.compile(r"[A-Z]+|[.#][0-9]+|<-|@+|[0-9]+|[^\s]")


def _intercal_tokens(program: str) -> list[str]:
    """Return whole keywords, decimal operands, and expression punctuation."""
    return _TOKEN.findall(program)


def _wrap_intercal(program: str, width: int) -> str:
    """Break over-wide statements only at C-INTERCAL token boundaries."""
    from esolangs.tools.wrap import _join_tokens

    return "\n".join(
        line
        if len(line) <= width
        else _join_tokens(_intercal_tokens(line), width, separator=" ")
        for line in program.splitlines()
    )


def _intercal_narrow(
    truth_table: str, *, simplify: bool = True, split: bool = False
) -> str:
    """Name each primitive operation in the reduced Shannon diagram.

    At most O(T/log T) diagram nodes need O(log T)-digit names: O(T) source.
    Constant arms simplify Boolean operations; complementary arms use XOR.
    Each assignment has only one mingle/unary/select frame.
    """
    n = _validate_truth_table(truth_table)
    nodes, root = _diagram(truth_table, n)
    assigned: list[tuple[int, _Expr]] = []

    def name(expr: _Expr) -> _Expr:
        if split:
            children = expr.children
            operator = "xor" if expr.op == "not" else expr.op
            if expr.op == "not":
                children = (*children, _ONE)
            intermediate = n + 2 + len(assigned)
            assigned.append(
                (
                    intermediate,
                    _Expr("mingle", ("and", "or", "xor").index(operator), children),
                )
            )
            # Boolean operands give a result at most 7, which fits a onespot;
            # the following selection extracts its answer from bit1.
            expr = _Expr("select", children=(_Expr("input", intermediate - 1),))
        variable = n + 2 + len(assigned)
        assigned.append((variable, expr))
        return _Expr("input", variable - 1)

    selectors = [_Expr("input", n - 1 - level) for level in range(n)]
    if not simplify:
        inverses = [name(_Expr("not", children=(selector,))) for selector in selectors]
        previous = [_ZERO, _ONE]
        for level, zero, one in nodes[2:]:
            low = name(_Expr("and", children=(inverses[level], previous[zero])))
            high = name(_Expr("and", children=(selectors[level], previous[one])))
            previous.append(name(_Expr("or", children=(low, high))))
        return _program(n, assigned, previous[root])
    negated: dict[int, _Expr] = {}
    results = [_ZERO, _ONE]
    complements = {0: 1, 1: 0}
    seen: dict[tuple[int, int, int], int] = {}
    for node, (level, zero, one) in enumerate(nodes[2:], 2):
        mirror = (level, complements.get(zero, -1), complements.get(one, -1))
        if mirror in seen:
            other = seen[mirror]
            complements[node], complements[other] = other, node
        seen[level, zero, one] = node
        selector = selectors[level]
        if (zero, one) == (0, 1):
            result = selector
        elif complements.get(zero) == one:
            result = name(_Expr("xor", children=(selector, results[zero])))
        else:
            if level not in negated:
                negated[level] = name(_Expr("not", children=(selector,)))
            if zero == 0:
                result = name(_Expr("and", children=(selector, results[one])))
            elif one == 0:
                result = name(_Expr("and", children=(negated[level], results[zero])))
            elif zero == 1:
                result = name(_Expr("or", children=(negated[level], results[one])))
            elif one == 1:
                result = name(_Expr("or", children=(selector, results[zero])))
            else:
                low = name(_Expr("and", children=(negated[level], results[zero])))
                high = name(_Expr("and", children=(selector, results[one])))
                result = name(_Expr("or", children=(low, high)))
        results.append(result)
    return _program(n, assigned, results[root])


def _mux(
    selector: _Expr, zero: _Expr, one: _Expr, negated: "_Expr | None" = None
) -> _Expr:
    """Return ``(~selector & zero) V (selector & one)``.

    ``negated`` names a variable already holding ``~selector``.
    """
    if negated is None:
        negated = _Expr("not", children=(selector,))
    left = _Expr("and", children=(negated, zero))
    return _Expr("or", children=(left, _Expr("and", children=(selector, one))))


def _intercal_shared(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one order's template with repeated subexpressions assigned once.

    The Shannon tree is reduced to a diagram (:func:`_diagram`), and a node
    read by two or more parents is given a spare variable, ``.k <- expr``,
    and named by it wherever it recurs, when that is shorter: the rule
    weighs the node's inlined text against one statement and a name per
    reader, so it is local to the node.  A level's ``~selector`` recurs in
    every node of the level and is assigned once by the same rule.
    Variables are numbered from ``.{n + 2}``: the complements, then the
    nodes bottom-up, so the short names go to the deep nodes, which are
    the most numerous and the most often read.
    """
    n = _validate_truth_table(truth_table)
    nodes, root = _diagram(truth_table, n)
    selectors = [_Expr("input", n - 1 - perm[level]) for level in range(n)]
    negated = _negations(nodes, selectors)
    first = n + 2 + sum(name is not None for name in negated)
    readers = [0] * len(nodes)
    for _level, zero, one in nodes[2:]:
        readers[zero] += 1
        readers[one] += 1

    # A node's inlined length is its level's frame -- the mux over two
    # ``#0`` leaves, less the leaves -- plus its halves' text.
    frames = [
        len(_mux(selector, _ZERO, _ZERO, _variable(name)).render()) - 4
        for selector, name in zip(selectors, negated, strict=True)
    ]
    text = [2, 2] + [0] * (len(nodes) - 2)
    names: dict[int, int] = {}
    for node in range(2, len(nodes)):
        level, zero, one = nodes[node]
        inline = frames[level] + text[zero] + text[one]
        name = first + len(names)
        spelled = len(f".{name}")
        # ``DO .k <- `` and a newline, plus a fifth of the four characters a
        # ``PLEASE`` costs over ``DO``, against what each later reader saves.
        statement = len(f"DO .{name} <- ") + 2
        count = readers[node]
        if (count - 1) * inline > statement + count * spelled:
            names[node] = name
            text[node] = spelled
        else:
            text[node] = inline

    exprs = [_ZERO, _ONE]
    for level, zero, one in nodes[2:]:
        low = _variable(names.get(zero)) or exprs[zero]
        high = _variable(names.get(one)) or exprs[one]
        exprs.append(_mux(selectors[level], low, high, _variable(negated[level])))
    assigned = [
        (name, _Expr("not", children=(selector,)))
        for selector, name in zip(selectors, negated, strict=True)
        if name is not None
    ]
    assigned.sort(key=lambda pair: pair[0])
    assigned += [(names[node], exprs[node]) for node in names]
    return _program(n, assigned, exprs[root])


def _diagram(truth_table: str, n: int) -> tuple[list[tuple[int, int, int]], int]:
    """Return the table's reduced Shannon diagram and its root's id.

    Subtables are interned level by level, bottom-up, by the ids of their
    two halves: ``O(T)`` dictionary lookups and no search.  Ids 0 and 1 are
    the constants; every later id is a ``(level, zero, one)`` node, listed
    after both its halves.  A subtable whose halves are the same id is that
    id -- a constant span, or a node whose
    selector cannot change its value.
    """
    nodes: list[tuple[int, int, int]] = [(n, 0, 0), (n, 1, 1)]
    index: dict[tuple[int, int, int], int] = {}
    ids = [int(bit) for bit in truth_table]
    for level in range(n - 1, -1, -1):
        halves, ids = ids, []
        for at in range(0, len(halves), 2):
            key = (level, halves[at], halves[at + 1])
            if key[1] == key[2]:
                ids.append(key[1])
                continue
            ids.append(index.setdefault(key, len(nodes)))
            if ids[-1] == len(nodes):
                nodes.append(key)
    return nodes, ids[0]


def _negations(
    nodes: list[tuple[int, int, int]], selectors: list[_Expr]
) -> list[int | None]:
    """Name each level's ``~selector`` variable, or ``None`` to inline it.

    Numbered from the bottom level up, from the first spare ``.{n + 2}``.
    """
    n = len(selectors)
    per_level = [0] * n
    for level, _zero, _one in nodes[2:]:
        per_level[level] += 1
    negated: list[int | None] = [None] * n
    name = n + 2
    for level in range(n - 1, -1, -1):
        inline = len(_Expr("not", children=(selectors[level],)).render())
        statement = len(f"DO .{name} <- ") + inline + 2
        if per_level[level] * (inline - len(f".{name}")) > statement:
            negated[level] = name
            name += 1
    return negated


_ZERO, _ONE = _Expr("constant", 0), _Expr("constant", 1)


def _variable(name: int | None) -> _Expr | None:
    """Return the expression reading ``.name``, or ``None`` for no name."""
    return None if name is None else _Expr("input", name - 1)


def _program(n: int, assigned: list[tuple[int, _Expr]], result: _Expr) -> str:
    """Return the polite template: inputs, shared variables, result, output."""
    statements = [f".{n - i} <- {TEMPLATE_CHAR * 2}" for i in range(n)]
    statements += [f".{name} <- {expr.render()}" for name, expr in assigned]
    statements += [f".{n + 1} <- {result.render()}"]
    statements += [f"READ OUT .{n + 1}", "GIVE UP"]
    polite = max(1, (len(statements) + 4) // 5)
    return "\n".join(
        f"{'PLEASE' if i < polite else 'DO'} {statement}"
        for i, statement in enumerate(statements)
    )
