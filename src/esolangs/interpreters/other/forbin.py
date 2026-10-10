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
  frame's ``parent`` is where its function was written, and an assignment
  updates the nearest scope holding the name, since ``{code} 0;`` must be
  "the same" as ``code``;
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

``_Machine`` runs on an explicit stack of ``_Frame``s (``self.frames``, one
per statement-position call in progress -- ``main`` initially, one more per
nested call), each with a statement cursor and, while a ``for`` loop is
active, its row iterator.  This makes ``step()`` interruptible between
statements, between a ``for`` loop's rows, and between statement-position
calls (``again 0;``, a call whose result is discarded) -- the granularity a
hang can actually occur at, and the recursion pattern this language
actually uses (there is no return-value-threading idiom across nested
calls; ``return`` exits the whole function immediately).  A statement's own
expression evaluation, and any *expression-position* call it contains
(``x = f(y)``, where the assignment needs the result back synchronously),
still runs to completion inside one ``step()`` through the original
recursive ``_eval``/``_call``/``_run`` -- Forbin has no realistic program
shape that recurses that way, so this narrower scope fixes the depth cap
for the pattern the language is actually written in without the larger risk
of converting expression evaluation itself into an explicit continuation
stack.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from esolangs._drive import drive
from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO
from esolangs.interpreters.other._forbin_parse import (
    _ForSpec,
    _Function,
    _Parser,
    _Statement,
    _ValueNode,
)
from esolangs.interpreters.source_hints import syntax_error

#: Functions here that call an IO effect outside the ``run``/``_Machine``
#: shells, read by the interpreter-convention sweep.  ``_call`` is a
#: documented, nonconforming recursive evaluator: a read or write happens
#: part-way down a recursive descent, so making it pure would need an
#: explicit continuation stack and ordered I/O effects.  ``_BitReader.read``
#: is the same boundary under its helper type.
REACHES_IO = frozenset({"_BitReader.read", "_call"})


class _BitReader:
    """Serves the input one bit at a time, most significant first."""

    def __init__(self, io: IO) -> None:
        self.io = io
        self.bits: list[int] = []
        self.reads = 0

    def read(self) -> int:
        if not self.bits:
            byte = self.io.input_char()
            self.bits = [(byte >> k) & 1 for k in range(7, -1, -1)]
        bit = self.bits.pop(0)
        self.reads += 1
        return bit


class _Frame:
    """One function invocation: its function, defining scope, and locals.

    ``body``/``pos`` is the statement list a frame is executing and its
    cursor; ``for_rows``/``for_names``/``for_ind`` track a ``for`` loop in
    progress at that cursor, one row resumed per step, and
    ``for_body``/``for_body_pos`` is the cursor into the *current* row's
    body -- a nested resumable sequence sharing this frame's scope, not a
    pushed frame, since loop-variable/outer-variable writes land in the
    same ``locals``.
    """

    __slots__ = (
        "body",
        "fn",
        "for_body",
        "for_body_pos",
        "for_ind",
        "for_names",
        "for_rows",
        "locals",
        "parent",
        "pos",
    )

    def __init__(self, fn: _Function, parent: _Frame | None) -> None:
        self.fn = fn
        self.parent = parent
        self.locals: dict[str, object] = {}
        self.body = fn.body
        self.pos = 0
        self.for_rows: list[list[object]] | None = None
        self.for_names: list[str] = []
        self.for_ind = 0
        self.for_body: list[_Statement] = []
        self.for_body_pos = 0

    def at(self, **fields: object) -> _Frame:
        """Return a copy of this frame with ``fields`` replaced.

        A frame's cursors advance by replacement rather than by
        assignment, so a step returns the frame that follows.  The copy
        shares ``locals`` -- the same dict object, not a copy of it --
        which is what keeps a child frame's ``parent`` pointer correct
        after its parent has been replaced: the stale parent and the live
        one resolve names through one store, so a write through either is
        seen by both.  ``fn``, ``body``, ``for_rows``, ``for_names`` and
        ``for_body`` are shared for the same reason and are never mutated
        after they are set.
        """
        copy = _Frame.__new__(_Frame)
        for slot in _Frame.__slots__:
            object.__setattr__(copy, slot, getattr(self, slot))
        for name, value in fields.items():
            object.__setattr__(copy, name, value)
        return copy


@dataclass(frozen=True, eq=False)
class _Closure:
    """A function value: its definition and the scope it was written in."""

    fn: _Function
    env: _Frame

    def __repr__(self) -> str:
        """Name the function and its scope (a scope is its locals dict)."""
        return f"<{self.fn.name or 'literal'} {id(self.fn):x}@{id(self.env.locals):x}>"


