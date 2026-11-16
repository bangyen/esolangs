"""Interpreter for Packlang.

Packlang organizes code into *packages*: a package declares variables and
one or more functions, and names the dependencies whose functions it may
call (``Package : IO, myDep { ... } myName;``).  Variables are typed
(``Integer``, ``Char``, ``String``, ``Array(type, length)``) and manipulated
by ``INIT``/``INCR``/``DECR`` rather than assignment; ``Integer(min, max,
under, over)`` bounds a counter and names the values it wraps to.  Control
flow is ``If cond Then { ... }`` and ``While cond Do { ... }``.  ``^`` is
XOR and ``!`` is logical negation, so ``a ^ b`` is a not-equal test and
``!(a ^ b)`` an equality test -- the spelling every wiki example uses.  The
built-in ``IO`` package provides ``charPut(value)`` and ``charGet(var)``.

Every function is stepped, the entry one and its callees alike.  A call
*pushes* a frame rather than running the callee inside the calling
statement, so a statement holding calls is re-entered once per call: each
step runs the leftmost-innermost one that has not returned, and its value
comes back rewritten into the statement's expression as a literal.  So
one command of the innermost function is one ``step()``, every
intermediate state reaches ``snapshot``, and a loop inside a
called function is provable by :func:`esolangs.vm.run_until_halt_or_cycle`
instead of hanging unobserved.  The transition performs no IO itself: it
*requests* a read by returning a flag and the shell takes the character code, also
from a callee.  IO inside a called function works: callees are framed, so
the same shell performs their ``charPut``/``charGet`` in call order.

There is no recursion ceiling.  A program that recurses forever grows the
frame list, not Python's stack; that class revisits no state, so
``esolangs.run``'s wall-clock ``timeout`` handles it, as ``grapheme.py``
records.

Numeric literals default to decimal. ``literal_policy="binary_digits"`` reads
all-0/1 digit strings as binary and every other number as decimal; this makes
the dependency example's ``110000`` mean 48. Generation uses the same policy
for expression literals, type bounds and array lengths.

Input/output:
    ``charGet`` consumes the next character, including newlines.  EOF yields
    newline byte 10, as specified; the wiki cat's ``c ^ 10`` terminator
    therefore remains reachable.

Errors:
    ProgramError: No parameterless entry function; an unbalanced or empty
    program; characters that are no token; a malformed declaration; an unknown
    datatype; an ``Integer`` minimum above its maximum; a duplicate function in
    a package; several parameterless ``main``; ``charPut`` or ``charGet``
    called with the wrong argument count.
    HaltError: An undefined variable or function; an array index outside its
    length; a call to a function whose package is not a dependency; a user
    function called with the wrong argument count.

Decisions:
    * Entry point: the wiki never says what runs.  This interpreter calls the
      parameterless function named ``main``, else the sole parameterless
      function of the last-declared package, which makes PlusOrMinus runnable
      (its ``Integer plusOrMinus : code`` names a package variable rather
      than taking an argument).
    * Dependency visibility is enforced, a rule of this interpreter's own.  A
      package calls its own functions and those of the packages it depends on,
      and nothing else.  The wiki says a dependency may itself have
      dependencies, so the relation is followed transitively.
    * A plain ``Integer`` and a ``Char`` use arithmetic bounds 0..255, wrapping both
      ways, matching ``charPut``'s byte output (the wiki gives ``Integer`` no
      range, and charPut prints ``v % 256``); ``Integer(min, max, under,
      over)`` wraps to the named values instead.  ``INIT`` sets a variable to
      its type's minimum, and an ``Array`` to a row of them, which is what the
      cat example's ``INIT input`` relies on.
    * A function's value is its last evaluated expression statement (the
      trailing ``0;`` in every wiki example); a function that evaluates none
      returns 0.
    * ``charGet`` stores Unicode code points whole (``λ`` is 955), even in
      a byte counter; a later increment applies its named wrap. Input
      encoding is unspecified; this follows the repository's Unicode
      character-input convention, rather than asserting a spec-defined encoding.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from esolangs.exceptions import HaltError
from esolangs.languages.packlang.interpreter._parse import (
    _DECR,
    _INCR,
    _INIT,
    _JUMP,
    _JUMP_UNLESS,
    _PRINT,
    _READ,
    _VALUE,
    _Function,
    _parse,
    _Program,
    _Type,
)
from esolangs.languages.packlang.interpreter._scope import _visible
from esolangs.languages.packlang.interpreter._types import _Expr, _Store
from esolangs.languages.packlang.interpreter._values import (
    _get,
    _int,
    _node,
    _set,
    _truth,
)
from esolangs.languages.packlang.interpreter._workspace import _WORKSPACE_MODEL, _term
from esolangs.languages.packlang.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import IO, _BufferedOutput
from esolangs.runtime.memory import format_integer, repr_value

# There is no recursion ceiling.  A call pushes a frame rather than
# recursing natively, so a runaway program grows the frame list on the
# heap and never touches Python's stack.  That class revisits no state, so
# it is what ``esolangs.run``'s wall-clock ``timeout`` is for -- the same
# reasoning ``grapheme.py`` records.


@dataclass(frozen=True, slots=True)
class _Frame:
    """One call frame: the function, its cursor, and its own variables.

    ``pending`` is the current statement's expression with the calls that
    have already returned rewritten into it as literals, and ``returned``
    the value a just-finished callee is handing back.  Both are what let a
    call inside an expression suspend: the statement is re-entered once per
    call it contains, each time with one more resolved.
    """

    func: _Function
    store: _Store
    pc: int = 0
    result: int = 0
    pending: _Expr | None = None
    returned: int | None = None

    def key(self) -> tuple[object, ...]:
        """Return the frame as a hashable value for :meth:`snapshot`."""
        return (self.func.package, self.func.name, self.pc, self.store, self.result)


#: The active call frames, including suspended expressions and return values.
type _State = tuple[_Frame, ...]


def _evaluate(node: _Expr, store: _Store) -> int:
    """Run the call-free remainder in left-to-right order."""
    pending: list[tuple[str, object]] = []
    while True:
        kind = node[0]
        if kind in ("lit", "done"):
            result = _int(node[1])
        elif kind == "var":
            value = _get(store, str(node[1]))
            if isinstance(value, tuple):
                raise HaltError(
                    f"{node[1]!r} is an array and has no scalar value",
                    hint="index the array to select a scalar element",
                )
            result = _int(value)
        elif kind == "length":
            value = _get(store, str(node[1]))
            if not isinstance(value, tuple):
                raise HaltError(
                    f"{node[1]!r} is not an array",
                    hint="use an array variable for indexing",
                )
            result = len(value)
        elif kind == "xor":
            pending.append(("right", node[2]))
            node = _node(node[1])
            continue
        elif kind == "not":
            pending.append(("not", None))
            node = _node(node[1])
            continue
        elif kind == "apply":
            indexed, node = _array_index(node, store)
            pending.append(("index", indexed))
            continue
        else:
            raise HaltError(f"cannot evaluate {kind!r}")

        while pending:
            operation, operand = pending.pop()
            if operation == "right":
                pending.append(("xor", result))
                node = _node(operand)
                break
            if operation == "xor":
                result = _int(operand) ^ result
            elif operation == "not":
                result = 0 if _truth(result) else 1
            else:
                name, array = _node(operand)
                assert isinstance(array, tuple)
                if not 0 <= result < len(array):
                    raise HaltError(
                        f"index {format_integer(result)} is outside {name!r}",
                        hint=(
                            "keep the index within the bounds stated in the diagnostic"
                        ),
                    )
                result = _int(array[result])
        else:
            return result


def _array_index(
    node: _Expr, store: _Store
) -> tuple[tuple[str, tuple[object, ...]], _Expr]:
    """Resolve the array before evaluating its index."""
    name = str(node[1])
    args = [_node(arg) for arg in _node(node[2])]
    if not any(slot == name for slot, _ in store):
        raise HaltError(f"unresolved call to {name!r}")
    value = _get(store, name)
    if not isinstance(value, tuple):
        raise HaltError(
            f"{name!r} is not an array", hint="use an array variable for indexing"
        )
    if len(args) != 1:
        raise HaltError(
            f"indexing {name!r} takes exactly one index",
            hint="supply exactly one index when accessing an array",
        )
    return (name, value), args[0]


def _pending_call(node: _Expr, store: _Store) -> _Expr | None:
    """Find the leftmost innermost call in evaluation order."""
    pending: list[tuple[_Expr, bool]] = []
    while True:
        kind = node[0]
        if kind == "not":
            node = _node(node[1])
            continue
        if kind == "xor":
            pending.append((_node(node[2]), False))
            node = _node(node[1])
            continue
        if kind == "apply":
            pending.append((node, True))
            pending.extend((_node(arg), False) for arg in reversed(_node(node[2])))
        while pending:
            node, checked = pending.pop()
            if not checked:
                break
            name = str(node[1])
            if not any(slot == name for slot, _ in store):
                return node
        else:
            return None


def _substitute(node: _Expr, target: _Expr, value: int) -> _Expr:
    """Replace a returned call without modifying the shared source tree."""
    pending = [(node, False)]
    rewritten: dict[int, _Expr] = {}
    while pending:
        current, ready = pending.pop()
        if current is target:
            rewritten[id(current)] = ("done", value)
            continue
        kind = current[0]
        if kind in ("not", "xor"):
            children = current[1:]
        elif kind == "apply":
            children = _node(current[2])
        else:
            rewritten[id(current)] = current
            continue
        if ready:
            parts = tuple(rewritten[id(child)] for child in children)
            rewritten[id(current)] = (
                ("apply", current[1], parts) if kind == "apply" else (kind, *parts)
            )
        else:
            pending.append((current, True))
            pending.extend((_node(child), False) for child in children)
    return rewritten[id(node)]


def _expression_key(node: _Expr | None) -> str:
    """Keep the previous snapshot spelling for deeply suspended calls."""
    try:
        return repr_value(node)
    except RecursionError:
        pass
    parts: list[str] = []
    pending: list[tuple[object, bool]] = [(node, False)]
    while pending:
        item, delimiter = pending.pop()
        if delimiter:
            parts.append(str(item))
        elif isinstance(item, tuple):
            parts.append("(")
            pending.append((",)" if len(item) == 1 else ")", True))
            for i in range(len(item) - 1, -1, -1):
                pending.append((item[i], False))
                if i:
                    pending.append((", ", True))
        else:
            parts.append(repr_value(item))
    return "".join(parts)


def _callee(node: _Expr, program: _Program, caller: str) -> _Function:
    """Resolve the function a pending call names, checking visibility."""
    name = str(node[1])
    local = program.functions.get((caller, name))
    if local is not None:
        return local
    named = [func for func in program.functions.values() if func.name == name]
    if not named:
        raise HaltError(
            f"undefined function {name!r}",
            hint="define the function before calling it; check its spelling",
        )
    visible = [func for func in named if _visible(func, caller, program)]
    if not visible:
        raise HaltError(
            f"{caller!r} does not depend on {named[0].package!r}, "
            f"so {name!r} is not in scope",
            hint="declare the package dependency before calling its function",
        )
    if len(visible) != 1:
        raise HaltError(f"ambiguous function {name!r} in {caller!r}")
    return visible[0]


def _entered(func: _Function, values: list[int], program: _Program) -> _Frame:
    """Build the frame a call runs in, binding its arguments."""
    if len(values) != len(func.params):
        raise HaltError(
            f"{func.name!r} takes {len(func.params)} arguments",
            hint="pass the number of arguments declared by the function",
        )
    store = _initial_store(func, program)
    bound = dict(zip(func.params, values, strict=True))
    return _Frame(func, tuple((slot, bound.get(slot, value)) for slot, value in store))


def _initial_store(func: _Function, program: _Program) -> _Store:
    """Build a function's store: the globals it sees, plus its own locals."""
    types = {
        name: kind
        for (package, name), kind in program.globals.items()
        if package == func.package
    }
    types.update(func.locals)
    return tuple((name, kind.zero()) for name, kind in sorted(types.items()))


