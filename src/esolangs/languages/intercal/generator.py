"""INTERCAL Boolean program generator: a fully grouped Shannon expression.

Inputs are read into ``.1``..``.n`` by a polite ``@@`` template in input
order. A mingle of the two children selected by ``selector$not selector``
forms each mux; constant branches fold first. Repeated masks, complements
and folded subexpressions are named where shorter, then ``READ OUT`` prints
the result (:func:`_intercal_shared`).

Size:
    O(T) for dense tables;
    n=8 constant zero: 129 chars; n=10 parity: 810 chars,
    n=10 random 1847: 3,338 chars.

Decisions:
    Inputs remain in physical order. Retired layouts are historical;
    ``balance=True`` packs short statements into shared rows
    ([ablations.balance_packed_rows]).
"""

import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from math import isqrt
from typing import Any, NamedTuple

from esolangs.generation.decision import DecisionNode as _Node
from esolangs.generation.decision import reduced_diagram
from esolangs.generation.helpers import (
    _validate_truth_table,
)
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.template import (
    InputSlot,
    TemplateLayout,
    TemplateToken,
    layout_fragments,
    layout_tokens,
)
from esolangs.generation.wrap import balance_score
from esolangs.languages.intercal import descriptor

_VARIABLE_MAX = 65535  # the largest INTERCAL variable number


@dataclass(frozen=True, slots=True)
class _Expr:
    op: str
    value: int = 0
    children: tuple["_Expr", ...] = ()
    text: str = ""

    def render(self, depth: int = 0) -> str:
        if self.op == "constant":
            return f"#{self.value}"
        if self.op == "input":
            return f".{self.value + 1}"
        if self.op == "element":
            return self.text
        outer, inner = ("'", '"') if depth % 2 == 0 else ('"', "'")
        if self.op == "mingle":
            left, right = self.children
            return f"{outer}{left.render(depth + 1)}${right.render(depth + 1)}{outer}"
        if self.op == "select":
            zero, one, mask = self.children
            return (
                f"{outer}{inner}{one.render(depth + 2)}${zero.render(depth + 2)}{inner}"
                f"~{mask.render(depth + 1)}{outer}"
            )
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


_INPUT = InputSlot(2)
type _Statement = str | tuple[str, InputSlot]


def intercal(truth_table: str, width: int | None = None) -> str:
    """Return a polite C-INTERCAL template computing ``truth_table``.

    Inputs are tested in input order.  A ``width`` breaks over-wide
    statements between tokens.
    """
    return _layout(truth_table, width).source


def _layout(truth_table: str, width: int | None) -> TemplateLayout:
    n = _validate_truth_table(truth_table)
    if truth_table.count(truth_table[0]) == len(truth_table):
        # [ablations.constant_table_audit_20261101]: all setters overwrite .1.
        natural = _polite(
            [*[(".1 <- ", _INPUT)] * n, f"READ OUT #{truth_table[0]}", "GIVE UP"]
        )
    else:
        natural = _intercal_shared(truth_table, tuple(range(n)))
    return natural if width is None else _wrap_layout(natural, width)


_TOKEN = re.compile(r"[A-Z]+|[.,;#][0-9]+|<-|@+|[0-9]+|[^\s]")


def _intercal_tokens(program: str) -> list[str]:
    """Return whole keywords, decimal operands, and expression punctuation."""
    return _TOKEN.findall(program)


def balance_intercal(default: TemplateLayout) -> TemplateLayout:
    """Return the lowest-``balance_score`` of four packed wraps of ``default``.

    Statements are token-wrapped (:func:`_wrap_layout`), then consecutive
    lines share a row up to the width: a line break is a token boundary
    and a statement starts at ``DO`` or ``PLEASE``, so short statements
    no longer cost a row each.  The square width is about 1.2-1.3 times
    ``sqrt(2 * characters)``; wraps at 1.1, 1.2, 1.3 and 1.4 times it stay within
    7% of the best width on the measured tables (see
    [ablations.balance_packed_rows]).
    """
    root = (2 * len(default.source)) ** 0.5
    candidates = []
    for scale in (1.1, 1.2, 1.3, 1.4):
        width = max(1, round(root * scale))
        wrapped = _wrap_layout(default, width)
        candidates.append(
            TemplateLayout(_pack_rows(wrapped.source, width), wrapped.spans)
        )
    return min(candidates, key=lambda candidate: balance_score(candidate.source))


