"""Typed values and source-relative instructions for logical accounting."""

from __future__ import annotations

from collections.abc import Hashable
from struct import pack
from typing import TYPE_CHECKING

from esolangs.languages.algebraic_programming_language.interpreter._parse import (
    _Definition,
)
from esolangs.runtime._state import WorkspaceVariant

if TYPE_CHECKING:
    from esolangs.languages.algebraic_programming_language.interpreter import _Frame
    from esolangs.languages.algebraic_programming_language.interpreter._parse import (
        _Node,
    )


def _value(value: object) -> WorkspaceVariant:
    if isinstance(value, _Definition):
        if value.site is None:
            raise TypeError("workspace definitions require a declared source line")
        return WorkspaceVariant("function", (value.site,))
    if isinstance(value, float):
        return WorkspaceVariant("floating", (pack("!d", value),))
    if isinstance(value, int):
        return WorkspaceVariant("integer", (value,))
    raise TypeError("workspace values must be numbers or definitions")


def _children(node: _Node) -> tuple[_Node, ...]:
    if node[0] == "neg" or node[0] == "ret":
        return (node[1],)
    if node[0] == "bin":
        return node[2], node[3]
    if node[0] == "call":
        return node[2]
    return ()


def _locations(body: list[_Node]) -> dict[int, int]:
    """Index immutable code structurally; container sharing cannot change locations."""
    locations: dict[int, int] = {}
    interned: dict[tuple[Hashable, ...], int] = {}
    pending = [(node, False) for node in reversed(body)]
    while pending:
        node, ready = pending.pop()
        if id(node) in locations:
            continue
        children = _children(node)
        if not ready:
            pending.append((node, True))
            pending.extend((child, False) for child in reversed(children))
            continue
        prefix: tuple[Hashable, ...] = (node[0],)
        if node[0] == "lit":
            prefix += (
                ("floating", pack("!d", node[1]))
                if isinstance(node[1], float)
                else ("integer", node[1])
            )
        elif node[0] in ("var", "ref", "bin", "call"):
            prefix += (node[1],)
        key = (*prefix, *(locations[id(child)] for child in children))
        locations[id(node)] = interned.setdefault(key, len(interned))
    return locations


def _frame(frame: _Frame) -> WorkspaceVariant:
    if frame.fn.workspace_nodes is None:
        frame.fn.workspace_nodes = _locations(frame.fn.body)
    return WorkspaceVariant(
        "frame",
        (
            _value(frame.fn),
            frame.stmt,
            tuple(
                (
                    WorkspaceVariant(
                        "instruction", (frame.fn.workspace_nodes[id(node)],)
                    ),
                    tuple(_value(value) for value in done),
                )
                for node, done in frame.work
            ),
            _value(frame.value),
            frame.returned,
            frame.printing,
            frame.assign,
            frozenset((key, _value(value)) for key, value in frame.locals.items()),
        ),
    )