def _lookup(frame: _Frame, name: str, globals_: dict[str, _Function]) -> object:
    """Resolve a variable, builtin, or function name from ``frame`` outward.

    The chain is lexical: a frame's ``parent`` is the scope its function
    was defined in, so a top-level function sees globals, not its caller.
    """
    scope: _Frame | None = frame
    root = frame
    while scope is not None:
        if name in scope.locals:
            return scope.locals[name]
        if name in scope.fn.nested:
            return _Closure(scope.fn.nested[name], scope)
        root, scope = scope, scope.parent
    if name in ("in", "out"):
        return name
    if name in globals_:
        return _Closure(globals_[name], root)
    raise HaltError(
        f"undeclared identifier {name!r}",
        hint="declare the identifier before using it; check its spelling",
    )


def _eval(
    node: _ValueNode,
    frame: _Frame,
    globals_: dict[str, _Function],
    reader: _BitReader,
    depth: int,
) -> object:
    if node[0] == "lit":
        return node[1]
    if node[0] == "not":
        value = _eval(node[1], frame, globals_, reader, depth)
        if value in (0, 1):
            return 1 - value
        raise HaltError("! needs a bit", hint="use 0 or 1 as the operand")
    if node[0] == "var":
        return _lookup(frame, node[1], globals_)
    if node[0] == "fnlit":
        return _Closure(node[1], frame)
    callee = _eval(node[1], frame, globals_, reader, depth)
    args = [_eval(a, frame, globals_, reader, depth) for a in node[2]]
    return _call(callee, args, globals_, reader, depth)


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


def _enter(callee: _Closure, args: list[object]) -> _Frame:
    """Return a frame for calling ``callee``; unpassed parameters are 0."""
    frame = _Frame(callee.fn, callee.env)
    for name in callee.fn.args:
        frame.locals[name] = 0
    for name, value in zip(callee.fn.args, args, strict=False):
        frame.locals[name] = value
    return frame


def _bind(frame: _Frame, name: str, value: object) -> None:
    """Assign ``name`` where it lives, else as a new local of ``frame``.

    The wiki makes ``{code} 0;`` the same as ``code``, so a write inside a
    literal (or a nested function) reaches the enclosing variable.
    """
    scope: _Frame | None = frame
    while scope is not None:
        if name in scope.locals:
            scope.locals[name] = value
            return
        scope = scope.parent
    frame.locals[name] = value


def _call(
    callee: object,
    args: list[object],
    globals_: dict[str, _Function],
    reader: _BitReader,
    depth: int,
) -> object:
    if isinstance(callee, _Closure):
        result = _run(_enter(callee, args), globals_, reader, depth + 1)
        return result if result is not None else 0
    if isinstance(callee, str):
        if callee == "in":
            return reader.read()
        # A name only evaluates to a string for the two builtins -- see the
        # ``("in", "out")`` test in ``_value`` -- so the remaining one is
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
        reader.io.print_char(chr(byte))
        return 0
    raise HaltError(
        "called value is not a function",
        hint="call a function value rather than a scalar or list",
    )


def _run(
    frame: _Frame, globals_: dict[str, _Function], reader: _BitReader, depth: int = 0
) -> object | None:
    """Run ``frame``'s body to completion, natively recursing into any call.

    Only reached today for expression-position calls (``x = f(y)``), whose
    own recursion depth is bounded by Python's default recursion limit
    (not this module's old, invented 250 cap) -- a statement-position call
    (``f(y);``) is stepped through ``_Machine``'s explicit ``frames`` stack
    instead and is not depth-limited at all.
    """
    for stmt in frame.fn.body:
        got = _exec_stmt(stmt, frame, globals_, reader, depth)
        if got is not None:
            return got
    return None