def _pack_rows(program: str, width: int) -> str:
    """Join consecutive lines with a space while a row fits ``width``."""
    rows: list[str] = []
    for line in program.splitlines():
        if rows and len(rows[-1]) + 1 + len(line) <= width:
            rows[-1] += " " + line
        else:
            rows.append(line)
    return "\n".join(rows)


def _wrap_layout(program: TemplateLayout, width: int) -> TemplateLayout:
    """Break over-wide statements only at C-INTERCAL token boundaries."""

    def parts() -> Iterator[TemplateToken]:
        for i, line in enumerate(program.lines()):
            if i:
                yield "\n"
            if len(line.source) <= width:
                yield from line.fragments()
                continue
            tokens: list[TemplateToken] = []
            for part in line.fragments():
                if isinstance(part, InputSlot):
                    tokens.append(part)
                else:
                    tokens.extend(_intercal_tokens(part))
            yield from layout_tokens(
                tokens, width, char=descriptor.TEMPLATE_CHAR
            ).fragments()

    return layout_fragments(parts(), char=descriptor.TEMPLATE_CHAR)


def _mux(
    selector: _Expr,
    zero: _Expr,
    one: _Expr,
    negated: "_Expr | None" = None,
    mask: "_Expr | None" = None,
) -> _Expr:
    """Select one Boolean child, folding constants before shared-mask use."""
    if mask is not None:
        if zero == _ZERO and one == _ONE:
            return selector
        return _Expr("select", children=(zero, one, mask))
    if negated is None:
        negated = _Expr("not", children=(selector,))
    if zero == _ZERO:
        return selector if one == _ONE else _Expr("and", children=(selector, one))
    if one == _ZERO:
        return negated if zero == _ONE else _Expr("and", children=(negated, zero))
    if zero == _ONE:
        return _Expr("or", children=(negated, one))
    if one == _ONE:
        return _Expr("or", children=(selector, zero))
    mask = mask or _Expr("mingle", children=(selector, negated))
    return _Expr("select", children=(zero, one, mask))


def _intercal_shared(truth_table: str, perm: tuple[int, ...]) -> TemplateLayout:
    """Name profitable folded expressions after planning selector aliases.

    Graph readers are lower bounds on rendered uses; unnamed parents can
    duplicate their children. Both alias and node passes take O(T) work.
    """
    n = _validate_truth_table(truth_table)
    nodes, root = reduced_diagram(truth_table, n)
    selectors = [_Expr("input", n - 1 - perm[level]) for level in range(n)]
    negated, mask_names = _aliases(nodes, selectors)
    masks = [
        None if name is None else _Expr("element", text=f":{name}")
        for name in mask_names
    ]
    first = n + 2 + sum(name is not None for name in negated)
    readers = [0] * len(nodes)
    for _level, zero, one in _interior(nodes):
        readers[zero] += 1
        readers[one] += 1

    text = [2, 2] + [0] * (len(nodes) - 2)
    names: dict[int, int] = {}
    for node in range(2, len(nodes)):
        level, zero, one = nodes[node]
        inline = _mux_chars(
            nodes[node], selectors[level], _variable(negated[level]), masks[level], text
        )
        name = first + len(names)
        spelled = len(f".{name}")
        statement = len(f"DO .{name} <- ") + _STATEMENT_OVERHEAD
        count = readers[node]
        if (count - 1) * inline > statement + count * spelled:
            names[node] = name
            text[node] = spelled
        else:
            text[node] = inline

    top = first + len(names) - 1
    width = _spill(top)
    complements = [_variable(name) for name in negated]
    exprs = [_ZERO, _ONE]
    for level, zero, one in _interior(nodes):
        low = _reference(names.get(zero), width) or exprs[zero]
        high = _reference(names.get(one), width) or exprs[one]
        exprs.append(
            _mux(selectors[level], low, high, complements[level], masks[level])
        )
    assigned: list[tuple[int | str, _Expr]] = [
        (name, _Expr("not", children=(selector,)))
        for selector, name in zip(selectors, negated, strict=True)
        if name is not None
    ]
    assigned.sort(key=lambda pair: pair[0])
    assigned += [
        (
            f":{name}",
            _Expr(
                "mingle",
                children=(
                    selectors[level],
                    complements[level] or _Expr("not", children=(selectors[level],)),
                ),
            ),
        )
        for level, name in enumerate(mask_names)
        if name is not None
    ]
    assigned += [(names[node], exprs[node]) for node in names]
    return _program(n, assigned, exprs[root], width)


