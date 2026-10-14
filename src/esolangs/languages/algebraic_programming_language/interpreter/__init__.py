"""Interpreter for Algebraic Programming Language.

An algebra-shaped language with no input command and no output command.
A program is a series of lines: a line *containing* ``=`` is a definition
(a variable, a function ``F(x) = ...``, or a custom operator ``a ~ b =
...``), and a line without one is *executed*, its result printed to
STDOUT.  Every lowercase variable appearing on an executed line is read
from user input, so reading is a side effect of naming a variable and
printing is a side effect of having a line to evaluate.  The only data
type is a number.

Branching is short-circuit evaluation.  ``&`` and ``|`` skip their
right-hand side, and ``$`` (return) may *be* that side, so ``x & $0``
returns 0 exactly when ``x`` is truthy -- the wiki's own spelling of
"not", and the only conditional the language has.  Looping is the same
mechanism recursing: the wiki's truth machine is ``x? = x & x?``.

Decisions for gaps in the wiki spec (documented):

- **Input binding is a pre-scan.**  The spec says variables are "set
  initially to user input in the order they first appear in the line",
  so this interpreter binds every unbound lowercase variable on an
  executed line *before* evaluating it, in left-to-right order of first
  appearance.  Evaluating lazily would let a short-circuit skip a read
  and consume input in an order the spec's own worked example (``a + b +
  d`` then ``c + e + b`` asking for ``a, b, d, c, e``) contradicts.
  Bindings persist across lines, which is what makes that example ask
  for ``b`` once.  Only executed lines read: an assignment's right side
  naming an unbound variable is an error ("that variable won't be input"
  says nothing of the others).
- **``$`` binds like unary ``-``**, so ``$y * 2`` is ``($y) * 2``: the
  wiki's own ``CEIL`` writes ``$(n - n % 1 + 1)``.
- **Truthiness and the value of a short-circuit.**  The wiki pins only
  the false case ("false -> 0 or 0.0").  Zero is false and every other
  number is true; ``&`` returns its right operand when the left is
  truthy and ``0`` otherwise, and ``|`` returns its left operand when
  that is truthy and its right otherwise.  This is the reading that
  makes the wiki's ``WHILE`` example terminate.
- **Printing.**  An executed line prints its result followed by a
  newline; an integral value prints without a trailing ``.0`` (so the
  Hello-World example prints ``72``, not ``72.0``).  A line whose
  evaluation returns via a top-level ``$`` still prints.
- **Numbers.**  Values are Python ``int`` where a computation stays
  integral and ``float`` once division or a fractional literal makes it
  otherwise, so the unbounded integers the wiki's Turing-completeness
  argument relies on are unbounded here.
- **EOF** while binding a variable raises :class:`EOFError`, as the
  Brainfuck interpreter does; a line that is not a number raises
  :class:`~esolangs.exceptions.HaltError`.
- Malformed programs raise :class:`ValueError`: an unparsable
  expression, an unknown name, an unbalanced ``()`` or ``{}``, a
  definition whose left-hand side is not a variable, call, or operator
  pattern, a call with the wrong argument count, and the wiki's own
  ``1(2)`` (bracket multiplication is invalid syntax).
- Division or modulo by zero, and ``0 ** -1``, raise
  :class:`~esolangs.exceptions.HaltError`.
- **An uppercase name defined without parentheses** (``F = 7``) is a
  nullary function, called as ``F()``.  The wiki only writes ``F() =
  123``, but its own rule that a bare-variable left-hand side is an
  assignment is restricted to *lowercase* names, so this is the reading
  that leaves the uppercase case meaning something.  Printing a function
  rather than calling it is an invalid operation
  (:class:`~esolangs.exceptions.HaltError`), since the only printable
  values are numbers.

``_Machine`` evaluates on an explicit stack of :class:`_Frame` objects
rather than by Python recursion, because in this language recursion *is*
the loop.  A ``step()`` that evaluated a whole line would never return on
``n?``, the frame stack would never be observed growing, and
:func:`~esolangs.vm.run_until_halt_or_ancestor` would have nothing to
step between.  Each frame holds one call's expression and a cursor into
its sub-evaluations, so ``step()`` advances exactly one node and a
recursion pushes one frame per lap -- the granularity the ancestor check
needs to prove ``x? = x & x?`` hangs.

Input numbers are whitespace-delimited tokens; the spec does not define their
text framing.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from types import MappingProxyType

from esolangs.exceptions import HaltError
from esolangs.languages.algebraic_programming_language.interpreter._parse import (
    _as_number,
    _Bin,
    _blocks,
    _body,
    _Call,
    _Definition,
    _free_variables,
    _is_lower,
    _Node,
    _Number,
    _number,
    _parse_lhs,
    _Parser,
    _split_definition,
    _tokens,
)
from esolangs.runtime._drive import drive
from esolangs.runtime.io import IO
from esolangs.runtime.memory import format_integer
from esolangs.runtime.source_hints import syntax_error


@dataclass(frozen=True)
class _Frame:
    """One call in progress: its body, its bindings, and its cursor.

    ``work`` is an explicit stack of ``(node, resolved operands)`` pairs
    standing in for what Python recursion would keep on its own stack, so
    a single ``step()`` resolves one node and returns.  ``stmt`` indexes
    the definition's body, since a multiline function prints every
    statement but its last.

    ``printing`` marks the synthetic frame wrapping an *executed line*,
    whose result goes to STDOUT; ``assign`` names the variable an
    assignment line binds instead.  Both are false/None for an ordinary
    call, whose value simply returns to its caller.

    Frozen with tuple collections, so a step returns new frames rather
    than editing the ones it was handed -- the old state a caller holds
    stays intact.
    """

    fn: _Definition
    locals: Mapping[str, object]
    stmt: int
    work: tuple[tuple[_Node, tuple[object, ...]], ...]
    value: object = 0
    returned: bool = False
    printing: bool = False
    assign: str | None = None

    def __repr__(self) -> str:
        """Identify the frame by its function and cursor."""
        return f"<frame {self.fn.name} @{self.stmt}>"


class _NeedInput(Exception):  # noqa: N818 - an internal resumption signal
    """Signals that a line needs one more input token than supplied.

    Raised by :func:`_start_line` when binding a free variable finds the
    explicit input tuple exhausted; a line start has printed nothing yet.
    The shell reads one more token and calls :func:`_advance` again; the
    transition is deterministic, so the retry reaches the same point with
    the new value.
    """


def _frozen[T](mapping: Mapping[str, T]) -> Mapping[str, T]:
    """Return ``mapping`` as an immutable mapping, sharing an existing freeze."""
    return (
        mapping if isinstance(mapping, MappingProxyType) else MappingProxyType(mapping)
    )


@dataclass(frozen=True)
class _State:
    """Every changing value in an Algebraic Programming Language run.

    A value, not a record: the dictionaries are copied before a write, the
    frames are an immutable tuple, and :func:`_advance` returns a new one.
    """

    defs: Mapping[str, _Definition]
    globals: Mapping[str, object]
    frames: tuple[_Frame, ...]
    line: int
    steps: int = 0


class _Machine:
    """The run state: the definitions, the globals, and the call stack.

    A program is a list of logical lines; ``self.line`` is the cursor into
    the executed ones.  A definition line binds a name and advances.  An
    executed line binds its free variables from input, then evaluates on
    the frame stack, printing the result when the stack empties.
    """

    #: The wiki gives no bound; this caps *one* line's evaluation so a
    #: runaway expression cannot allocate without limit while still
    #: leaving the hang detectors room to prove a loop.  Reset per line,
    #: so a long program of short lines is not cut off.
    _WORK_LIMIT = 1 << 20

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.lines = tuple(_blocks(code))
        self.state = _State(MappingProxyType({}), MappingProxyType({}), (), 0)
        # Identity -> (serial, object): holding the object keeps its id
        # from being reused, so a serial names one object for the run.
        self._serials: dict[int, tuple[int, object]] = {}

    @property
    def defs(self) -> dict[str, _Definition]:
        """The definitions, as a fresh dict for the VM's views."""
        return dict(self.state.defs)

    @property
    def globals(self) -> dict[str, object]:
        """The global bindings, as a fresh dict for the VM's views."""
        return dict(self.state.globals)

    @property
    def frames(self) -> list[_Frame]:
        return list(self.state.frames)

    @property
    def line(self) -> int:
        return self.state.line

    @property
    def halted(self) -> bool:
        """Whether every line has been executed and no frame is live."""
        return self.line >= len(self.lines) and not self.frames

    #: ``ip`` starts with a line number rather than a cell or an offset,
    #: with each open frame's index after it.
    ip_shape = "line"

    @property
    def ip(self) -> tuple[int, ...]:
        """The line cursor followed by each live frame's statement index."""
        return (self.line, *(f.stmt for f in self.state.frames))

    @property
    def memory(self) -> list[int]:
        """The global bindings' integral values, in name order.

        APL has no addressable store; the nearest thing is the set of
        variables input has bound, which is what a reader wants to see.
        Non-integral values are truncated towards zero and function values
        are reported as 0, since this view is typed ``list[int]``.
        """
        return [
            int(v) if isinstance(v, (int, float)) else 0
            for _, v in sorted(self.state.globals.items())
        ]

    @property
    def stack(self) -> list[object]:
        """The live call stack, outermost first."""
        return list(self.state.frames)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        Typed keys preserve exact numbers and retained function identity.
        A redefined ``F`` can call its older body through a saved alias;
        name-only keys incorrectly reported that finite call as a cycle.
        The input cursor distinguishes calls that keep reading.

        The work stack is captured *by content*, not by depth.  Recording
        only its length made two genuinely different states compare equal
        -- one operand of ``1 + 1`` resolved versus both -- and the cycle
        detector called a halting program a hang.  A node is identified
        by identity, which is stable because the parse tree is built once
        and never rewritten.  Identities are reported as first-seen
        serials rather than raw ``id``s, so a snapshot is small and the
        same on every run.
        """
        return (
            self.line,
            tuple(sorted((k, self._key(v)) for k, v in self.state.globals.items())),
            tuple(
                (
                    self._key(f.fn),
                    f.stmt,
                    tuple(
                        (self._serial(node), tuple(self._key(v) for v in done))
                        for node, done in f.work
                    ),
                    self._key(f.value),
                    f.returned,
                    tuple(sorted((k, self._key(v)) for k, v in f.locals.items())),
                )
                for f in self.state.frames
            ),
            self.io.progress(),
        )

    def frame_entry_key(self, frame: object) -> tuple[object, ...]:
        """Return what ``frame`` is about to run, for the ancestor check.

        Two frames with equal keys replay each other, so the key is the
        function, its bindings, and the input cursor.  The input position
        carries the soundness: a recursion whose base case waits on an
        unread line enters with identical bindings every lap and is one
        read from returning, not looping.  See
        :func:`esolangs.vm.run_until_halt_or_ancestor`.
        """
        if not isinstance(frame, _Frame):
            raise AssertionError("isinstance(frame, _Frame)")
        return (
            self._key(frame.fn),
            tuple(sorted((k, self._key(v)) for k, v in frame.locals.items())),
            self.io.progress(),
        )

    def _serial(self, thing: object) -> int:
        """Return ``thing``'s serial: its identity numbered by first sight."""
        return self._serials.setdefault(id(thing), (len(self._serials), thing))[0]

    def _key(self, value: object) -> tuple[object, ...]:
        """Keep numeric types and retained function identities distinct."""
        if isinstance(value, _Definition):
            return (
                "function",
                self._serial(value),
                value.name,
                tuple(value.params),
                tuple(self._serial(node) for node in value.body),
                tuple(value.control),
            )
        if isinstance(value, float):
            return ("float", value.hex())
        return ("integer", value)

    def step(self) -> None:
        """Advance the program by one definition, read, or expression node.

        The shell: it reads the tokens the line asks for, applies the pure
        transition, and prints what the transition asks it to.  Binding a
        line's free variables can need any number of reads, so they cannot
        be hoisted; each :data:`_NeedInput` reads one more token and retries.
        Output comes only at a step's end, so a fault has nothing to flush.
        """
        if self.halted:
            return
        inputs: list[_Number] = []
        while True:
            try:
                state, out = _advance(self.state, self.lines, inputs, self._WORK_LIMIT)
            except _NeedInput:
                inputs.append(self._read_number())
                continue
            break
        self.state = state
        if out is not None:
            self.io.print_str(out)

    def _read_number(self) -> _Number:
        """Read one whitespace-delimited numeric token."""
        text = self.io.input_token().strip()
        try:
            return _number(text)
        except ValueError as exc:
            raise HaltError(
                f"input {text!r} is not a number",
                hint="supply a decimal number as input",
            ) from exc