def _exec_stmt(
    stmt: _Statement,
    frame: _Frame,
    globals_: dict[str, _Function],
    reader: _BitReader,
    depth: int,
) -> object | None:
    """Execute one statement, returning its value if it was a ``return``."""
    if stmt[0] == "return":
        return _eval(stmt[1], frame, globals_, reader, depth)
    if stmt[0] == "assign":
        targets, rhs = stmt[1], stmt[2]
        if len(rhs) == 1:
            bindings = [
                (name, _eval(rhs[0], frame, globals_, reader, depth))
                for name in targets
                if name != "_"
            ]
        else:
            bindings = [
                (name, _eval(value, frame, globals_, reader, depth))
                for name, value in zip(targets, rhs, strict=False)
                if name != "_"
            ]
        for name, value in bindings:
            _bind(frame, name, value)
        return None
    if stmt[0] == "call":
        callee = _eval(stmt[1], frame, globals_, reader, depth)
        args = [_eval(a, frame, globals_, reader, depth) for a in stmt[2]]
        _call(callee, args, globals_, reader, depth)
        return None
    # The three arms above are the other statement kinds, so what is
    # left is a ``for``.
    spec, body = stmt[1], stmt[2]
    rows: list[list[object]]
    if spec[0] == "range":
        _, name, start_node, end_node = spec
        start = _eval(start_node, frame, globals_, reader, depth)
        end = _eval(end_node, frame, globals_, reader, depth)
        lo, hi = _bound(start, "start"), _bound(end, "end")
        rows = [[v] for v in range(lo, hi + 1)] if lo <= hi else []
        names = [name]
    else:
        _, names, patterns = spec
        rows = []
        for pat in patterns:
            items = pat[1] if pat[0] == "group" else [pat]
            wilds = [j for j, p in enumerate(items) if p[0] == "*"]
            if not wilds:
                rows.append(
                    [
                        (
                            _eval(p[1], frame, globals_, reader, depth)
                            if p[0] == "value"
                            else 0
                        )
                        for p in items
                    ]
                )
            else:
                import itertools

                for combo in itertools.product((0, 1), repeat=len(wilds)):
                    row: list[object] = []
                    w = 0
                    for p in items:
                        if p[0] == "*":
                            row.append(combo[w])
                            w += 1
                        else:
                            row.append(_eval(p[1], frame, globals_, reader, depth))
                    rows.append(row)
    for row in rows:
        for name, bound in zip(names, row, strict=False):
            if name != "_":
                _bind(frame, name, bound)
        got = _exec_block(body, frame, globals_, reader, depth)
        if got is not None:
            return got
    return None


def _exec_block(
    stmts: list[_Statement],
    frame: _Frame,
    globals_: dict[str, _Function],
    reader: _BitReader,
    depth: int,
) -> object | None:
    """Run a block of statements in ``frame``'s scope; None unless a return fired."""
    for stmt in stmts:
        got = _exec_stmt(stmt, frame, globals_, reader, depth)
        if got is not None:
            return got
    return None


def _for_rows(
    spec: _ForSpec,
    frame: _Frame,
    globals_: dict[str, _Function],
    reader: _BitReader,
    depth: int,
) -> tuple[list[list[object]], list[str]]:
    """Compute a ``for`` statement's iteration rows and bound variable names."""
    if spec[0] == "range":
        _, name, start_node, end_node = spec
        start = _eval(start_node, frame, globals_, reader, depth)
        end = _eval(end_node, frame, globals_, reader, depth)
        lo, hi = _bound(start, "start"), _bound(end, "end")
        range_rows: list[list[object]] = (
            [[v] for v in range(lo, hi + 1)] if lo <= hi else []
        )
        return range_rows, [name]
    _, names, patterns = spec
    rows: list[list[object]] = []
    for pat in patterns:
        items = pat[1] if pat[0] == "group" else [pat]
        wilds = [j for j, p in enumerate(items) if p[0] == "*"]
        if not wilds:
            rows.append(
                [
                    (
                        _eval(p[1], frame, globals_, reader, depth)
                        if p[0] == "value"
                        else 0
                    )
                    for p in items
                ]
            )
        else:
            import itertools

            for combo in itertools.product((0, 1), repeat=len(wilds)):
                row: list[object] = []
                w = 0
                for p in items:
                    if p[0] == "*":
                        row.append(combo[w])
                        w += 1
                    else:
                        row.append(_eval(p[1], frame, globals_, reader, depth))
                rows.append(row)
    return rows, names


def _start_statement_call(
    stmt: _Statement,
    frame: _Frame,
    globals_: dict[str, _Function],
    reader: _BitReader,
) -> _Frame | Literal[False] | None:
    """Return a pushed frame, False for a completed call, or None for a noncall."""
    if stmt[0] != "call":
        return None
    callee = _eval(stmt[1], frame, globals_, reader, 0)
    args = [_eval(a, frame, globals_, reader, 0) for a in stmt[2]]
    if not isinstance(callee, _Closure):
        _call(callee, args, globals_, reader, 0)
        return False
    return _enter(callee, args)


@dataclass
class _State:
    """The live call frames and buffered bit reader of a Forbin run."""

    frames: list[_Frame]
    reader: _BitReader