def _interior(nodes: Sequence[_Node]) -> Sequence[_Node]:
    """Return the nodes after the two constants (ids 0 and 1)."""
    return nodes[2:]


def _mux_chars(
    node: _Node,
    selector: _Expr,
    complement: _Expr | None,
    mask: _Expr | None,
    text: list[int],
) -> int:
    """Price a folded mux without re-rendering either child's subtree."""
    _, zero, one = node
    selected = len(selector.render())
    if mask is not None:
        if zero == 0 and one == 1:
            return selected
        return 6 + len(mask.render()) + text[zero] + text[one]
    negated = len(complement.render()) if complement is not None else 11 + selected
    if zero == 0:
        return selected if one == 1 else 9 + selected + text[one]
    if one == 0:
        return negated if zero == 1 else 9 + negated + text[zero]
    if zero == 1:
        return 9 + negated + text[one]
    if one == 1:
        return 9 + selected + text[zero]
    frame = 9 + selected + negated
    return frame + text[zero] + text[one]


class _Usage(NamedTuple):
    """Fold categories whose local frames respond differently to aliasing."""

    positive: int = 0
    negative: int = 0
    complement: int = 0
    full: int = 0


class _AliasCost(NamedTuple):
    """One level's local prices; no graph state survives the alias choice."""

    uses: _Usage
    selector: int
    negated: int
    raw: int
    mask: int

    def __call__(self, mode: tuple[bool, bool]) -> tuple[int, int]:
        neg, named = mode
        positive, negative, complement, full = self.uses
        if named:
            definition = (
                7 + _STATEMENT_OVERHEAD + self.mask + 3 + self.selector + self.raw
            )
            total = definition + (positive + negative) * (8 + self.mask)
            total += complement * (10 + self.mask) + full * (6 + self.mask)
        else:
            child = self.negated if neg else self.raw
            total = (7 + _STATEMENT_OVERHEAD + self.negated + self.raw) if neg else 0
            total += positive * (9 + self.selector) + negative * (9 + child)
            total += complement * child + full * (9 + self.selector + child)
        return total, int(neg) + int(named)


def _aliases(
    nodes: Sequence[_Node], selectors: list[_Expr]
) -> tuple[list[int | None], list[int | None]]:
    """Price inline, negation-only or mask-only local spellings.

    A named mask also shortens constant folds except a bare selector, so its
    complement is used only once and cannot justify a separate alias.
    """
    n = len(selectors)
    uses = [_Usage() for _ in range(n)]
    for level, zero, one in _interior(nodes):
        current = uses[level]
        if zero == 0 and one == 1:
            continue
        if zero == 1 and one == 0:
            current = current._replace(complement=current.complement + 1)
        elif zero == 0 or one == 1:
            current = current._replace(positive=current.positive + 1)
        elif one == 0 or zero == 1:
            current = current._replace(negative=current.negative + 1)
        else:
            current = current._replace(full=current.full + 1)
        uses[level] = current
    negated: list[int | None] = [None] * n
    masks: list[int | None] = [None] * n
    count = 0
    for level in range(n - 1, -1, -1):
        selector = selectors[level]
        raw = len(_Expr("not", children=(selector,)).render())
        scalar = n + 2 + count
        mask = selector.value + 1
        prices = _AliasCost(
            uses[level], len(selector.render()), len(f".{scalar}"), raw, len(f":{mask}")
        )
        neg, named = min(
            ((False, False), (True, False), (False, True)), key=prices.__call__
        )
        if neg:
            negated[level] = scalar
            count += 1
        if named:
            masks[level] = mask
    return negated, masks


