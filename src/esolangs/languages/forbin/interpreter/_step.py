"""The step core and expression evaluation of the Forbin interpreter."""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from dataclasses import replace
from itertools import product
from typing import Literal

from esolangs.exceptions import HaltError
from esolangs.languages.forbin.interpreter._parse import (
    _ForSpec,
    _Function,
    _Statement,
    _ValueNode,
)
from esolangs.languages.forbin.interpreter._scope import (
    _bind,
    _bound,
    _Closure,
    _Ctx,
    _enter,
    _Frame,
    _lookup,
    _NeedByte,
    _read_bit,
    _State,
)
from esolangs.runtime._fault import _Fault


def _eval(
    node: _ValueNode,
    frame: _Frame,
    globals_: Mapping[str, _Function],
    ctx: _Ctx,
) -> tuple[object, _Ctx]:
    """Return a value expression's result and the threaded context."""
    if node[0] == "lit":
        return node[1], ctx
    if node[0] == "not":
        value, ctx = _eval(node[1], frame, globals_, ctx)
        if value in (0, 1):
            return 1 - value, ctx
        raise HaltError("! needs a bit", hint="use 0 or 1 as the operand")
    if node[0] == "var":
        return _lookup(frame, node[1], globals_, ctx.scopes), ctx
    if node[0] == "fnlit":
        return _Closure(node[1], frame.scope), ctx
    callee, ctx = _eval(node[1], frame, globals_, ctx)
    args: list[object] = []
    for argument in node[2]:
        value, ctx = _eval(argument, frame, globals_, ctx)
        args.append(value)
    return _call(callee, args, globals_, ctx)


def _call(
    callee: object,
    args: list[object],
    globals_: Mapping[str, _Function],
    ctx: _Ctx,
) -> tuple[object, _Ctx]:
    """Apply a callable, threading the context through any nested run."""
    if isinstance(callee, _Closure):
        frame, scopes = _enter(callee, args, ctx.scopes)
        ctx = ctx._replace(scopes=scopes)
        result, ctx = _run(frame, globals_, ctx)
        return (result if result is not None else 0), ctx
    if isinstance(callee, str):
        if callee == "in":
            return _read_bit(ctx)
        # A name only evaluates to a string for the two builtins -- see the
        # ``("in", "out")`` test in ``_lookup`` -- so the remaining one is
        # ``out`` and needs no test of its own.
        if len(args) != 8:
            raise HaltError(
                "out needs exactly 8 bit arguments",
                hint="give out eight arguments, each equal to 0 or 1",
            )
        byte = 0
        for bit in args:
            # Same rule as ``!`` above: a bit is 0 or 1, and anything
            # else has no byte to contribute.
            if bit == 0:
                byte *= 2
            elif bit == 1:
                byte = byte * 2 + 1
            else:
                raise HaltError(
                    "out needs bit arguments", hint="give out arguments equal to 0 or 1"
                )
        ctx.out.append(chr(byte))
        return 0, ctx
    raise HaltError(
        "called value is not a function",
        hint="call a function value rather than a scalar or list",
    )


#: Marks "no frame returned a value" from the step core.  A fresh object
#: is never a Forbin value, so ``is``/``is not`` comparisons are exact.
_NO_RETURN = object()


def _run(
    frame: _Frame,
    globals_: Mapping[str, _Function],
    ctx: _Ctx,
) -> tuple[object | None, _Ctx]:
    """Run ``frame``'s body to completion through the step core.

    Only reached for expression-position calls (``x = f(y)``), whose
    recursion depth is bounded by Python's default recursion limit; a
    statement-position call (``f(y);``) pushes onto the explicit frame
    stack, so it is not depth-limited.  Past the host's recursion limit a
    runaway raises :class:`RecursionError`, which the ``step()`` shell
    reports as a halt.
    """
    frames: tuple[_Frame, ...] = (frame,)
    result: object | None = None
    while frames:
        if len(frames) > sys.getrecursionlimit():
            raise RecursionError(
                "statement-position calls nested past the host's depth limit"
            )
        frames, ctx, returned = _step_frames(frames, globals_, ctx)
        if returned is not _NO_RETURN and not frames:
            # Only the outermost frame's own return value is this run's
            # result.  A return from an inner frame (e.g. a nested
            # statement-position call evaluated through the step core)
            # just pops that frame; recording it would leak the inner
            # value to the enclosing expression-position call.
            result = returned
    return result, ctx


def _run_block(
    stmts: list[_Statement],
    frame: _Frame,
    globals_: Mapping[str, _Function],
    ctx: _Ctx,
) -> tuple[object | None, _Ctx]:
    """Run ``stmts`` to completion in ``frame``'s scope; the return value or None.

    Drives the step core on a synthetic frame sharing ``frame``'s scope,
    so direct execution and the resumable machine share one statement
    implementation.
    """
    block_fn = _Function("$block", [])
    block_fn.body = stmts
    block_frame = _Frame(block_fn, frame.scope)
    return _run(block_frame, globals_, ctx)