def _type_of(name: str, func: _Function, program: _Program) -> _Type:
    return func.locals.get(name) or program.globals.get((func.package, name)) or _Type()


def _statement(
    frame: _Frame,
    program: _Program,
    byte: int | None,
    stmt: tuple[object, ...],
) -> tuple[_Frame, str | None, bool]:
    """Return the frame after one statement, any output, and whether to read.

    Pure: it reads the frame and returns a new one, reaching no ``IO``.  A
    read is requested by returning True for the third element, and the
    shell calls back with the byte in ``byte`` -- so the transition stays a
    function of its arguments and the two ports remain the shell's.
    """
    op = stmt[0]
    store = frame.store
    pc = frame.pc + 1
    out: str | None = None
    result = frame.result

    if op == _PRINT:
        value = _evaluate(_node(stmt[1]), store)
        out = chr(value % 256)
    elif op == _READ:
        if byte is None:
            return frame, None, True
        store = _write(store, str(stmt[1]), stmt[2], lambda _old: byte)
    elif op == _INIT:
        kind = _type_of(str(stmt[1]), frame.func, program)
        store = _write(store, str(stmt[1]), stmt[2], lambda _o: kind.low, whole=kind)
    elif op in (_INCR, _DECR):
        step = 1 if op == _INCR else -1
        kind = _type_of(str(stmt[1]), frame.func, program)
        store = _write(store, str(stmt[1]), stmt[2], lambda old: kind.clamp(old + step))
    elif op == _JUMP_UNLESS:
        guard = _evaluate(_node(stmt[1]), store)
        if not _truth(guard):
            pc = _int(stmt[2])
    elif op == _JUMP:
        pc = _int(stmt[1])
    # Every opcode the parser emits has an arm above, so the chain is
    # exhaustive and this last test never falls through.
    elif op == _VALUE:  # pragma: no branch
        result = _evaluate(_node(stmt[1]), store)

    return (
        replace(frame, store=store, pc=pc, result=result, pending=None, returned=None),
        out,
        False,
    )