def _variable(name: int | None) -> _Expr | None:
    """Return the expression reading ``.name``, or ``None`` for no name."""
    return None if name is None else _Expr("input", name - 1)


def _spill(top: int) -> int:
    """Return the array width for names up to ``top``; 0 when all fit as variables.

    ``S = top - 65535`` names spill; ``ceil(sqrt(S))`` per array keeps one
    element write at O(sqrt(S)), the interpreter copying the array and the
    array map per write.
    """
    spilled = top - _VARIABLE_MAX
    return isqrt(spilled - 1) + 1 if spilled > 0 else 0


def _target(name: int | str, width: int) -> str:
    """Spell a scalar/shared array target, or preserve a colon-mask target."""
    if isinstance(name, str):
        return name
    if name <= _VARIABLE_MAX:
        return f".{name}"
    index = name - _VARIABLE_MAX - 1
    return f",{index // width + 1} SUB #{index % width + 1}"


def _reference(name: int | None, width: int) -> _Expr | None:
    """Return the expression reading shared ``name``, or ``None`` for no name."""
    if name is None or name <= _VARIABLE_MAX:
        return _variable(name)
    return _Expr("element", text=_target(name, width))


def _program(
    n: int, assigned: list[tuple[int | str, _Expr]], result: _Expr, width: int = 0
) -> TemplateLayout:
    """Return the polite template: inputs, arrays, shared names, result, output."""
    statements: list[_Statement] = [(f".{n - i} <- ", _INPUT) for i in range(n)]
    if width:
        last = max(name for name, _ in assigned if isinstance(name, int))
        arrays = (last - _VARIABLE_MAX - 1) // width + 1
        statements += [f",{j} <- #{width}" for j in range(1, arrays + 1)]
    statements += [
        f"{_target(name, width)} <- {expr.render()}" for name, expr in assigned
    ]
    statements.append(f".{n + 1} <- {result.render()}")
    statements += [f"READ OUT .{n + 1}", "GIVE UP"]
    return _polite(statements)


def _polite(statements: list[_Statement]) -> TemplateLayout:
    """Mark one statement in five PLEASE, rounding up."""
    polite = max(1, (len(statements) + 4) // 5)

    def parts() -> Iterator[TemplateToken]:
        for i, statement in enumerate(statements):
            if i:
                yield "\n"
            yield "PLEASE " if i < polite else "DO "
            if isinstance(statement, str):
                yield statement
            else:
                yield from statement

    return layout_fragments(parts(), char=descriptor.TEMPLATE_CHAR)


def _same_layout(template: str, _plain: str, layout: Callable[[int], Any]) -> bool:
    """Equivalent statement syntax: every layout shares the narrowest one's tokens."""
    narrow = layout(1)
    return isinstance(narrow, str) and _intercal_tokens(template) == _intercal_tokens(
        narrow
    )


def intercal_request(request: GenerationRequest) -> TemplateLayout:
    """Emit source through the declared generation request interface."""
    return _layout(request.table, request.width)


def intercal_balance_request(request: BalanceRequest) -> TemplateLayout:
    """Pack rows and preserve the ordered input slots."""
    if not isinstance(request.source, TemplateLayout):
        raise TypeError("balancing needs a rendered template with slots")
    return balance_intercal(request.source)
