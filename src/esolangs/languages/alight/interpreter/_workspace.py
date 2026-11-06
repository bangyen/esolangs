"""Canonical live-list graphs and typed suspended expressions for accounting."""

from __future__ import annotations

from collections.abc import Hashable
from fractions import Fraction
from typing import TYPE_CHECKING, assert_never

from esolangs.languages.alight.interpreter._parse import (
    _Bin,
    _Call,
    _Expr,
    _List,
    _Not,
    _Num,
    _SpecialNode,
    _Val,
    _Value,
    _Var,
)
from esolangs.runtime._state import WorkspaceVariant

if TYPE_CHECKING:
    from esolangs.languages.alight.interpreter._machine import _Walker


class _Graph:
    """Number reachable mutable lists by ordered roots, independent of allocation."""

    def __init__(self) -> None:
        self.indices: dict[int, int] = {}
        self.pending: list[list[_Value]] = []

    def value(self, value: _Value) -> Hashable:
        if isinstance(value, list):
            identity = id(value)
            if identity not in self.indices:
                self.indices[identity] = len(self.pending)
                self.pending.append(value)
            return WorkspaceVariant("reference", (self.indices[identity],))
        if isinstance(value, str):
            return WorkspaceVariant(value, ())
        number = Fraction(value)
        return WorkspaceVariant("number", (number.numerator, number.denominator))

    def expression(self, expr: _Expr | None) -> Hashable:
        """Freeze syntax by value; only runtime lists acquire graph references."""
        if expr is None:
            return None
        frozen: dict[int, Hashable] = {}
        pending = [(expr, False)]
        while pending:
            node, ready = pending.pop()
            if id(node) in frozen:
                continue
            if isinstance(node, _Num | _Val):
                frozen[id(node)] = WorkspaceVariant(node.tag, (self.value(node.value),))
                continue
            if isinstance(node, _SpecialNode):
                frozen[id(node)] = WorkspaceVariant("special", (self.value(node.name),))
                continue
            if isinstance(node, _Var):
                frozen[id(node)] = WorkspaceVariant("var", (node.name,))
                continue
            prefix: tuple[Hashable, ...] = ()
            if isinstance(node, _List):
                children = tuple(node.items)
            elif isinstance(node, _Call):
                prefix = (node.name,)
                children = tuple(node.args)
            elif isinstance(node, _Not):
                children = (node.operand,)
            elif isinstance(node, _Bin):
                prefix = (node.op,)
                children = (node.left, node.right)
            else:
                assert_never(node)
            if ready:
                frozen[id(node)] = WorkspaceVariant(
                    node.tag, (*prefix, *(frozen[id(child)] for child in children))
                )
            else:
                pending.append((node, True))
                pending.extend((child, False) for child in reversed(children))
        return frozen[id(expr)]

    def walker(self, walker: _Walker) -> WorkspaceVariant:
        return WorkspaceVariant(
            "walker",
            (
                walker.row,
                walker.col,
                walker.heading,
                frozenset(
                    (key, self.value(value))
                    for key, value in sorted(walker.vars.items())
                ),
                self.expression(walker.pending),
                None if walker.returned is None else self.value(walker.returned),
            ),
        )

    def heap(self) -> tuple[tuple[Hashable, ...], ...]:
        nodes = []
        cursor = 0
        while cursor < len(self.pending):
            nodes.append(tuple(self.value(value) for value in self.pending[cursor]))
            cursor += 1
        return tuple(nodes)