def _write(
    store: _Store,
    name: str,
    index: object,
    update: Callable[[int], int],
    whole: _Type | None = None,
) -> _Store:
    """Apply ``update`` to a variable or one array element.

    ``whole`` is set by ``INIT``, which resets an entire array rather than
    one element -- the cat example's ``INIT input`` depends on that.
    """
    value = _get(store, name)
    if isinstance(value, tuple):
        if index is None:
            if whole is not None:
                return _set(store, name, whole.zero())
            raise HaltError(
                f"{name!r} is an array and needs an index",
                hint="supply an index when assigning an array element",
            )
        at = _evaluate(_node(index), store)
        if not 0 <= at < len(value):
            raise HaltError(
                f"index {format_integer(at)} is outside {name!r}",
                hint=("keep the index within the bounds stated in the diagnostic"),
            )
        row = list(value)
        row[at] = update(_int(row[at]))
        return _set(store, name, tuple(row))
    if index is not None:
        raise HaltError(
            f"{name!r} is not an array", hint="use an array variable for indexing"
        )
    return _set(store, name, update(_int(value)))


#: Where each statement kind keeps the expression a call can hide in.
#: The three write opcodes carry an array index at slot 2, which may
#: itself be a call; ``_JUMP`` alone carries none.
_EXPR_SLOT = {
    _PRINT: 1,
    _JUMP_UNLESS: 1,
    _VALUE: 1,
    _READ: 2,
    _INIT: 2,
    _INCR: 2,
    _DECR: 2,
}


