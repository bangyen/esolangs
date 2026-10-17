"""INTERCAL Boolean program generator: a fully grouped Shannon expression.

Inputs are read into ``.1``..``.n`` by a polite ``@@`` template, tested in
input order, and the result is printed with ``READ OUT``.  Subexpressions the
expression would repeat are assigned once to spare variables and named where
they recur (:func:`_intercal_shared`).

Size:
    O(n) for structured tables, O(T) for random; n=10 parity: 1,262 chars,
    n=10 random 1847: 8,947 chars.

Decisions:
    Greedy input order costs +2.14% on three inputs and +1.68% on the
    five-input sample.  Narrower rebuilds (unsimplified, per-operation names,
    split mingles) were retired: at n=7..10 wrapping the natural program is
    smaller at every width from 1 to 259, by 26.2% (n=7) to 32.3% (n=10).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple

from esolangs.generation.helpers import (
    _validate_truth_table,
    in_input_order,
)
from esolangs.generation.wrap import _join_tokens, balance_score
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

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
        if self.op == "not":
            children, operator = (*self.children, _ONE), "?"
        else:
            children = self.children
            operator = {"and": "&", "or": "V"}[self.op]
        left, right = children
        mingled = (
            f"{inner}{operator}{left.render(depth + 2)}$"
            f"{right.render(depth + 2)}{inner}"
        )
        return f"{outer}{mingled}~#1{outer}"


_ZERO, _ONE = _Expr("constant", 0), _Expr("constant", 1)
# A statement's newline plus a fifth of the 4 characters PLEASE costs over DO.
_STATEMENT_OVERHEAD = 2


def intercal(truth_table: str, width: int | None = None) -> str:
    """Return a polite C-INTERCAL template computing ``truth_table``.

    Inputs are tested in input order.  A ``width`` breaks over-wide
    statements between tokens.
    """
    natural = in_input_order(truth_table, _intercal_shared)
    if width is None:
        return natural
    return _wrap_intercal(natural, width)


_TOKEN = re.compile(r"[A-Z]+|[.#][0-9]+|<-|@+|[0-9]+|[^\s]")


def _intercal_tokens(program: str) -> list[str]:
    """Return whole keywords, decimal operands, and expression punctuation."""
    return _TOKEN.findall(program)


def balance_intercal(_table: str, default: str) -> str:
    """Return the lowest-``balance_score`` of four wraps of ``default``.

    The longest statement dominates: with ``m`` rows besides it (half a row of
    token waste each) and ``L`` its characters, the square width solves
    ``w = 2(m + L / w)``.  Token
    quantisation puts the best width 15-30% above that root; wraps at 1.15,
    1.25, 1.3 and 1.4 times it stay within 5% of the best fit width on 360
    random tables of 2-64 rows.
    """
    lengths = sorted(map(len, default.splitlines()))
    rows = len(lengths) - 0.5
    root = rows + (rows * rows + 2 * lengths[-1]) ** 0.5
    candidates = [
        _wrap_intercal(default, max(1, round(root * scale)))
        for scale in (1.15, 1.25, 1.3, 1.4)
    ]
    return min(candidates, key=balance_score)


def _wrap_intercal(program: str, width: int) -> str:
    """Break over-wide statements only at C-INTERCAL token boundaries."""
    return "\n".join(
        line
        if len(line) <= width
        else _join_tokens(_intercal_tokens(line), width, separator=" ")
        for line in program.splitlines()
    )


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

    The Shannon tree is reduced to a diagram (:func:`_diagram`); a node read
    by two or more parents gets a spare variable, ``.k <- expr``, named
    wherever it recurs, when that is shorter.  The rule weighs the node's
    inlined text against one statement plus a name per reader, so it is local
    to the node.  A level's ``~selector`` recurs in every node of the level
    and is assigned once by the same rule.  Variables are numbered from
    ``.{n + 2}``: the complements, then the nodes bottom-up, so the short
    names go to the deep nodes, the most numerous and most often read.
    """
    n = _validate_truth_table(truth_table)
    nodes, root = _diagram(truth_table, n)
    selectors = [_Expr("input", n - 1 - perm[level]) for level in range(n)]
    negated = _negations(nodes, selectors)
    first = n + 2 + sum(name is not None for name in negated)
    readers = [0] * len(nodes)
    for _level, zero, one in _interior(nodes):
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
        # Against what each later reader saves.
        statement = len(f"DO .{name} <- ") + _STATEMENT_OVERHEAD
        count = readers[node]
        if (count - 1) * inline > statement + count * spelled:
            names[node] = name
            text[node] = spelled
        else:
            text[node] = inline

    exprs = [_ZERO, _ONE]
    for level, zero, one in _interior(nodes):
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


