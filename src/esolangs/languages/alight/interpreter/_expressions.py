"""Reduce and evaluate Alight expressions in a live call frame."""

from typing import TYPE_CHECKING, assert_never

from esolangs.exceptions import HaltError
from esolangs.languages.alight.interpreter._hints import Hint
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
from esolangs.languages.alight.interpreter._rewrite import _replace
from esolangs.languages.alight.interpreter._values import (
    _BUILTINS,
    _arith,
    _boolean,
    _builtin,
    _compare,
    _InPlace,
    _list_value,
    _logic,
    _truth,
)
from esolangs.languages.alight.interpreter._walker import _Walker

if TYPE_CHECKING:
    from esolangs.languages.alight.interpreter._machine import _Core


class _Expressions:
    """Alight expression evaluation, against the innermost walk's namespace.

    ``reduce`` resolves the calls in an expression left to right, stopping
    at the first user-defined call -- builtins run immediately, replaced by
    their values so a re-entered command never runs one twice.
    ``evaluate`` computes the value of a fully reduced expression.
    ``rebind`` carries an in-place ``at`` through every alias of the list.
    """

    def __init__(self, core: "_Core") -> None:
        self._core = core

    def reduce(self, expr: _Expr) -> tuple[_Expr, str | None]:
        """Resolve calls left to right, stopping at the first user one.

        Returns the rewritten expression and the name of the user call to
        push, or None when nothing is left to run.  Every call passed --
        **builtins included** -- is replaced by its value, so a builtin runs
        once even when a command resumes after a user call.

        Resolved operands and operators are retained too: ``1/0+at{l,.5,66}``
        must fail before the setter changes ``l``.
        """
        if isinstance(expr, (_Num, _Val, _SpecialNode)):
            return expr, None
        if isinstance(expr, _Var):
            return _Val("val", self.evaluate(expr)), None
        if isinstance(expr, _Not):
            inner, pending = self.reduce(expr.operand)
            node: _Expr = _Not("not", inner)
            if pending is not None:
                return node, pending
            return _Val("val", self.evaluate(node)), None
        if isinstance(expr, _Bin):
            left, pending = self.reduce(expr.left)
            if pending is not None:
                return _Bin("bin", expr.op, left, expr.right), pending
            right, pending = self.reduce(expr.right)
            node = _Bin("bin", expr.op, left, right)
            if pending is not None:
                return node, pending
            return _Val("val", self.evaluate(node)), None
        if isinstance(expr, _List):
            items, pending = self._reduce_all(expr.items)
            if pending is not None:
                return _List("list", items), pending
            return _Val("val", self.evaluate(_List("list", items))), None
        if isinstance(expr, _Call):
            args, pending = self._reduce_all(expr.args)
            if pending is not None:
                return _Call("call", expr.name, args), pending
            if expr.name not in _BUILTINS:
                return _Call("call", expr.name, args), expr.name
            # A builtin with every argument resolved: run it now and keep the
            # value, so a re-entry never runs it again.
            values = [self.evaluate(a) for a in args]
            result = _builtin(expr.name, values, self._core.list_update)
            if isinstance(result, _InPlace):
                self.rebind(result.old, result.updated)
                result = result.updated
            return _Val("val", result), None
        assert_never(expr)

    def _reduce_all(self, exprs: list[_Expr]) -> tuple[list[_Expr], str | None]:
        """Reduce ``exprs`` in order, stopping at the first pending call."""
        done: list[_Expr] = []
        for i, item in enumerate(exprs):
            reduced, pending = self.reduce(item)
            done.append(reduced)
            if pending is not None:
                return [*done, *exprs[i + 1 :]], pending
        return done, None

    def evaluate(self, expr: _Expr) -> _Value:
        """Evaluate a parsed expression in this frame's namespace.

        Nodes are typed, so each tag dispatches to typed fields.  They are
        built by the parser, by ``_Expressions.reduce`` (folds resolved calls
        into values, rebuilds nodes with reduced children), and by
        ``_parse._replace_first`` (rebuilds the path to a replaced call).  A
        node is an immutable tuple, so a snapshot can carry one.
        """
        if isinstance(expr, _Num):
            return expr.value
        if isinstance(expr, _Val):
            # A call ``reduce`` already ran, carrying its value so that a
            # re-entry of this command does not run it a second time.
            return expr.value
        if isinstance(expr, _SpecialNode):
            return expr.name
        if isinstance(expr, _Var):
            if expr.name not in self._core.vars:
                raise Hint.VARIABLE_REFERENCE.halt(f"no such variable: {expr.name!r}")
            return self._core.vars[expr.name]
        if isinstance(expr, _List):
            return _list_value([self.evaluate(e) for e in expr.items])
        if isinstance(expr, _Not):
            return _boolean(not _truth(self.evaluate(expr.operand)))
        if isinstance(expr, _Bin):
            left = self.evaluate(expr.left)
            right = self.evaluate(expr.right)
            if expr.op in "=<>":
                return _compare(expr.op, left, right)
            if expr.op in "&|^":
                return _logic(expr.op, left, right)
            return _arith(expr.op, left, right)
        if isinstance(expr, _Call):
            # ``reduce`` replaces every call before evaluation.
            raise HaltError("unresolved expression")  # pragma: no cover
        assert_never(expr)

    def evaluate_rest(self) -> _Value:
        """Evaluate the expression already validated and reduced by step."""
        pending = self._core.walker.pending
        if pending is None:  # pragma: no cover - resolve() sets pending first
            raise HaltError("no pending expression")
        return self.evaluate(pending)

    def rebind(self, old: list[_Value], updated: list[_Value]) -> None:
        """Replace ``old`` by ``updated`` in every value the run can reach.

        The language's in-place ``at`` is a shared-reference update: after
        ``set m l; at{l,.5,66}`` both names see the new list.  A pure run
        cannot edit the list, so it rebuilds every variable, pending
        expression and returned value that referenced ``old`` -- preserving
        the sharing among them -- and swaps in fresh walker copies for those
        that changed.  This is why lists are shared rather than copied
        everywhere else: the one operation that changes one pays for it.
        """
        memo: dict[int, object] = {}
        walkers: list[_Walker] = []
        for walker in self._core.walkers:
            variables = _replace(walker.vars, old, updated, memo)
            pending = _replace(walker.pending, old, updated, memo)
            returned = _replace(walker.returned, old, updated, memo)
            if (
                variables is walker.vars
                and pending is walker.pending
                and returned is walker.returned
            ):
                walkers.append(walker)
                continue
            copy = _Walker(walker.row, walker.col, walker.heading, variables)
            copy.pending = pending
            copy.returned = returned
            walkers.append(copy)
        self._core.walkers = walkers