def _expression_of(stmt: tuple[object, ...]) -> _Expr | None:
    """Return the expression ``stmt`` evaluates, or None if it has none."""
    slot = _EXPR_SLOT.get(str(stmt[0]))
    if slot is None or slot >= len(stmt) or stmt[slot] is None:
        return None
    return _node(stmt[slot])


def _resolved(frame: _Frame) -> tuple[object, ...]:
    """Return the statement to run: the parsed one, or the resolved copy.

    Handing the rewritten *statement* to :func:`_statement` rather than
    rebuilding the function keeps the parsed program untouched -- it is
    shared by every frame and by each lap of a ``While``.
    """
    stmt = frame.func.body[frame.pc]
    if frame.pending is None:
        return stmt
    # A pending call came from this statement's expression, so it has a slot.
    slot = _EXPR_SLOT[str(stmt[0])]
    parts = list(stmt)
    parts[slot] = frame.pending
    return tuple(parts)


def _resolve(frame: _Frame, program: _Program) -> tuple[_Frame, _Frame | None]:
    """Return the updated caller and any callee it needs to enter."""
    expr = _expression_of(frame.func.body[frame.pc])
    if expr is None:
        return frame, None
    working = frame.pending if frame.pending is not None else expr
    package = frame.func.package
    if frame.returned is not None:
        call = _pending_call(working, frame.store)
        # A value is waiting only because a call was found and stepped,
        # so the same search finds it again here.
        if call is not None:  # pragma: no branch
            working = _substitute(working, call, frame.returned)
        frame = replace(frame, returned=None)
    call = _pending_call(working, frame.store)
    frame = replace(frame, pending=working)
    if call is None:
        return frame, None
    func = _callee(call, program, package)
    values = [_evaluate(_node(arg), frame.store) for arg in _node(call[2])]
    return frame, _entered(func, values, program)