def _advance_pos(frame: _Frame) -> _Frame:
    """Return ``frame`` with its statement cursor moved past one statement."""
    return replace(frame, pos=frame.pos + 1)


def _advance_body_pos(frame: _Frame) -> _Frame:
    """Return ``frame`` with its for-body cursor moved past one statement."""
    return replace(frame, for_body_pos=frame.for_body_pos + 1)


def _step_stmt(
    stmt: _Statement,
    frame: _Frame,
    frames: tuple[_Frame, ...],
    advance: Callable[[_Frame], _Frame],
    globals_: Mapping[str, _Function],
    ctx: _Ctx,
) -> tuple[tuple[_Frame, ...], _Ctx, object]:
    """Execute one statement as a single step of the core.

    ``advance`` moves the cursor the statement was read from -- the
    statement cursor, or the for-body cursor while stepping a loop body.
    Returns the new frame stack, the context, and the statement's return
    value, or :data:`_NO_RETURN` when the statement did not return.  A
    ``for`` nested in a loop body runs atomically, since the frame's
    ``for_*`` fields already track the outer loop.
    """
    if stmt[0] == "for":
        rows, names, ctx = _for_rows(stmt[1], frame, globals_, ctx)
        returned: object = _NO_RETURN
        for row in rows:
            for name, value in zip(names, row, strict=False):
                if name != "_":
                    ctx = ctx._replace(scopes=_bind(frame, name, value, ctx.scopes))
            got, ctx = _run_block(stmt[2], frame, globals_, ctx)
            if got is not None:
                returned = got
                break
        if returned is not _NO_RETURN:
            return frames[:-1], ctx, returned
        return (*frames[:-1], advance(frame)), ctx, _NO_RETURN
    pushed, ctx = _start_statement_call(stmt, frame, globals_, ctx)
    if isinstance(pushed, _Frame):
        return (*frames[:-1], advance(frame), pushed), ctx, _NO_RETURN
    if pushed is False:
        return (*frames[:-1], advance(frame)), ctx, _NO_RETURN
    if stmt[0] == "return":
        value, ctx = _eval(stmt[1], frame, globals_, ctx)
        return frames[:-1], ctx, value
    if stmt[0] != "assign":
        raise AssertionError(f"unexpected statement kind: {stmt[0]}")
    targets, rhs = stmt[1], stmt[2]
    bindings: list[tuple[str, object]] = []
    # One right-hand side is evaluated afresh for every target.
    nodes = rhs * len(targets) if len(rhs) == 1 else rhs
    for name, node in zip(targets, nodes, strict=False):
        if name != "_":
            value, ctx = _eval(node, frame, globals_, ctx)
            bindings.append((name, value))
    for name, value in bindings:
        ctx = ctx._replace(scopes=_bind(frame, name, value, ctx.scopes))
    return (*frames[:-1], advance(frame)), ctx, _NO_RETURN


def _for_rows(
    spec: _ForSpec,
    frame: _Frame,
    globals_: Mapping[str, _Function],
    ctx: _Ctx,
) -> tuple[list[list[object]], list[str], _Ctx]:
    """Compute a ``for`` statement's iteration rows and bound variable names."""
    if spec[0] == "range":
        _, name, start_node, end_node = spec
        start, ctx = _eval(start_node, frame, globals_, ctx)
        end, ctx = _eval(end_node, frame, globals_, ctx)
        lo, hi = _bound(start, "start"), _bound(end, "end")
        range_rows: list[list[object]] = (
            [[v] for v in range(lo, hi + 1)] if lo <= hi else []
        )
        return range_rows, [name], ctx
    _, names, patterns = spec
    rows: list[list[object]] = []
    for pat in patterns:
        items = pat[1] if pat[0] == "group" else [pat]
        wilds = sum(p[0] == "*" for p in items)
        # No wildcard is one empty combination: one row of values.
        for combo in product((0, 1), repeat=wilds):
            row: list[object] = []
            w = 0
            for p in items:
                if p[0] == "*":
                    row.append(combo[w])
                    w += 1
                else:
                    value, ctx = _eval(p[1], frame, globals_, ctx)
                    row.append(value)
            rows.append(row)
    return rows, names, ctx


def _start_statement_call(
    stmt: _Statement,
    frame: _Frame,
    globals_: Mapping[str, _Function],
    ctx: _Ctx,
) -> tuple[_Frame | Literal[False] | None, _Ctx]:
    """Return a pushed frame, False for a completed call, or None for a noncall."""
    if stmt[0] != "call":
        return None, ctx
    callee, ctx = _eval(stmt[1], frame, globals_, ctx)
    args: list[object] = []
    for argument in stmt[2]:
        value, ctx = _eval(argument, frame, globals_, ctx)
        args.append(value)
    if not isinstance(callee, _Closure):
        _value, ctx = _call(callee, args, globals_, ctx)
        return False, ctx
    pushed, scopes = _enter(callee, args, ctx.scopes)
    ctx = ctx._replace(scopes=scopes)
    return pushed, ctx