class _Machine:
    """One Forbin run: an explicit stack of resumable call frames.

    ``self.frames`` holds one ``_Frame`` per statement-position call in
    progress (``main`` initially); a call pushes a frame instead of
    recursing, so that recursion pattern is uncapped.  Only the innermost
    frame (``self.frames[-1]``) is ever touched per ``step()``.
    """

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        # Where the source ends, kept because ``ip`` still has to report a
        # position once every frame has been popped.
        self._length = len(code)
        parser = _Parser(code)
        self.globals = parser.parse()
        if "main" not in self.globals:
            raise syntax_error(
                "Forbin program has no main function",
                "define a main function, for example main { return 0; }",
            )
        reader = _BitReader(io)
        self.global_frame = _Frame(_Function("$globals", []), None)
        for initializer in parser.initializers:
            _exec_stmt(initializer, self.global_frame, self.globals, reader, 0)
        main_fn = self.globals["main"]
        main_frame = _Frame(main_fn, self.global_frame)
        # unpassed parameters are set to 0 (per the wiki); main is called
        # with a single dummy argument 0, so every parameter ends up 0
        for name in main_fn.args:
            main_frame.locals[name] = 0
        self.state = _State([main_frame], reader)
        # Identity -> (serial, object): holding the object keeps its id
        # from being reused, so a serial names one object for the run.
        self._serials: dict[int, tuple[int, object]] = {}

    @property
    def reader(self) -> _BitReader:
        return self.state.reader

    @property
    def frames(self) -> list[_Frame]:
        return self.state.frames

    @property
    def halted(self) -> bool:
        """Whether the frame stack has emptied (``main`` returned or ended)."""
        return not self.frames

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
        if not self.frames:
            return []
        return [v for v in self.frames[-1].locals.values() if type(v) is int]

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
        scope: _Frame | None = frame
        while scope is not None:
            for name, value in scope.locals.items():
                bindings.setdefault(name, value)
            for name, function in scope.fn.nested.items():
                bindings.setdefault(name, function)
            scope = scope.parent
        return (
            frame.fn,
            tuple(sorted((name, self._render(v)) for name, v in bindings.items())),
            self.io.progress(),
            tuple(self.reader.bits),
            self.reader.reads,
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        Locals are captured via :meth:`_render` (``repr`` with closure
        identities as first-seen serials, so a snapshot is the same on
        every run) since a function value is not
        meaningfully hashable (it closes over live, mutable frames) --
        sufficient for the state-cycle detector's purpose, since a
        genuine hang re-executes the same cursor with the same bindings
        on every lap.  A call that never returns pushes one new frame per
        step and none is ever popped, so this cannot mistake unbounded
        recursion for a repeat: the frame tuple's length strictly grows.
        """
        return (
            tuple(
                (
                    f.fn.name,
                    f.pos,
                    tuple(sorted((k, self._render(v)) for k, v in f.locals.items())),
                    f.for_ind if f.for_rows is not None else -1,
                    f.for_body_pos if f.for_rows is not None else -1,
                    self._serial(f.fn),
                    None
                    if f.for_rows is None
                    else tuple(tuple(row) for row in f.for_rows),
                    () if f.for_rows is None else tuple(f.for_names),
                )
                for f in self.frames
            ),
            self.io.progress(),
            tuple(self.reader.bits),
            self.reader.reads,
            tuple(
                sorted(
                    (name, self._render(value))
                    for name, value in self.global_frame.locals.items()
                )
            ),
            self._scopes(),
        )

    def _scopes(self) -> tuple[object, ...]:
        """Render every scope a live frame or a closure can reach.

        A closure keeps its defining scope after that frame returns, and a
        call through it can write there, so those locals are state too.
        """
        seen: dict[int, _Frame] = {}
        todo: list[_Frame | None] = [*self.frames, self.global_frame]
        while todo:
            scope = todo.pop()
            while scope is not None and self._serial(scope.locals) not in seen:
                seen[self._serial(scope.locals)] = scope
                todo += [
                    v.env for v in scope.locals.values() if isinstance(v, _Closure)
                ]
                scope = scope.parent
        return tuple(
            (key, tuple(sorted((k, self._render(v)) for k, v in s.locals.items())))
            for key, s in sorted(seen.items())
        )

    def _serial(self, thing: object) -> int:
        """Return ``thing``'s serial: its identity numbered by first sight."""
        return self._serials.setdefault(id(thing), (len(self._serials), thing))[0]

    def _render(self, value: object) -> str:
        """``repr(value)``, but a closure names its identities by serial."""
        if isinstance(value, _Closure):
            fn, scope = self._serial(value.fn), self._serial(value.env.locals)
            return f"<{value.fn.name or 'literal'} {fn}@{scope}>"
        return repr(value)

    def step(self) -> None:
        """Execute one statement, one ``for``-loop row, or advance a call.

        An *expression-position* call (``x = (f y);``) still recurses
        natively through ``_eval``, so a deep enough one exhausts Python's
        own stack.  That is a valid Forbin operation the host cannot
        afford rather than the invalid one :class:`HaltError` names, but
        the alternative is leaking the interpreter's implementation
        strategy to the caller as a raw traceback, so it halts here and
        says which limit it hit.  The wrapping lives on ``step`` rather
        than ``run`` because generators and the hang detectors drive
        ``step`` directly; ``run`` is a loop over it and is covered too.
        """
        try:
            self._step_once()
        except RecursionError:
            raise HaltError(
                "expression-position recursion exceeded the host's depth limit",
                hint="reduce expression-position recursion depth",
            ) from None

    def _step_once(self) -> None:
        """Execute one statement, one ``for``-loop row, or advance a call."""
        if self.halted:
            return
        frame = self.frames[-1]

        if frame.for_rows is not None:
            self._step_for(frame)
            return

        if frame.pos >= len(frame.body):
            self._pop()
            return

        stmt = frame.body[frame.pos]
        if stmt[0] == "for":
            spec = stmt[1]
            rows, names = _for_rows(spec, frame, self.globals, self.reader, 0)
            self.frames[-1] = frame.at(for_rows=rows, for_names=names, for_ind=0)
            return

        pushed = _start_statement_call(stmt, frame, self.globals, self.reader)
        if isinstance(pushed, _Frame):
            self.frames[-1] = frame.at(pos=frame.pos + 1)
            self.frames.append(pushed)
            return
        got = (
            None
            if pushed is False
            else _exec_stmt(stmt, frame, self.globals, self.reader, 0)
        )
        self.frames[-1] = frame.at(pos=frame.pos + 1)
        if got is not None:
            self._pop()

    def _step_for(self, frame: _Frame) -> None:
        """Advance a ``for`` loop already in progress.

        One row-body statement, one new row, or the loop's own completion.
        """
        if frame.for_body_pos < len(frame.for_body):
            stmt = frame.for_body[frame.for_body_pos]
            pushed = _start_statement_call(stmt, frame, self.globals, self.reader)
            if isinstance(pushed, _Frame):
                self.frames[-1] = frame.at(for_body_pos=frame.for_body_pos + 1)
                self.frames.append(pushed)
                return
            got = (
                None
                if pushed is False
                else _exec_stmt(stmt, frame, self.globals, self.reader, 0)
            )
            self.frames[-1] = frame.at(for_body_pos=frame.for_body_pos + 1)
            if got is not None:
                self._pop()
            return
        if frame.for_ind >= len(frame.for_rows or []):
            self.frames[-1] = frame.at(for_rows=None, pos=frame.pos + 1)
            return
        row = frame.for_rows[frame.for_ind] if frame.for_rows is not None else []
        frame = frame.at(for_ind=frame.for_ind + 1)
        self.frames[-1] = frame
        for name, value in zip(frame.for_names, row, strict=False):
            if name != "_":
                _bind(frame, name, value)
        # This method only runs while the cursor sits on the ``for`` whose
        # rows it is walking, so the statement under it is that ``for``.
        # The tag is checked rather than tested-and-skipped: narrowing the
        # union is what lets ``current[2]`` be read at all, and a plain
        # ``if`` would make a broken invariant skip the body assignment
        # silently instead of saying so.  Raising rather than asserting
        # keeps the check under ``python -O``.
        # The message names the tag actually found.  Being unreachable, the
        # line carries mutants no test can kill whatever it says -- measured
        # at three for a constant string and three for this -- so the
        # spelling is chosen for what it reports if the impossible happens.
        current = frame.body[frame.pos]
        if current[0] != "for":
            raise AssertionError(f"cursor left the for statement: {current[0]}")
        self.frames[-1] = frame.at(for_body=current[2], for_body_pos=0)

    def _pop(self) -> None:
        """Pop the finished top frame.

        A statement-position call's return value is discarded, matching
        the language's no-value-threading recursion idiom.
        """
        self.frames.pop()


def run(code: str, io: IO) -> None:
    """Run a Forbin program, calling ``main`` with a dummy argument."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