def _advance(
    frames: _State, program: _Program, byte: int | None = None
) -> tuple[_State, str | None, bool]:
    """Return immutable call frames, any output, and whether input is needed."""
    if not frames:
        return frames, None, False
    frame = frames[-1]
    if frame.pc >= len(frame.func.body):
        callers = frames[:-1]
        if callers:
            callers = (*callers[:-1], replace(callers[-1], returned=frame.result))
        return callers, None, False
    frame, callee = _resolve(frame, program)
    callers = (*frames[:-1], frame)
    if callee is not None:
        return (*callers, callee), None, False
    result, output, wants_read = _statement(frame, program, byte, _resolved(frame))
    return (*callers[:-1], result), output, wants_read


def _program_key(program: _Program) -> tuple[tuple[object, ...], ...]:
    """Return the parsed program as a hashable, order-canonical key.

    :meth:`_Machine.snapshot` carries this so a repeated state proves a
    loop.  It identifies the whole program -- every function with its
    package, parameters, body, callees, and local types, plus the
    dependency graph and the globals -- and nothing about the run's
    progress.  Every mapping is sorted by name before packing, so the same
    program yields the same key regardless of declaration order.
    """
    return (
        tuple(
            sorted(
                (
                    name,
                    func.package,
                    func.params,
                    func.body,
                    func.uses,
                    tuple(
                        sorted(
                            (slot, *kind.key()) for slot, kind in func.locals.items()
                        )
                    ),
                )
                for name, func in program.functions.items()
            )
        ),
        tuple(sorted(program.dependencies.items())),
        tuple(sorted((key, *kind.key()) for key, kind in program.globals.items())),
    )


# Programs are parsed into a flat statement list per function, so :class:`_Machine`
# steps one statement at a time and :func:`_advance` is a pure transition over an
# immutable state.  The variable store is a tuple of ``(name, value)`` pairs, so
# :meth:`_Machine.snapshot` is hashable as it stands and a repeated state proves a loop.
# :func:`_visible` enforces dependency visibility.
_Image = tuple[_Program, tuple[tuple[object, ...], ...]]


def _prepare_source(code: str, literal_policy: str) -> _Image:
    program = _parse(code, literal_policy)
    return program, _program_key(program)