def _set_top(state: _State, frame: _Frame) -> _State:
    """Return ``state`` with its innermost frame replaced by ``frame``."""
    return replace(state, frames=(*state.frames[:-1], frame))


def _push_work(frame: _Frame, node: _Node) -> _Frame:
    """Return ``frame`` with ``node`` queued as the next sub-evaluation."""
    return replace(frame, work=(*frame.work, (node, ())))


def _pop_work(frame: _Frame) -> _Frame:
    """Return ``frame`` with its innermost work item dropped."""
    return replace(frame, work=frame.work[:-1])


def _append_done(frame: _Frame, value: object) -> _Frame:
    """Return ``frame`` with ``value`` delivered to its innermost node."""
    node, done = frame.work[-1]
    return replace(frame, work=(*frame.work[:-1], (node, (*done, value))))


def _format_value(value: object) -> str:
    """Render one result the way the wiki's examples read, plus a newline."""
    number = _as_number(value)
    text = format_integer(number) if isinstance(number, int) else _format_float(number)
    return text + "\n"


# The semantics are a pure transition: :func:`_advance` maps an immutable
# :class:`_State` (the definitions, the globals, the frame tuple, the line cursor) plus
# the explicit input values a line may read to a new state and the text it asks to
# print.  ``step`` is the shell: it reads the tokens the line asks for, applies the
# transition, and writes what it returns.  A line binds every free variable before
# evaluating it, so the number of reads is not known ahead of evaluation; each
# :data:`_NeedInput` reads one more token and retries the deterministic transition.
def _advance(
    state: _State,
    lines: Sequence[str],
    inputs: Sequence[_Number] = (),
    work_limit: int = 1 << 20,
) -> tuple[_State, str | None]:
    """Return the state after one step, and the text to print, if any.

    Pure: ``lines`` and ``inputs`` are parameters, and a write leaves as
    the returned string.  A line whose input binding needs a value the
    explicit ``inputs`` does not hold raises :data:`_NeedInput`.
    """
    if state.frames:
        return _step_frame(state, work_limit)
    return _start_line(state, lines, inputs)