class _Node(NamedTuple):
    """A diagram node: a selector level and the ids of its two halves."""

    level: int
    zero: int
    one: int


def _interior(nodes: list[_Node]) -> list[_Node]:
    """Return the nodes after the two constants (ids 0 and 1)."""
    return nodes[2:]


def _diagram(truth_table: str, n: int) -> tuple[list[_Node], int]:
    """Return the table's reduced Shannon diagram and its root's id.

    Subtables are interned level by level, bottom-up, by the ids of their
    two halves: ``O(T)`` dictionary lookups and no search.  Ids 0 and 1 are
    the constants; every later id is a ``(level, zero, one)`` node, listed
    after both its halves.  A subtable whose halves are the same id is that
    id -- a constant span, or a node whose
    selector cannot change its value.
    """
    nodes = [_Node(n, 0, 0), _Node(n, 1, 1)]
    index: dict[_Node, int] = {}
    ids = [int(bit) for bit in truth_table]
    for level in range(n - 1, -1, -1):
        halves, ids = ids, []
        for at in range(0, len(halves), 2):
            key = _Node(level, halves[at], halves[at + 1])
            if key.zero == key.one:
                ids.append(key.zero)
                continue
            if key not in index:
                index[key] = len(nodes)
                nodes.append(key)
            ids.append(index[key])
    return nodes, ids[0]


def _negations(nodes: list[_Node], selectors: list[_Expr]) -> list[int | None]:
    """Name each level's ``~selector`` variable, or ``None`` to inline it.

    Numbered from the bottom level up, from the first spare ``.{n + 2}``.
    Naming beats inlining every ``~selector`` by 15.4% at n=8, 19.0% at n=10
    (random tables); always naming a used level is within 0.8% at n=8.
    """
    n = len(selectors)
    per_level = [0] * n
    for level, _zero, _one in _interior(nodes):
        per_level[level] += 1
    negated: list[int | None] = [None] * n
    name = n + 2
    for level in range(n - 1, -1, -1):
        inline = len(_Expr("not", children=(selectors[level],)).render())
        statement = len(f"DO .{name} <- ") + inline + _STATEMENT_OVERHEAD
        if per_level[level] * (inline - len(f".{name}")) > statement:
            negated[level] = name
            name += 1
    return negated


def _variable(name: int | None) -> _Expr | None:
    """Return the expression reading ``.name``, or ``None`` for no name."""
    return None if name is None else _Expr("input", name - 1)


def _program(n: int, assigned: list[tuple[int, _Expr]], result: _Expr) -> str:
    """Return the polite template: inputs, shared variables, result, output."""
    statements = [f".{n - i} <- {TEMPLATE_CHAR * 2}" for i in range(n)]
    statements += [f".{name} <- {expr.render()}" for name, expr in assigned]
    statements.append(f".{n + 1} <- {result.render()}")
    statements += [f"READ OUT .{n + 1}", "GIVE UP"]
    polite = max(1, (len(statements) + 4) // 5)  # one statement in five
    return "\n".join(
        f"{'PLEASE' if i < polite else 'DO'} {statement}"
        for i, statement in enumerate(statements)
    )


def _same_layout(template: str, _plain: str, layout: Callable[[int], Any]) -> bool:
    """Equivalent statement syntax: every layout shares the narrowest one's tokens."""
    narrow = layout(1)
    return isinstance(narrow, str) and _intercal_tokens(template) == _intercal_tokens(
        narrow
    )


LANGUAGE = Language(
    "INTERCAL",
    "intercal",
    category="variable_based",
    random=True,
    boolean=intercal,
    same_layout=_same_layout,
    contract=BooleanContract(
        answer_pattern=r"(?s)^(_\n|I)\n$",
        answer_values=("_\n", "I"),
        note="INTERCAL READ OUT prints a lone overbar for zero and I for one",
    ),
    balance=balance_intercal,
    empty_program="INTERCAL program is insufficiently or excessively polite (E099)",
    example=Example(pair=PAIR, char=TEMPLATE_CHAR, expected="_\n\n"),
)