class _Machine:
    """The run state: a stack of call frames and the parsed program.

    ``step()`` advances the innermost frame by one statement, and a call
    -- wherever it sits in an expression -- *pushes* a frame rather than
    running the callee inside the caller's step.  So every statement of
    every function reaches :meth:`snapshot`, and a loop inside a called
    function is provable by :func:`esolangs.vm.run_until_halt_or_cycle`
    rather than hanging where nothing can see it.
    """

    eof_is_a_value = True

    def __init__(
        self, code: str | _Image, io: IO, *, literal_policy: str = "decimal"
    ) -> None:
        self.io = io
        self._writer = _BufferedOutput()
        self.program, self._program_key = (
            _prepare_source(code, literal_policy) if isinstance(code, str) else code
        )
        self._input_reads = 0
        self._pending_input: int | None = None
        entry = self.program.entry
        self.frames: _State = (_Frame(entry, _initial_store(entry, self.program)),)

    @property
    def frame(self) -> _Frame:
        """The innermost frame: the one ``step`` advances."""
        return self.frames[-1]

    @property
    def halted(self) -> bool:
        """Whether every frame has run out, the entry function last."""
        return not self.frames

    @property
    def ip(self) -> int:
        """The current statement position."""
        return self.frame.pc if self.frames else 0

    @property
    def memory(self) -> list[object]:
        """The addressable cells: the innermost frame's variables, in order.

        An array variable contributes its row, so the list is flat and a
        caller reading it sees the same cells the program writes.
        """
        cells: list[object] = []
        if not self.frames:
            return cells
        for _name, value in self.frame.store:
            if isinstance(value, tuple):
                cells.extend(value)
            else:
                cells.append(value)
        return cells

    @property
    def stack(self) -> list[object]:
        """The suspended callers, innermost last.

        A call is a frame now, so there *is* something to observe: each
        entry is the statement its caller is waiting on.
        """
        return [frame.pc for frame in self.frames[:-1]]

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture live frames and values independently of cycle serialization."""
        cursor = self.io.progress()
        pending = self._pending_input
        return _WORKSPACE_MODEL.capture(
            frames=tuple(
                WorkspaceVariant(
                    "frame",
                    (
                        frame.func.package,
                        frame.func.name,
                        frame.pc,
                        frozenset(
                            (
                                slot,
                                tuple(_int(cell) for cell in value)
                                if isinstance(value, tuple)
                                else _int(value),
                            )
                            for slot, value in frame.store
                        ),
                        frame.result,
                        _term(frame.pending),
                        frame.returned,
                    ),
                )
                for frame in self.frames
            ),
            input_cursor=(
                cursor
                if pending is None
                else WorkspaceVariant("pending_input", (cursor, pending))
            ),
            input_reads=(
                WorkspaceVariant("pending_output", (self._input_reads, accepted))
                if (accepted := self._writer.accepted)
                else self._input_reads
            ),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Every frame's cursor, store and result, plus how far each has got
        # through resolving the calls in its current statement, plus the
        # input position -- a repeat that ignores consumed input is not a
        # real cycle.  ``pending`` is by value: it is rewritten as each call
        # returns, so it is built fresh rather than fixed at parse time.
        boundary = (
            tuple(
                (frame.key(), _expression_key(frame.pending), frame.returned)
                for frame in self.frames
            ),
            self.io.progress(),
            self._input_reads,
            self._program_key,
        )
        if (pending := self._pending_input) is not None:
            return (*boundary, ("pending_input", pending))
        accepted = self._writer.accepted
        return (*boundary, accepted) if accepted else boundary

    def step(self) -> None:
        """Advance the innermost frame, owning the two ports.

        A statement holding calls takes several steps: each pushes a frame
        for the leftmost-innermost call not yet returned, and the value
        comes back rewritten into ``pending`` as a literal.  The statement
        itself runs on the step where none is left.

        Stepping a halted machine is a no-op, not an ``IndexError``:
        ``run_until_halt_or_cycle`` steps once more after the halt to prove
        it stayed there.
        """
        frames, out, wants_read = _advance(self.frames, self.program)
        if wants_read:
            byte = self._pending_input
            if byte is None:
                try:
                    byte = self.io.input_char()
                    self._input_reads += 1
                except EOFError:
                    byte = 10
                self._pending_input = byte
            frames, out, _ = _advance(self.frames, self.program, byte)
            self._pending_input = None
        if out is not None:
            self._write_char(out)
        self.frames = frames

    def _write_char(self, char: str) -> None:
        self._writer.write(self.io, char, first=lambda: self.io.print_char(char))


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Parse once under the selected literal policy."""
    if not isinstance(source, str):
        raise TypeError("Packlang machines require text source")
    if options.keys() - {"literal_policy"}:
        raise TypeError("Packlang machines accept only literal_policy")
    image = _prepare_source(
        source, literal_policy=options.get("literal_policy", "decimal")
    )
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(
    code: str | _Image, io: IO, *, literal_policy: str = "decimal"
) -> CompletionReport:
    """Run a Packlang program to completion."""
    machine = _Machine(code, io, literal_policy=literal_policy)
    return drive(machine, policy=CAPABILITIES.completion)


def run(code: str, io: IO, *, literal_policy: str = "decimal") -> None:
    """Run a Packlang program to completion."""
    _execute(code, io, literal_policy=literal_policy)