def _start_line(
    state: _State, lines: Sequence[str], inputs: Sequence[_Number]
) -> tuple[_State, str | None]:
    """Consume one logical line: define a name, or begin evaluating."""
    text = lines[state.line]
    line = state.line + 1
    split = _split_definition(text)
    if split is None:
        node = _Parser(_tokens(text), state.defs).parse()
        globals_ = _bind_inputs(node, state.globals, inputs)
        definition = _Definition("", [], [node])
        frame = _Frame(
            fn=definition,
            locals=MappingProxyType({}),
            stmt=0,
            work=((node, ()),),
            printing=True,
        )
        return (
            replace(
                state,
                globals=globals_,
                frames=(*state.frames, frame),
                line=line,
                steps=0,
            ),
            None,
        )
    lhs, rhs = split
    name, params = _parse_lhs(lhs)
    if not params and _is_lower(name):
        # ``n = 7``: a plain assignment.  It binds rather than
        # prints and takes no input, so its body runs in a frame
        # flagged to assign the result instead of printing it.
        body = _body(rhs, state.defs)
        definition = _Definition("", [], body)
        frame = _Frame(
            fn=definition,
            locals=MappingProxyType({}),
            stmt=0,
            work=((body[0], ()),),
            assign=name,
        )
        return (
            replace(state, frames=(*state.frames, frame), line=line, steps=0),
            None,
        )
    # The name is registered *before* its body is parsed, so a
    # definition can refer to itself: the wiki's truth machine is
    # ``x? = x & x?``, whose body names the very operator being
    # defined, and the parser can only match ``?`` against a pattern
    # it already knows.  The parser reads only registered names (see
    # ``_Parser.operator_patterns``), never a registered body, so the
    # pre-registration entry is a body-less stub; the definition is
    # constructed once its body is known.
    parse_defs = _frozen({**state.defs, name: _Definition(name, params, [])})
    definition = _Definition(name, params, _body(rhs, parse_defs))
    defs = _frozen({**state.defs, name: definition})
    return replace(state, defs=defs, line=line, steps=0), None


