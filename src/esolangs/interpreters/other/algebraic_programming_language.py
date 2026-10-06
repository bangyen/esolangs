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
  for ``b`` once.
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

from dataclasses import dataclass

from esolangs._drive import drive
from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO
from esolangs.interpreters.memory import format_integer
from esolangs.interpreters.other._apl_parse import (
    _as_number,
    _Bin,
    _blocks,
    _body,
    _Call,
    _contains_return,
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
from esolangs.interpreters.source_hints import syntax_error


class _Frame:
    """One call in progress: its body, its bindings, and its cursor.

    ``work`` is an explicit stack of (node, resolved-operands) pairs
    standing in for what Python recursion would keep on its own stack, so
    a single ``step()`` resolves one node and returns.  ``stmt`` indexes
    the definition's body, since a multiline function prints every
    statement but its last.

    ``printing`` marks the synthetic frame wrapping an *executed line*,
    whose result goes to STDOUT; ``assign`` names the variable an
    assignment line binds instead.  Both are false/None for an ordinary
    call, whose value simply returns to its caller.
    """

    def __init__(
        self,
        definition: _Definition,
        args: dict[str, object],
        *,
        printing: bool,
        assign: str | None,
    ) -> None:
        self.fn = definition
        self.locals = args
        self.stmt = 0
        self.work: list[tuple[_Node, list[object]]] = []
        self.value: object = 0
        self.returned = False
        self.printing = printing
        self.assign = assign

    def __repr__(self) -> str:
        """Identify the frame by its function and cursor."""
        return f"<frame {self.fn.name} @{self.stmt}>"


@dataclass
class _State:
    """Every changing value in an Algebraic Programming Language run."""

    defs: dict[str, _Definition]
    globals: dict[str, object]
    frames: list[_Frame]
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
        self.lines = _blocks(code)
        self.state = _State({}, {}, [], 0)

    @property
    def defs(self) -> dict[str, _Definition]:
        return self.state.defs

    @property
    def globals(self) -> dict[str, object]:
        return self.state.globals

    @property
    def frames(self) -> list[_Frame]:
        return self.state.frames

    @property
    def line(self) -> int:
        return self.state.line

    @line.setter
    def line(self, value: int) -> None:
        self.state.line = value

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
        return (self.line, *(f.stmt for f in self.frames))

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
            for _, v in sorted(self.globals.items())
        ]

    @property
    def stack(self) -> list[object]:
        """The live call stack, outermost first."""
        return list(self.frames)

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
        by ``id``, which is stable because the parse tree is built once
        and never rewritten.
        """
        return (
            self.line,
            tuple(sorted((k, _value_key(v)) for k, v in self.globals.items())),
            tuple(
                (
                    _value_key(f.fn),
                    f.stmt,
                    tuple(
                        (id(node), tuple(_value_key(v) for v in done))
                        for node, done in f.work
                    ),
                    _value_key(f.value),
                    f.returned,
                    tuple(sorted((k, _value_key(v)) for k, v in f.locals.items())),
                )
                for f in self.frames
            ),
            self.io.position(),
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
            _value_key(frame.fn),
            tuple(sorted((k, _value_key(v)) for k, v in frame.locals.items())),
            self.io.position(),
        )

    def step(self) -> None:
        """Advance the program by one definition, read, or expression node."""
        if self.halted:
            return
        if self.frames:
            self._step_frame(self.frames[-1])
            return
        self._start_line()

    def _start_line(self) -> None:
        """Consume one logical line: define a name, or begin evaluating."""
        text = self.lines[self.line]
        self.line += 1
        self.state.steps = 0
        split = _split_definition(text)
        if split is None:
            node = _Parser(_tokens(text), self.defs).parse()
            self._bind_inputs(node)
            self._push(_Definition("", [], [node]), {}, printing=True)
            return
        lhs, rhs = split
        name, params = _parse_lhs(lhs)
        if not params and _is_lower(name):
            # ``n = 123``: a plain assignment.  It binds rather than
            # prints and takes no input, so its body runs in a frame
            # flagged to assign the result instead of printing it.
            self._push(_Definition("", [], _body(rhs, self.defs)), {}, assign=name)
            return
        # The name is registered *before* its body is parsed, so a
        # definition can refer to itself: the wiki's truth machine is
        # ``x? = x & x?``, whose body names the very operator being
        # defined, and the parser can only match ``?`` against a pattern
        # it already knows.
        definition = _Definition(name, params, [("lit", 0)])
        self.defs[name] = definition
        definition.body = _body(rhs, self.defs)
        definition.control = [_contains_return(node) for node in definition.body]

    def _push(
        self,
        definition: _Definition,
        args: dict[str, object],
        *,
        printing: bool = False,
        assign: str | None = None,
    ) -> None:
        """Push a frame for ``definition`` and queue its first statement."""
        frame = _Frame(definition, args, printing=printing, assign=assign)
        frame.work.append((definition.body[0], []))
        self.frames.append(frame)

    def _bind_inputs(self, node: _Node) -> None:
        """Bind every unbound variable in ``node`` from input, in order.

        The spec's example asks for ``a, b, d, c, e`` across two lines,
        which is first-appearance order with bindings persisting, so the
        walk is left-to-right and skips names already bound.
        """
        for name in _free_variables(node):
            if name not in self.globals:
                self.globals[name] = self._read_number()

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

    def _step_frame(self, frame: _Frame) -> None:
        """Resolve one node of ``frame``'s current expression."""
        self.state.steps += 1
        if self.state.steps > self._WORK_LIMIT:
            raise HaltError(
                "expression exceeded the evaluation budget",
                hint="reduce nesting or repeated evaluation to fit the budget",
            )
        if not frame.work:
            self._advance(frame)
            return
        node, done = frame.work[-1]
        # Narrowed on ``node`` itself rather than through a ``kind`` local,
        # so mypy can discriminate the tuple union: binding the tag to a
        # variable first loses the link between it and the node's shape.
        if node[0] == "lit":
            self._resolve(frame, node[1])
            return
        if node[0] == "var":
            self._resolve(frame, self._lookup(frame, node[1]))
            return
        if node[0] == "ref":
            self._resolve(frame, self._lookup_function(node[1]))
            return
        if node[0] == "neg":
            if not done:
                self._descend(frame, node[1])
            else:
                self._resolve(frame, -_as_number(done[0]))
            return
        if node[0] == "ret":
            if not done:
                self._descend(frame, node[1])
                return
            # ``$`` exits the function immediately, so the rest of the
            # expression around it is abandoned rather than resumed.
            frame.returned = True
            frame.value = done[0]
            frame.work.clear()
            return
        if node[0] == "bin":
            self._step_binary(frame, node, done)
            return
        self._step_call(frame, node, done)

    def _lookup(self, frame: _Frame, name: str) -> object:
        """Resolve a variable against the frame's locals, then the globals."""
        if name in frame.locals:
            return frame.locals[name]
        if name in self.globals:
            return self.globals[name]
        raise syntax_error(
            f"unknown variable {name!r}",
            "define the lowercase variable before reading it",
        )

    def _lookup_function(self, name: str) -> object:
        """Resolve a bare uppercase name to the definition it refers to.

        Only the globals are searched.  A ``ref`` node's name is
        uppercase by construction and every parameter is validated
        lowercase, so a bare name can never be a local; a *parameter*
        holding a function is called as ``c()``, which resolves through
        ``_step_call``'s own locals lookup instead.
        """
        if name in self.defs:
            return self.defs[name]
        raise syntax_error(
            f"unknown function {name!r}",
            "define this uppercase function before referring to it",
        )

    def _descend(self, frame: _Frame, node: _Node) -> None:
        """Queue ``node`` as the next sub-evaluation of the current one."""
        frame.work.append((node, []))

    def _step_binary(self, frame: _Frame, node: _Bin, done: list[object]) -> None:
        """Resolve one stage of a binary operator, short-circuiting & and |.

        ``&`` and ``|`` evaluate their left side first and skip the right
        entirely when it cannot change the answer, which is what makes
        ``x & $0`` a conditional: the ``$`` on the right never runs unless
        ``x`` is truthy.
        """
        op = node[1]
        if not done:
            self._descend(frame, node[2])
            return
        if len(done) == 1:
            left = done[0]
            if op == "&" and not _truthy(left):
                self._resolve(frame, 0)
                return
            if op == "|" and _truthy(left):
                self._resolve(frame, left)
                return
            self._descend(frame, node[3])
            return
        left, right = done[0], done[1]
        if op in ("&", "|"):
            # The left operand did not decide the answer, so the value is
            # the right one as evaluated.
            self._resolve(frame, right)
            return
        self._resolve(frame, _arith(op, _as_number(left), _as_number(right)))

    def _step_call(self, frame: _Frame, node: _Call, done: list[object]) -> None:
        """Evaluate a call's arguments, then push the callee's frame."""
        name, args = node[1], node[2]
        if len(done) < len(args):
            self._descend(frame, args[len(done)])
            return
        # A name bound to a *value* is a parameter holding a function,
        # which is how the wiki's ``WHILE(x, c)`` calls ``x()``.
        target = frame.locals.get(name)
        definition = target if isinstance(target, _Definition) else self.defs.get(name)
        if definition is None:
            raise syntax_error(
                f"unknown function {name!r}",
                (
                    "define the called function or pass a defined function as "
                    "the parameter"
                ),
            )
        if len(done) != len(definition.params):
            raise syntax_error(
                f"{definition.name!r} takes {len(definition.params)} "
                f"argument(s), got {len(done)}",
                (
                    "pass exactly the number of arguments declared in the "
                    "function header"
                ),
            )
        frame.work.pop()
        self._push(definition, dict(zip(definition.params, done, strict=True)))

    def _resolve(self, frame: _Frame, value: object) -> None:
        """Finish the innermost node, handing ``value`` to its parent."""
        frame.work.pop()
        frame.value = value
        if frame.work:
            frame.work[-1][1].append(value)

    def _advance(self, frame: _Frame) -> None:
        """Move to the frame's next statement, or return from it."""
        if not frame.returned and frame.stmt + 1 < len(frame.fn.body):
            # Every statement but the last prints, per the wiki's
            # MULTILINE example -- unless it carries a ``$``, which makes
            # it a conditional return rather than a printed value.
            if not frame.fn.control[frame.stmt]:
                self._print(frame.value)
            frame.stmt += 1
            frame.work.append((frame.fn.body[frame.stmt], []))
            return
        self._pop(frame)

    def _pop(self, frame: _Frame) -> None:
        """Return the frame's value to its caller, printing or assigning it."""
        value = frame.value
        self.frames.pop()
        if frame.assign is not None:
            self.globals[frame.assign] = value
        if not self.frames:
            if frame.printing:
                self._print(value)
            return
        parent = self.frames[-1]
        parent.value = value
        if parent.work:
            parent.work[-1][1].append(value)

    def _print(self, value: object) -> None:
        """Write one result, formatted the way the wiki's examples read."""
        number = _as_number(value)
        text = (
            format_integer(number) if isinstance(number, int) else _format_float(number)
        )
        self.io.print_str(text + "\n")


def _format_float(value: float) -> str:
    """Render a float, dropping a trailing ``.0`` from an integral one."""
    return format_integer(int(value)) if value.is_integer() else str(value)


def _truthy(value: object) -> bool:
    """Whether ``value`` is true: every number but zero, and any function."""
    if isinstance(value, _Definition):
        return True
    return _as_number(value) != 0


def _value_key(value: object) -> tuple[object, ...]:
    """Keep numeric types and retained function identities distinct."""
    if isinstance(value, _Definition):
        return (
            "function",
            id(value),
            value.name,
            tuple(value.params),
            tuple(id(node) for node in value.body),
            tuple(value.control),
        )
    if isinstance(value, float):
        return ("float", value.hex())
    return ("integer", value)


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


if __name__ == "__main__":
    script_main(run)
