"""Scopes, frames and the evaluation context of the Forbin interpreter."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import NamedTuple

from esolangs.exceptions import HaltError
from esolangs.languages.forbin.interpreter._parse import (
    _Function,
)


class _NeedByte(Exception):  # noqa: N818 - an internal resumption signal
    """Signals that a statement needs one more input byte than supplied.

    Raised by the pure reader when ``in`` finds the explicit input tuple
    exhausted.  ``effects`` is the output already computed before the read,
    so the shell can flush it before reading.  The shell reads one more byte
    and calls :func:`_advance` again; the transition is deterministic, so the
    retry reaches the same point with the new value.
    """

    def __init__(self, effects: tuple[str, ...] = ()) -> None:
        super().__init__()
        self.effects = effects


def _frozen(locals_: Mapping[str, object]) -> Mapping[str, object]:
    """Return ``locals_`` as an immutable mapping, sharing an existing freeze."""
    return (
        locals_ if isinstance(locals_, MappingProxyType) else MappingProxyType(locals_)
    )


@dataclass(frozen=True)
class _Scope:
    """One lexical scope: its function, its locals, and its parent's id."""

    fn: _Function
    locals: Mapping[str, object]
    parent: int | None


@dataclass(frozen=True)
class _Frame:
    """One function invocation: its function, scope, and cursors.

    ``pos`` is the statement cursor into ``fn.body``; ``for_rows`` and its
    companions track a ``for`` loop in progress at that cursor, one row
    resumed per step, and ``for_body_pos`` is the cursor into the *current*
    row's body -- a nested resumable sequence sharing this frame's scope, not
    a pushed frame, since loop-variable and outer-variable writes land in
    the same scope.  The body is read from ``fn.body[pos]``, not stored.
    """

    fn: _Function
    scope: int
    pos: int = 0
    for_rows: tuple[tuple[object, ...], ...] | None = None
    for_names: tuple[str, ...] = ()
    for_ind: int = 0
    for_started: bool = False
    for_body_pos: int = 0


@dataclass(frozen=True)
class _Closure:
    """A function value: its definition and the scope it was written in."""

    fn: _Function
    scope: int

    def __repr__(self) -> str:
        """Name the function and its scope id."""
        return f"<{self.fn.name or 'literal'}@{self.scope}>"


class _Ctx(NamedTuple):
    """The threaded state of one pure transition attempt.

    ``out`` is the effect accumulator of the single attempt: it is owned by
    :func:`_advance`, never part of the run state, and its contents are
    returned as an immutable tuple.
    """

    scopes: Mapping[int, _Scope]
    bits: tuple[int, ...]
    reads: int
    input_pos: int
    out: list[str]
    inputs: tuple[int, ...]


@dataclass(frozen=True)
class _State:
    """Every changing value in a Forbin run."""

    frames: tuple[_Frame, ...]
    scopes: Mapping[int, _Scope]
    bits: tuple[int, ...]
    reads: int


def _new_scope(
    scopes: Mapping[int, _Scope],
    fn: _Function,
    parent: int | None,
    locals_: Mapping[str, object],
) -> tuple[int, Mapping[int, _Scope]]:
    """Add a scope node; return its id and the new store.

    Scopes are only ever added, so the next id is the store's size.
    """
    scope = len(scopes)
    node = _Scope(fn, _frozen(locals_), parent)
    return scope, MappingProxyType({**scopes, scope: node})


def _lookup(
    frame: _Frame,
    name: str,
    globals_: Mapping[str, _Function],
    scopes: Mapping[int, _Scope],
) -> object:
    """Resolve a variable, builtin, or function name from ``frame`` outward.

    The chain is lexical: a scope's ``parent`` is the scope its function
    was defined in, so a top-level function sees globals, not its caller.
    """
    scope: int | None = frame.scope
    root = frame.scope
    while scope is not None:
        node = scopes[scope]
        if name in node.locals:
            return node.locals[name]
        if name in node.fn.nested:
            return _Closure(node.fn.nested[name], scope)
        root = scope
        scope = node.parent
    if name in ("in", "out"):
        return name
    if name in globals_:
        return _Closure(globals_[name], root)
    raise HaltError(
        f"undeclared identifier {name!r}",
        hint="declare the identifier before using it; check its spelling",
    )


def _bind(
    frame: _Frame, name: str, value: object, scopes: Mapping[int, _Scope]
) -> Mapping[int, _Scope]:
    """Return the store with ``name`` assigned where it lives.

    The wiki makes ``{code} 0;`` the same as ``code``, so a write inside a
    literal (or a nested function) reaches the enclosing variable.
    """
    scope: int | None = frame.scope
    while scope is not None:
        node = scopes[scope]
        if name in node.locals:
            updated = replace(node, locals=_frozen({**node.locals, name: value}))
            return MappingProxyType({**scopes, scope: updated})
        scope = node.parent
    node = scopes[frame.scope]
    updated = replace(node, locals=_frozen({**node.locals, name: value}))
    return MappingProxyType({**scopes, frame.scope: updated})


def _read_bit(ctx: _Ctx) -> tuple[int, _Ctx]:
    """Return the next input bit, most significant first, and the new context.

    Refills from the next explicit input byte when the buffer empties;
    running out raises :data:`_NeedByte`.
    """
    bits = ctx.bits
    if not bits:
        if ctx.input_pos >= len(ctx.inputs):
            raise _NeedByte
        byte = ctx.inputs[ctx.input_pos]
        bits = tuple((byte >> k) & 1 for k in range(7, -1, -1))
        ctx = ctx._replace(input_pos=ctx.input_pos + 1)
    return bits[0], ctx._replace(bits=bits[1:], reads=ctx.reads + 1)


def _bound(value: object, which: str) -> int:
    """Return a ``for`` range bound, halting if it is not a number.

    ``_eval`` yields any Forbin value, so a bound can be a function; the
    language gives no meaning to counting from one, and comparing it would
    otherwise raise Python's own TypeError instead of halting.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise HaltError(
            f"for {which} bound must be a number, got {value!r}",
            hint="use numeric values for both loop bounds",
        )
    return value


def _enter(
    callee: _Closure,
    args: list[object],
    scopes: Mapping[int, _Scope],
) -> tuple[_Frame, Mapping[int, _Scope]]:
    """Return a frame for calling ``callee``; unpassed parameters are 0."""
    locals_: dict[str, object] = dict.fromkeys(callee.fn.args, 0)
    for name, value in zip(callee.fn.args, args, strict=False):
        locals_[name] = value
    scope, scopes = _new_scope(scopes, callee.fn, callee.scope, locals_)
    return _Frame(callee.fn, scope), scopes