def _bind_inputs(
    node: _Node, globals_: Mapping[str, object], inputs: Sequence[_Number]
) -> Mapping[str, object]:
    """Bind every unbound variable in ``node`` from input, in order.

    The spec's example asks for ``a, b, d, c, e`` across two lines,
    which is first-appearance order with bindings persisting, so the
    walk is left-to-right and skips names already bound.  Each read is
    the next explicit value; running out raises :data:`_NeedInput`.
    """
    out = dict(globals_)
    pos = 0
    for name in _free_variables(node):
        if name not in out:
            if pos >= len(inputs):
                raise _NeedInput
            out[name] = inputs[pos]
            pos += 1
    return _frozen(out)


def _step_frame(state: _State, work_limit: int) -> tuple[_State, str | None]:
    """Resolve one node of the innermost frame's current expression."""
    steps = state.steps + 1
    if steps > work_limit:
        raise HaltError(
            "expression exceeded the evaluation budget",
            hint="reduce nesting or repeated evaluation to fit the budget",
        )
    state = replace(state, steps=steps)
    frame = state.frames[-1]
    if not frame.work:
        return _next_statement(state)
    node, done = frame.work[-1]
    # Narrowed on ``node`` itself rather than through a ``kind`` local,
    # so mypy can discriminate the tuple union: binding the tag to a
    # variable first loses the link between it and the node's shape.
    if node[0] == "lit":
        return _resolve(state, frame, node[1])
    if node[0] == "var":
        return _resolve(state, frame, _lookup(frame, node[1], state.globals))
    if node[0] == "ref":
        return _resolve(state, frame, _lookup_function(node[1], state.defs))
    if node[0] == "neg":
        if not done:
            return _descend(state, frame, node[1])
        return _resolve(state, frame, -_as_number(done[0]))
    if node[0] == "ret":
        if not done:
            return _descend(state, frame, node[1])
        # ``$`` exits the function immediately, so the rest of the
        # expression around it is abandoned rather than resumed.
        frame = replace(frame, returned=True, value=done[0], work=())
        return _set_top(state, frame), None
    if node[0] == "bin":
        return _step_binary(state, frame, node, done)
    return _step_call(state, frame, node, done)