# The semantics are a pure transition.  :func:`_advance` maps an immutable
# ``_State`` -- the explicit frame stack, the lexical scope store, the input
# bit buffer and the explicit input bytes a statement may read -- to a new
# state and the bytes it asks to print.  ``step`` is the shell: it reads the
# bytes the transition asks for and writes what it returns.  A statement can
# read any number of bits (a call may read in a loop), so the reads cannot be
# hoisted; each :data:`_NeedByte` reads one more byte and retries the
# deterministic transition.
def _advance(
    state: _State,
    globals_: Mapping[str, _Function],
    inputs: tuple[int, ...] = (),
) -> tuple[_State, tuple[str, ...]]:
    """Return the state after one statement, row, or call, and output bytes.

    Pure: ``globals_`` and ``inputs`` are parameters, and ``out``'s write
    leaves as the returned effects instead of reaching a port.  A read that
    runs out raises :data:`_NeedByte` with the output prefix computed before
    it; any other fault raises :data:`_Fault` with the same prefix, so the
    shell can flush output before reading or re-raising.
    """
    out: list[str] = []
    ctx = _Ctx(state.scopes, state.bits, state.reads, 0, out, inputs)
    try:
        frames, ctx, _returned = _step_frames(state.frames, globals_, ctx)
    except _NeedByte:
        raise _NeedByte(tuple(out)) from None
    except _Fault:
        raise
    except BaseException as exc:
        raise _Fault(tuple(out), exc) from None
    return _State(frames, ctx.scopes, ctx.bits, ctx.reads), tuple(out)


def _step_frames(
    frames: tuple[_Frame, ...],
    globals_: Mapping[str, _Function],
    ctx: _Ctx,
) -> tuple[tuple[_Frame, ...], _Ctx, object]:
    """Advance one statement, row, or call: the single stepping core.

    Returns the new frame stack, the context, and the value of a frame
    that returned on this step, or :data:`_NO_RETURN` when none did.
    Output accumulates in ``ctx.out``; a read that runs out raises
    :data:`_NeedByte`.
    """
    frame = frames[-1]
    if frame.for_rows is not None:
        return _step_for_frames(frames, frame, globals_, ctx)
    if frame.pos >= len(frame.fn.body):
        return frames[:-1], ctx, _NO_RETURN
    stmt = frame.fn.body[frame.pos]
    if stmt[0] == "for":
        rows, names, ctx = _for_rows(stmt[1], frame, globals_, ctx)
        frame = replace(
            frame,
            for_rows=tuple(tuple(row) for row in rows),
            for_names=tuple(names),
            for_ind=0,
            for_started=False,
        )
        return (*frames[:-1], frame), ctx, _NO_RETURN
    return _step_stmt(stmt, frame, frames, _advance_pos, globals_, ctx)


def _step_for_frames(
    frames: tuple[_Frame, ...],
    frame: _Frame,
    globals_: Mapping[str, _Function],
    ctx: _Ctx,
) -> tuple[tuple[_Frame, ...], _Ctx, object]:
    """Advance a ``for`` loop already in progress: the core's loop half.

    One row-body statement, one new row, or the loop's own completion.
    The body is read from ``fn.body[pos]`` rather than stored on the
    frame, so the frame holds no parsed statements.
    """
    # This function only runs while the cursor sits on the ``for`` whose
    # rows it is walking, so the statement under it is that ``for``.
    # The tag is checked rather than tested-and-skipped: narrowing the
    # union is what lets ``current[2]`` be read at all, and a plain
    # ``if`` would make a broken invariant skip the body assignment
    # silently instead of saying so.  Raising rather than asserting
    # keeps the check under ``python -O``.
    current = frame.fn.body[frame.pos]
    if current[0] != "for":
        raise AssertionError(f"cursor left the for statement: {current[0]}")
    body = current[2]
    if frame.for_started and frame.for_body_pos < len(body):
        stmt = body[frame.for_body_pos]
        return _step_stmt(stmt, frame, frames, _advance_body_pos, globals_, ctx)
    if frame.for_ind >= len(frame.for_rows or ()):
        frame = replace(frame, for_rows=None, pos=frame.pos + 1)
        return (*frames[:-1], frame), ctx, _NO_RETURN
    row = frame.for_rows[frame.for_ind] if frame.for_rows is not None else ()
    frame = replace(frame, for_ind=frame.for_ind + 1)
    for name, value in zip(frame.for_names, row, strict=False):
        if name != "_":
            ctx = ctx._replace(scopes=_bind(frame, name, value, ctx.scopes))
    return (
        (*frames[:-1], replace(frame, for_started=True, for_body_pos=0)),
        ctx,
        _NO_RETURN,
    )
