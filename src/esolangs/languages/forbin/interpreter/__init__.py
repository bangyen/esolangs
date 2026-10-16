"""Interpreter for Forbin.

An imperative language whose only datatypes are functions and bits: functions
with bit arguments and nested definitions, iteration and range for-loops (a
range loop ``for i:1..0`` doubles as an if-statement), the NOT operator, and
the ``in``/``out`` builtins that read one bit and write one byte as eight bit
arguments (most significant first).

Input/output:
    ``in`` reads the next bit and raises at EOF (as the Brainfuck interpreter
    does); the wiki's cat example is not reproduced because its range-loop
    "while" (``for _:0..1`` runs twice) doubles every byte -- it was never
    run, Forbin being unimplemented.

Errors:
    ProgramError: Malformed syntax; no ``main`` function.
    InputExhaustedError: ``in`` when the input is exhausted.
    HaltError: A call that resolves to no function (an invalid operation), an
    undeclared identifier, ``!`` of a non-bit, ``out`` without exactly eight
    bit arguments, a ``for`` bound that is not a number, expression-position
    recursion past the host's depth limit.

Decisions:
    * The entry point is the function ``main``, called with a single dummy
      argument 0 (the examples always call ``main 0``).
    * Extra call arguments are discarded (``main 0`` passes a dummy), and
      unpassed parameters are set to 0.
    * Statements may omit the trailing ``;`` before a closing ``}`` (the
      wiki's cat example writes ``shouldLoop = 1`` with no semicolon).
    * A trailing statement semicolon is otherwise optional, matching the
      wiki's loose examples.
    * Scoping is lexical ("local to a function (and its children..."): a
      frame's scope node's ``parent`` is where its function was written, and
      an assignment updates the nearest scope holding the name, since
      ``{code} 0;`` must be "the same" as ``code``.
    * An iteration list's values are evaluated once, before the first pass.
    * ``return`` needs a value ("default is 0" is read as falling off the
      end) and ``out`` exactly eight; uneven multiple assignments pair by
      position, and a loop variable that "must first be defined" is bound
      even if it is not.
    * ``f;``, and ``(f)`` inside an expression, call with no arguments (as a
      statement, ``(f);`` calls ``f``'s result), though the wiki says
      "something has to be passed to call it" (generated code passes ``0``).
"""

from __future__ import annotations

from collections.abc import Sequence
from types import MappingProxyType

from esolangs.exceptions import HaltError
from esolangs.languages.forbin.interpreter._parse import (
    _Function,
    _Parser,
    _Statement,
)
from esolangs.languages.forbin.interpreter._scope import (
    _Closure,
    _Ctx,
    _Frame,
    _NeedByte,
    _new_scope,
    _State,
)
from esolangs.languages.forbin.interpreter._step import _advance, _run_block
from esolangs.runtime._drive import drive
from esolangs.runtime._fault import _Fault
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error


# ``_Machine`` runs on an explicit stack of :class:`_Frame` values (one per
# statement-position call in progress -- ``main`` initially, one more per
# nested call), each with a statement cursor and, while a ``for`` loop is
# active, its row iterator.  This makes ``step()`` interruptible between
# statements, between a ``for`` loop's rows, and between statement-position
# calls (``again 0;``, a call whose result is discarded) -- the granularity a
# hang can actually occur at, and the recursion pattern this language
# actually uses (there is no return-value-threading idiom across nested
# calls; ``return`` exits the whole function immediately).  A statement's own
# expression evaluation, and any *expression-position* call it contains
# (``x = f(y)``, where the assignment needs the result back synchronously),
# still runs to completion inside one ``step()``: expressions evaluate
# through ``_eval``/``_call``, and an expression-position call runs the same
# step core to completion via ``_run`` -- there is one statement
# implementation, shared by the resumable machine and direct execution.
# Forbin has no realistic program shape that recurses that way, so this
# narrower scope fixes the depth cap for the pattern the language is
# actually written in without the larger risk of converting expression
# evaluation itself into an explicit continuation stack.
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
        # First-sight numbering of functions and scopes, so a serial names
        # one of them for the whole run.  A function is keyed by ``id``:
        # parsed functions live as long as the machine.  A scope is keyed by
        # its scope id, never by its locals' ``id``: a binding replaces the
        # locals mapping, and the freed mapping's recycled id once gave one
        # program two different snapshot sequences on two runs.
        self._serials: dict[tuple[str, int], int] = {}
        self._next_serial = 0
        parser = _Parser(code)
        self.globals = parser.parse()
        if "main" not in self.globals:
            raise syntax_error(
                "Forbin program has no main function",
                "define a main function, for example main { return 0; }",
            )
        global_fn = _Function("$globals", [])
        global_scope, scopes = _new_scope(
            MappingProxyType({}), global_fn, None, MappingProxyType({})
        )
        self._global_scope = global_scope
        global_frame = _Frame(global_fn, global_scope)
        self.state = _State((), scopes, (), 0)
        for initializer in parser.initializers:
            self._run_initializer(initializer, global_frame)
        main_fn = self.globals["main"]
        main_locals = dict.fromkeys(main_fn.args, 0)
        main_scope, scopes = _new_scope(
            self.state.scopes, main_fn, global_scope, main_locals
        )
        main_frame = _Frame(main_fn, main_scope)
        self.state = _State((main_frame,), scopes, self.state.bits, self.state.reads)

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
        self.state = _State((), ctx.scopes, ctx.bits, ctx.reads)

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
        value is not meaningfully hashable; that suffices because a genuine
        hang re-executes the same cursor with the same bindings every lap.
        A call that never returns pushes a frame per step and none is
        popped, so unbounded recursion is never mistaken for a repeat: the
        frame tuple's length strictly grows.
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
                    self._serial(("fn", id(f.fn))),
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
        scope is keyed by its serial.
        """
        seen: dict[int, int] = {}
        todo: list[int] = [f.scope for f in self.state.frames]
        todo.append(self._global_scope)
        while todo:
            scope: int | None = todo.pop()
            while scope is not None:
                node = self.state.scopes[scope]
                key = self._serial(("scope", scope))
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

    def _serial(self, key: tuple[str, int]) -> int:
        """Return the serial of a function ``("fn", id)`` or ``("scope", id)``."""
        if key not in self._serials:
            self._serials[key] = self._next_serial
            self._next_serial += 1
        return self._serials[key]

    def _render(self, value: object) -> str:
        """``repr(value)``, but a closure names its function and scope.

        The scope is its defining scope's serial.
        """
        if isinstance(value, _Closure):
            fn = self._serial(("fn", id(value.fn)))
            scope = self._serial(("scope", value.scope))
            return f"<{value.fn.name or 'literal'} {fn}@{scope}>"
        return repr(value)

    def step(self) -> None:
        """Execute one statement, one ``for``-loop row, or advance a call.

        The shell: reads the bytes the statement asks for, writes what the
        transition returns.  An *expression-position* call (``x = (f y);``)
        recurses natively through ``_eval``, so a deep enough one exhausts
        Python's stack.  That is a valid Forbin operation the host cannot
        afford, not the invalid one :class:`HaltError` names; it halts here
        and says which limit it hit rather than leaking a raw traceback.
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