def _lookup(frame: _Frame, name: str, globals_: Mapping[str, object]) -> object:
    """Resolve a variable against the frame's locals, then the globals."""
    if name in frame.locals:
        return frame.locals[name]
    if name in globals_:
        return globals_[name]
    raise syntax_error(
        f"unknown variable {name!r}",
        "define the lowercase variable before reading it",
    )


def _lookup_function(name: str, defs: Mapping[str, _Definition]) -> object:
    """Resolve a bare uppercase name to the definition it refers to.

    Only the globals are searched.  A ``ref`` node's name is
    uppercase by construction and every parameter is validated
    lowercase, so a bare name can never be a local; a *parameter*
    holding a function is called as ``c()``, which resolves through
    :func:`_step_call`'s own locals lookup instead.
    """
    if name in defs:
        return defs[name]
    raise syntax_error(
        f"unknown function {name!r}",
        "define this uppercase function before referring to it",
    )


def _descend(state: _State, frame: _Frame, node: _Node) -> tuple[_State, str | None]:
    """Queue ``node`` as the next sub-evaluation of the current one."""
    return _set_top(state, _push_work(frame, node)), None


def _step_binary(
    state: _State, frame: _Frame, node: _Bin, done: tuple[object, ...]
) -> tuple[_State, str | None]:
    """Resolve one stage of a binary operator, short-circuiting & and |.

    ``&`` and ``|`` evaluate their left side first and skip the right
    entirely when it cannot change the answer, which is what makes
    ``x & $0`` a conditional: the ``$`` on the right never runs unless
    ``x`` is truthy.
    """
    op = node[1]
    if not done:
        return _descend(state, frame, node[2])
    if len(done) == 1:
        left = done[0]
        if op == "&" and not _truthy(left):
            return _resolve(state, frame, 0)
        if op == "|" and _truthy(left):
            return _resolve(state, frame, left)
        return _descend(state, frame, node[3])
    left, right = done[0], done[1]
    if op in ("&", "|"):
        # The left operand did not decide the answer, so the value is
        # the right one as evaluated.
        return _resolve(state, frame, right)
    return _resolve(state, frame, _arith(op, _as_number(left), _as_number(right)))


