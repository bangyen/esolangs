"""Canonical live lexical environments and typed closure values for accounting."""

from collections.abc import Hashable, Mapping

from esolangs.languages.forbin.interpreter._parse import _Function
from esolangs.languages.forbin.interpreter._scope import _Closure, _Frame, _Scope
from esolangs.runtime._state import WorkspaceVariant


class _Scopes:
    """Number reachable scopes from ordered roots, independently of store ids."""

    def __init__(self, scopes: Mapping[int, _Scope], global_scope: int) -> None:
        self.scopes = scopes
        self.global_function = scopes[global_scope].fn
        self.indices: dict[int, int] = {}
        self.pending: list[int] = []
        self.reference(global_scope)

    def reference(self, scope: int) -> WorkspaceVariant:
        if scope not in self.indices:
            self.indices[scope] = len(self.pending)
            self.pending.append(scope)
        return WorkspaceVariant("reference", (self.indices[scope],))

    def function(self, fn: _Function) -> WorkspaceVariant:
        if fn is self.global_function:
            return WorkspaceVariant("global", ())
        if fn.site is None:
            raise TypeError("workspace function needs a declared source location")
        return WorkspaceVariant("function", (fn.site,))

    def value(self, value: object) -> Hashable:
        if isinstance(value, int):
            return value
        if isinstance(value, _Closure):
            return WorkspaceVariant(
                "closure", (self.function(value.fn), self.reference(value.scope))
            )
        if value in ("in", "out"):
            return WorkspaceVariant("input" if value == "in" else "output", ())
        raise TypeError("workspace values must be bits, closures or builtins")

    def frame(self, frame: _Frame) -> WorkspaceVariant:
        loop = (
            None
            if frame.for_rows is None
            else WorkspaceVariant(
                "loop",
                (
                    tuple(tuple(self.value(v) for v in row) for row in frame.for_rows),
                    frame.for_names,
                    frame.for_ind,
                    frame.for_started,
                    frame.for_body_pos if frame.for_started else 0,
                ),
            )
        )
        return WorkspaceVariant(
            "frame",
            (
                self.function(frame.fn),
                self.reference(frame.scope),
                frame.pos,
                loop,
            ),
        )

    def environments(self) -> tuple[WorkspaceVariant, ...]:
        nodes = []
        cursor = 0
        while cursor < len(self.pending):
            scope = self.scopes[self.pending[cursor]]
            parent = None if scope.parent is None else self.reference(scope.parent)
            locals_ = frozenset(
                (key, self.value(value)) for key, value in sorted(scope.locals.items())
            )
            nodes.append(
                WorkspaceVariant(
                    "environment", (self.function(scope.fn), parent, locals_)
                )
            )
            cursor += 1
        return tuple(nodes)
