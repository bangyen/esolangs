"""Interpreter for Forbin.

An imperative language whose only datatypes are functions and bits:
functions with bit arguments and nested definitions, iteration and range
for-loops (a range loop ``for i:1..0`` doubles as an if-statement), the NOT
operator, and the ``in``/``out`` builtins that read one bit and write one
byte as eight bit arguments (most significant first).

Decisions for gaps in the wiki spec (documented):
- the entry point is the function ``main``, called with a single dummy
  argument 0 (the examples always call ``main 0``);
- extra call arguments are discarded (``main 0`` passes a dummy), and
  unpassed parameters are set to 0;
- ``in`` reads the next bit and raises :class:`EOFError` when the input is
  exhausted (as the Brainfuck interpreter does); the wiki's cat example is
  not reproduced because its range-loop "while" (``for _:0..1`` runs twice)
  doubles every byte — it was never run, Forbin being unimplemented;
- statements may omit the trailing ``;`` before a closing ``}`` (the wiki's
  cat example writes ``shouldLoop = 1`` with no semicolon);
- a trailing statement semicolon is otherwise optional, matching the wiki's
  loose examples;
- scoping is lexical ("local to a function (and its children...)"): a
  frame's scope node's ``parent`` is where its function was written, and an
  assignment updates the nearest scope holding the name, since ``{code} 0;``
  must be "the same" as ``code``;
- an iteration list's values are evaluated once, before the first pass;
- ``return`` needs a value ("default is 0" is read as falling off the
  end) and ``out`` exactly eight; uneven multiple assignments pair by
  position, and a loop variable that "must first be defined" is bound
  even if it is not;
- ``f;`` and ``(f)`` call with no arguments, though the wiki says
  "something has to be passed to call it" (generated code passes ``0``);
- a call that resolves to no function is an invalid operation
  (:class:`~esolangs.exceptions.HaltError`), and malformed syntax raises
  :class:`ValueError`.

The semantics are a pure transition.  :func:`_advance` maps an immutable
``_State`` -- the explicit frame stack, the lexical scope store, the input
bit buffer and the explicit input bytes a statement may read -- to a new
state and the bytes it asks to print.  ``step`` is the shell: it reads the
bytes the transition asks for and writes what it returns.  A statement can
read any number of bits (a call may read in a loop), so the reads cannot be
hoisted; each :data:`_NeedByte` reads one more byte and retries the
deterministic transition.

``_Machine`` runs on an explicit stack of :class:`_Frame` values (one per
statement-position call in progress -- ``main`` initially, one more per
nested call), each with a statement cursor and, while a ``for`` loop is
active, its row iterator.  This makes ``step()`` interruptible between
statements, between a ``for`` loop's rows, and between statement-position
calls (``again 0;``, a call whose result is discarded) -- the granularity a
hang can actually occur at, and the recursion pattern this language
actually uses (there is no return-value-threading idiom across nested
calls; ``return`` exits the whole function immediately).  A statement's own
expression evaluation, and any *expression-position* call it contains
(``x = f(y)``, where the assignment needs the result back synchronously),
still runs to completion inside one ``step()``: expressions evaluate
through ``_eval``/``_call``, and an expression-position call runs the same
step core to completion via ``_run`` -- there is one statement
implementation, shared by the resumable machine and direct execution.
Forbin has no realistic program shape that recurses that way, so this
narrower scope fixes the depth cap for the pattern the language is
actually written in without the larger risk of converting expression
evaluation itself into an explicit continuation stack.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import product
from types import MappingProxyType
from typing import Literal, NamedTuple

from esolangs.exceptions import HaltError
from esolangs.languages.forbin.interpreter._parse import (
    _ForSpec,
    _Function,
    _Parser,
    _Statement,
    _ValueNode,
)
from esolangs.runtime._drive import drive
from esolangs.runtime._fault import _Fault
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error


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
    a pushed frame, since loop-variable/outer-variable writes land in the
    same scope.  The body itself is read from ``fn.body[pos]`` rather than
    stored, so the frame holds no parsed statements.
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
    next_scope: int
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
    next_scope: int
    bits: tuple[int, ...]
    reads: int


def _new_scope(
    scopes: Mapping[int, _Scope],
    fn: _Function,
    parent: int | None,
    locals_: Mapping[str, object],
    next_scope: int,
) -> tuple[int, int, Mapping[int, _Scope]]:
    """Add a scope node; return its id, the next id, and the new store."""
    scope = next_scope
    node = _Scope(fn, _frozen(locals_), parent)
    return scope, next_scope + 1, MappingProxyType({**scopes, scope: node})


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
    next_scope: int,
) -> tuple[_Frame, int, Mapping[int, _Scope]]:
    """Return a frame for calling ``callee``; unpassed parameters are 0."""
    locals_: dict[str, object] = dict.fromkeys(callee.fn.args, 0)
    for name, value in zip(callee.fn.args, args, strict=False):
        locals_[name] = value
    scope, next_scope, scopes = _new_scope(
        scopes, callee.fn, callee.scope, locals_, next_scope
    )
    return (
        _Frame(callee.fn, scope),
        next_scope,
        scopes,
    )


def _call(
    callee: object,
    args: list[object],
    globals_: Mapping[str, _Function],
    ctx: _Ctx,
) -> tuple[object, _Ctx]:
    """Apply a callable, threading the context through any nested run."""
    if isinstance(callee, _Closure):
        frame, next_scope, scopes = _enter(callee, args, ctx.scopes, ctx.next_scope)
        ctx = ctx._replace(scopes=scopes, next_scope=next_scope)
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

    Only reached for expression-position calls (``x = f(y)``), whose own
    recursion depth is bounded by Python's default recursion limit -- a
    statement-position call (``f(y);``) pushes onto the explicit frame
    stack instead of recursing, so that pattern is not depth-limited at
    all.  The stack still cannot grow without bound here: past the host's
    own recursion limit a runaway raises :class:`RecursionError`, which
    the ``step()`` shell reports as a halt, exactly as the old recursive
    executor did.
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
    pushed, next_scope, scopes = _enter(callee, args, ctx.scopes, ctx.next_scope)
    ctx = ctx._replace(scopes=scopes, next_scope=next_scope)
    return pushed, ctx


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
    ctx = _Ctx(state.scopes, state.next_scope, state.bits, state.reads, 0, out, inputs)
    try:
        frames, ctx, _returned = _step_frames(state.frames, globals_, ctx)
    except _NeedByte:
        raise _NeedByte(tuple(out)) from None
    except _Fault:
        raise
    except BaseException as exc:
        raise _Fault(tuple(out), exc) from None
    return _State(frames, ctx.scopes, ctx.next_scope, ctx.bits, ctx.reads), tuple(out)


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


class _Machine:
    """One Forbin run: an explicit stack of resumable call frames.

    ``self.state.frames`` holds one :class:`_Frame` per statement-position
    call in progress (``main`` initially); a call pushes a frame instead of
    recursing, so that recursion pattern is uncapped.  Only the innermost
    frame is ever touched per ``step()``.
    """

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        # Where the source ends, kept because ``ip`` still has to report a
        # position once every frame has been popped.
        self._length = len(code)
        # First-sight identity numbering: the counter hands out each
        # serial, and the dict remembers which objects were already
        # numbered, so a serial names one object for the whole run.
        # The dict stores only ids, not the objects, so this is a
        # convention, not a structural guarantee: callers must number
        # only objects that stay reachable from the machine's state for
        # the rest of the run, since a freed object's id could be
        # recycled for a different object.
        self._serials: dict[int, int] = {}
        self._next_serial = 0
        parser = _Parser(code)
        self.globals = parser.parse()
        if "main" not in self.globals:
            raise syntax_error(
                "Forbin program has no main function",
                "define a main function, for example main { return 0; }",
            )
        global_fn = _Function("$globals", [])
        global_scope, next_scope, scopes = _new_scope(
            MappingProxyType({}), global_fn, None, MappingProxyType({}), 0
        )
        self._global_scope = global_scope
        global_frame = _Frame(global_fn, global_scope)
        self.state = _State((), scopes, next_scope, (), 0)
        for initializer in parser.initializers:
            self._run_initializer(initializer, global_frame)
        main_fn = self.globals["main"]
        main_locals = dict.fromkeys(main_fn.args, 0)
        main_scope, next_scope, scopes = _new_scope(
            self.state.scopes, main_fn, global_scope, main_locals, self.state.next_scope
        )
        main_frame = _Frame(main_fn, main_scope)
        self.state = _State(
            (main_frame,), scopes, next_scope, self.state.bits, self.state.reads
        )

    def _run_initializer(self, initializer: _Statement, global_frame: _Frame) -> None:
        """Run one top-level initializer, preserving its output order.

        A read that runs out flushes the output computed before it and reads
        one more byte; a fault flushes the same prefix before it is re-raised,
        so an initializer that prints before reading at EOF or halting does
        not lose its output.
        """
        inputs: list[int] = []
        flushed = 0
        while True:
            out: list[str] = []
            ctx = _Ctx(
                self.state.scopes,
                self.state.next_scope,
                self.state.bits,
                self.state.reads,
                0,
                out,
                tuple(inputs),
            )
            try:
                _value, ctx = _run_block([initializer], global_frame, self.globals, ctx)
            except _NeedByte:
                flushed = self._flush(out, flushed)
                inputs.append(self.io.input_char())
                continue
            except BaseException:
                self._flush(out, flushed)
                raise
            break
        self._flush(out, flushed)
        self.state = _State((), ctx.scopes, ctx.next_scope, ctx.bits, ctx.reads)

    def _flush(self, effects: Sequence[str], flushed: int) -> int:
        """Print ``effects`` past ``flushed``; return the new flush count."""
        for char in effects[flushed:]:
            self.io.print_char(char)
        return len(effects)

    @property
    def frames(self) -> list[_Frame]:
        return list(self.state.frames)

    @property
    def halted(self) -> bool:
        """Whether the frame stack has emptied (``main`` returned or ended)."""
        return not self.state.frames

    # The VM's language-shaped view: a call-frame language whose store is
    # the innermost frame's integer locals.

    #: ``ip`` is a position, but not one on the source text: each live frame's statement
    #: position.
    #: Declared rather than left to the default so that a tuple nobody has
    #: classified is a missing answer instead of this one.
    ip_shape = "opaque"

    @property
    def ip(self) -> tuple[int, ...]:
        """Each live frame's statement position, outermost first.

        No frames at all means ``main`` has returned, which is reported as
        the end of the source rather than an empty tuple.
        """
        frames = self.frames
        return tuple(f.pos for f in frames) if frames else (self._length,)

    @property
    def memory(self) -> list[int]:
        """The innermost frame's integer locals."""
        if not self.state.frames:
            return []
        scope = self.state.scopes[self.state.frames[-1].scope]
        return [v for v in scope.locals.values() if type(v) is int]

    def frame_entry_key(self, frame: _Frame) -> tuple[object, ...]:
        """Return what ``frame`` is about to run, for the ancestor check.

        Two frames with equal keys replay each other, so the key is the
        function, its bindings, and the input cursor -- not the statement
        cursor, which has already moved on in the ancestor by the time the
        callee is pushed.  The input position is what keeps the check
        sound: a recursion whose base case waits on an unread byte enters
        with identical bindings every lap and is one read from returning,
        not looping.  See :func:`esolangs.vm.run_until_halt_or_ancestor`.
        """
        bindings: dict[str, object] = {}
        scope: int | None = frame.scope
        while scope is not None:
            node = self.state.scopes[scope]
            for name, value in node.locals.items():
                bindings.setdefault(name, value)
            for name, function in node.fn.nested.items():
                bindings.setdefault(name, function)
            scope = node.parent
        return (
            frame.fn,
            tuple(sorted((name, self._render(v)) for name, v in bindings.items())),
            self.io.progress(),
            self.state.bits,
            self.state.reads,
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        Locals are captured via :meth:`_render` (``repr`` with closure
        scope ids, so a snapshot is the same on every run) since a function
        value is not meaningfully hashable -- sufficient for the
        state-cycle detector's purpose, since a genuine hang re-executes
        the same cursor with the same bindings on every lap.  A call that
        never returns pushes one new frame per step and none is ever
        popped, so this cannot mistake unbounded recursion for a repeat:
        the frame tuple's length strictly grows.
        """
        return (
            tuple(
                (
                    f.fn.name,
                    f.pos,
                    tuple(
                        sorted(
                            (k, self._render(v))
                            for k, v in self.state.scopes[f.scope].locals.items()
                        )
                    ),
                    f.for_ind if f.for_rows is not None else -1,
                    f.for_body_pos if f.for_rows is not None else -1,
                    self._serial(f.fn),
                    None
                    if f.for_rows is None
                    else tuple(tuple(row) for row in f.for_rows),
                    () if f.for_rows is None else tuple(f.for_names),
                )
                for f in self.state.frames
            ),
            self.io.progress(),
            self.state.bits,
            self.state.reads,
            tuple(
                sorted(
                    (name, self._render(value))
                    for name, value in self.state.scopes[
                        self._global_scope
                    ].locals.items()
                )
            ),
            self._scopes(),
        )

    def _scopes(self) -> tuple[object, ...]:
        """Render every scope a live frame or a closure can reach.

        A closure keeps its defining scope after that frame returns, and a
        call through it can write there, so those locals are state too.  Each
        scope is keyed by its locals' identity serial, the same numbering the
        original snapshot used, so the resource ledger's exact formula still
        holds.
        """
        seen: dict[int, int] = {}
        todo: list[int] = [f.scope for f in self.state.frames]
        todo.append(self._global_scope)
        while todo:
            scope: int | None = todo.pop()
            while scope is not None:
                node = self.state.scopes[scope]
                key = self._serial(node.locals)
                if key in seen:
                    break
                seen[key] = scope
                todo += [
                    v.scope for v in node.locals.values() if isinstance(v, _Closure)
                ]
                scope = node.parent
        return tuple(
            (
                key,
                tuple(
                    sorted(
                        (k, self._render(v))
                        for k, v in self.state.scopes[seen[key]].locals.items()
                    )
                ),
            )
            for key in sorted(seen)
        )

    def _serial(self, thing: object) -> int:
        """Return ``thing``'s serial: its identity numbered by first sight."""
        key = id(thing)
        if key not in self._serials:
            self._serials[key] = self._next_serial
            self._next_serial += 1
        return self._serials[key]

    def _render(self, value: object) -> str:
        """``repr(value)``, but a closure names its function and scope.

        The scope is its defining scope's locals serial, matching the
        original numbering so the ledger's exact workspace formula holds.
        """
        if isinstance(value, _Closure):
            fn = self._serial(value.fn)
            scope = self._serial(self.state.scopes[value.scope].locals)
            return f"<{value.fn.name or 'literal'} {fn}@{scope}>"
        return repr(value)

    def step(self) -> None:
        """Execute one statement, one ``for``-loop row, or advance a call.

        The shell: it reads the bytes the statement asks for and writes
        what the transition returns.  An *expression-position* call
        (``x = (f y);``) still recurses natively through ``_eval``, so a
        deep enough one exhausts Python's own stack.  That is a valid
        Forbin operation the host cannot afford rather than the invalid
        one :class:`HaltError` names, but the alternative is leaking the
        interpreter's implementation strategy to the caller as a raw
        traceback, so it halts here and says which limit it hit.
        """
        if self.halted:
            return
        inputs: list[int] = []
        flushed = 0
        while True:
            try:
                self.state, out = _advance(self.state, self.globals, tuple(inputs))
            except _NeedByte as need:
                flushed = self._flush(need.effects, flushed)
                inputs.append(self.io.input_char())
                continue
            except _Fault as fault:
                self._flush(fault.effects, flushed)
                if isinstance(fault.error, RecursionError):
                    raise HaltError(
                        "expression-position recursion exceeded the host's depth limit",
                        hint="reduce expression-position recursion depth",
                    ) from None
                raise fault.error from None
            break
        self._flush(out, flushed)


def run(code: str, io: IO) -> None:
    """Run a Forbin program, calling ``main`` with a dummy argument."""
    machine = _Machine(code, io)
    drive(machine)