def _step_call(
    state: _State, frame: _Frame, node: _Call, done: tuple[object, ...]
) -> tuple[_State, str | None]:
    """Evaluate a call's arguments, then push the callee's frame."""
    name, args = node[1], node[2]
    if len(done) < len(args):
        return _descend(state, frame, args[len(done)])
    # A name bound to a *value* is a parameter holding a function,
    # which is how the wiki's ``WHILE(x, c)`` calls ``x()``.
    target = frame.locals.get(name)
    definition = target if isinstance(target, _Definition) else state.defs.get(name)
    if definition is None:
        raise syntax_error(
            f"unknown function {name!r}",
            ("define the called function or pass a defined function as the parameter"),
        )
    if len(done) != len(definition.params):
        raise syntax_error(
            f"{definition.name!r} takes {len(definition.params)} "
            f"argument(s), got {len(done)}",
            ("pass exactly the number of arguments declared in the function header"),
        )
    frame = _pop_work(frame)
    pushed = _Frame(
        fn=definition,
        locals=_frozen(dict(zip(definition.params, done, strict=True))),
        stmt=0,
        work=((definition.body[0], ()),),
    )
    return replace(state, frames=(*state.frames[:-1], frame, pushed)), None


def _resolve(state: _State, frame: _Frame, value: object) -> tuple[_State, str | None]:
    """Finish the innermost node, handing ``value`` to its parent."""
    frame = _pop_work(frame)
    frame = replace(frame, value=value)
    if frame.work:
        frame = _append_done(frame, value)
    return _set_top(state, frame), None


def _next_statement(state: _State) -> tuple[_State, str | None]:
    """Move to the frame's next statement, or return from it."""
    frame = state.frames[-1]
    if not frame.returned and frame.stmt + 1 < len(frame.fn.body):
        # Every statement but the last prints, per the wiki's
        # MULTILINE example -- unless it carries a ``$``, which makes
        # it a conditional return rather than a printed value.
        out = None if frame.fn.control[frame.stmt] else _format_value(frame.value)
        stmt = frame.stmt + 1
        frame = replace(frame, stmt=stmt, work=(*frame.work, (frame.fn.body[stmt], ())))
        return _set_top(state, frame), out
    return _pop(state)


def _pop(state: _State) -> tuple[_State, str | None]:
    """Return the frame's value to its caller, printing or assigning it."""
    frame = state.frames[-1]
    value = frame.value
    frames = state.frames[:-1]
    globals_ = (
        state.globals
        if frame.assign is None
        else _frozen({**state.globals, frame.assign: value})
    )
    if not frames:
        out = _format_value(value) if frame.printing else None
        return replace(state, frames=frames, globals=globals_), out
    parent = replace(frames[-1], value=value)
    if parent.work:
        parent = _append_done(parent, value)
    return replace(state, frames=(*frames[:-1], parent), globals=globals_), None


def _format_float(value: float) -> str:
    """Render a float, dropping a trailing ``.0`` from an integral one."""
    return format_integer(int(value)) if value.is_integer() else str(value)


def _truthy(value: object) -> bool:
    """Whether ``value`` is true: every number but zero, and any function."""
    if isinstance(value, _Definition):
        return True
    return _as_number(value) != 0


def _arith(op: str, left: _Number, right: _Number) -> _Number:
    """Apply an operator, rejecting nonfinite and nonreal results."""
    try:
        return _as_number(_raw_arith(op, left, right))
    except OverflowError as exc:
        raise HaltError("arithmetic result exceeds the float range") from exc


def _raw_arith(op: str, left: _Number, right: _Number) -> _Number:
    """Apply one arithmetic operator, keeping integers exact.

    ``op`` is one of the six the parser emits for a ``bin`` node other
    than ``&``/``|``, which short-circuit and never reach here.  The
    parser is the only producer, so ``**`` is the fallthrough rather
    than a tested case followed by an unreachable "unknown operator".
    """
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        if right == 0:
            raise HaltError(
                "division by zero", hint="ensure the divisor is nonzero before dividing"
            )
        if isinstance(left, int) and isinstance(right, int):
            quotient_int, remainder = divmod(left, right)
            if remainder == 0:
                return quotient_int
        quotient = left / right
        # Keep an exact integer where the division is exact, so the
        # unbounded-integer model survives a round trip through ``/``.
        return int(quotient) if quotient.is_integer() else quotient
    if op == "%":
        if right == 0:
            raise HaltError(
                "modulo by zero",
                hint="ensure the divisor is nonzero before taking a remainder",
            )
        return left % right
    if left == 0 and right < 0:
        raise HaltError(
            "zero to a negative power",
            hint="use a nonzero base for a negative exponent",
        )
    return left**right


def run(code: str, io: IO) -> None:
    """Run an APL program, printing the result of every executed line."""
    machine = _Machine(code, io)
    drive(machine)
