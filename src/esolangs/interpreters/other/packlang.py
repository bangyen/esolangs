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

Programs are parsed into a flat statement list per function, so
:class:`_Machine` steps one statement at a time and :func:`_advance` is a
pure transition over an immutable state.  The variable store is a tuple of
``(name, value)`` pairs, so :meth:`_Machine.snapshot` is hashable as it
stands and a repeated state proves a loop.

Every function is stepped, the entry one and its callees alike.  A call
*pushes* a frame rather than running the callee inside the calling
statement, so a statement holding calls is re-entered once per call: each
step runs the leftmost-innermost one that has not returned, and its value
comes back rewritten into the statement's expression as a literal.  So
one command of whichever function is innermost is one ``step()``, every
intermediate state reaches :meth:`_Machine.snapshot`, and a loop inside a
called function is provable by
:func:`esolangs.vm.run_until_halt_or_cycle` rather than hanging where
nothing can observe it.  The transition still performs no IO itself: it
*requests* a read by returning a flag and the shell takes the byte, which
is now reachable from a callee as well.

There is therefore no recursion ceiling.  A program that recurses forever
grows the frame list rather than Python's stack; that class revisits no
state, so it is what ``esolangs.run``'s wall-clock ``timeout`` is for,
exactly as ``grapheme.py`` records.

Numeric literals default to decimal. ``literal_policy="binary_digits"`` reads
all-0/1 digit strings as binary and every other number as decimal; this makes
the dependency example's ``110000`` mean 48. Generation uses the same policy
for expression literals, type bounds and array lengths.

Further decisions for gaps the wiki leaves open:

* **Entry point.**  The wiki never says what runs.  This interpreter calls
  the parameterless function named ``main``, else the sole parameterless
  function of the last-declared package -- which is what makes
  PlusOrMinus runnable, its ``Integer plusOrMinus : code`` naming a
  package variable rather than taking an argument.  A program with no
  such function raises :class:`ValueError`, as does an unbalanced or
  empty program, a malformed declaration, or a call with the wrong
  argument count.
* **EOF.** ``charGet`` consumes the next character, including newlines.
  Exhausted input yields newline byte 10, as specified; the wiki cat's
  ``c ^ 10`` terminator therefore remains reachable.
* **Invalid runtime operations** raise
  :class:`~esolangs.exceptions.HaltError`: an undefined variable or
  function, an array index outside its length, and one rule of this
  interpreter's own -- **dependency visibility is enforced**
  (:func:`_visible`).  A package calls its own functions and those of the
  packages it depends on, and nothing else.  The wiki says a dependency
  may itself have dependencies, so the relation is followed transitively.
* **IO inside a called function works.**  It was refused, on the
  rationale that a call was evaluated inside a statement and so gave the
  shell no point at which to perform its ports.  Framing calls removed
  that rationale: a callee's statements are stepped like any other, so
  the same shell performs its ``charPut``/``charGet`` in call order.
* **Bounds.**  A plain ``Integer`` and a ``Char`` are bytes, 0..255 and
  wrapping both ways, matching ``charPut``'s byte output (the wiki gives
  ``Integer`` no range, and charPut prints ``v % 256``);
  ``Integer(min, max, under, over)`` wraps to the named values instead.
  ``INIT`` sets a variable to its type's minimum, and an ``Array`` to a
  row of them, which is what the cat example's ``INIT input`` relies on.
* **A function's value** is its last evaluated expression statement (the
  trailing ``0;`` in every wiki example); a function that evaluates none
  returns 0.
"""

from collections.abc import Callable, Iterable

from esolangs._drive import drive
from esolangs._suggest import Correction, keyword_correction
from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO
from esolangs.interpreters.other._packlang_parse import (
    _DECR,
    _INCR,
    _INIT,
    _JUMP,
    _JUMP_UNLESS,
    _PRINT,
    _READ,
    _VALUE,
    _Expr,
    _Function,
    _parse,
    _Program,
    _Type,
)
from esolangs.interpreters.other._packlang_scope import _visible
from esolangs.interpreters.other._packlang_values import (
    _get,
    _int,
    _node,
    _set,
    _truth,
)

# There is no recursion ceiling.  A call pushes a frame rather than
# recursing natively, so a runaway program grows the frame list on the
# heap and never touches Python's stack.  That class revisits no state, so
# it is what ``esolangs.run``'s wall-clock ``timeout`` is for -- the same
# reasoning ``grapheme.py`` and ``function_x_y.py`` record.


#: One variable: its name and its value.  Arrays hold a tuple of values;
#: scalars a single int.
type _Slot = tuple[str, object]
type _Store = tuple[_Slot, ...]

#: The whole run state as a value: the statement cursor, the variable
#: store, and the function's value so far.  The parsed program is constant
#: for a run, so it is not part of the state; :class:`_Frame` is this tuple
#: with names, and :meth:`_Frame.key` is the tuple itself.
type _State = tuple[int, _Store, int]


class _Frame:
    """One call frame: the function, its cursor, and its own variables.

    ``pending`` is the current statement's expression with the calls that
    have already returned rewritten into it as literals, and ``returned``
    the value a just-finished callee is handing back.  Both are what let a
    call inside an expression suspend: the statement is re-entered once per
    call it contains, each time with one more resolved.
    """

    __slots__ = ("func", "pc", "pending", "result", "returned", "store")

    def __init__(self, func: _Function, store: _Store, pc: int = 0) -> None:
        self.func = func
        self.store = store
        self.pc = pc
        self.result = 0
        self.pending: _Expr | None = None
        self.returned: int | None = None

    def key(self) -> tuple[object, ...]:
        """Return the frame as a hashable value for :meth:`snapshot`."""
        return (self.func.package, self.func.name, self.pc, self.store, self.result)


def _evaluate(node: _Expr, store: _Store, program: _Program, caller: str) -> int:
    """Return the value of an expression, which contains no unresolved call.

    Pure with respect to the store, and no longer recursive through a
    call: ``_Machine.step`` pushes a frame for every function call and
    rewrites its value in as a ``val`` node, so what reaches here is the
    call-free remainder.
    """
    kind = node[0]
    if kind in ("lit", "done"):
        return _int(node[1])
    if kind == "var":
        value = _get(store, str(node[1]))
        if isinstance(value, tuple):
            raise HaltError(
                f"{node[1]!r} is an array and has no scalar value",
                hint="index the array to select a scalar element",
            )
        return _int(value)
    if kind == "length":
        value = _get(store, str(node[1]))
        if not isinstance(value, tuple):
            raise HaltError(
                f"{node[1]!r} is not an array",
                hint="use an array variable for indexing",
            )
        return len(value)
    if kind == "xor":
        left = _evaluate(_node(node[1]), store, program, caller)
        right = _evaluate(_node(node[2]), store, program, caller)
        return left ^ right
    if kind == "not":
        value = _evaluate(_node(node[1]), store, program, caller)
        return 0 if _truth(value) else 1
    if kind == "apply":
        return _apply(node, store, program, caller)
    raise HaltError(f"cannot evaluate {kind!r}")


def _apply(node: _Expr, store: _Store, program: _Program, caller: str) -> int:
    """Evaluate an array index.  A function call never reaches here.

    Indexing and calling look alike in the grammar, and the store decides
    which one a name is.  ``_Machine.step`` resolves every *call* into a
    ``done`` node before evaluating, so what survives is the index case.
    """
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
    index = _evaluate(args[0], store, program, caller)
    if not 0 <= index < len(value):
        raise HaltError(
            f"index {index} is outside {name!r}",
            hint="keep the index within the bounds stated in the diagnostic",
        )
    return _int(value[index])


def _pending_call(
    node: _Expr, store: _Store, program: _Program, caller: str
) -> _Expr | None:
    """Return the call :func:`_evaluate` would reach first, or None.

    Leftmost-innermost, which is ``_evaluate``'s own order: a call's own
    arguments are searched before the call, and ``xor``'s left operand
    before its right.  Keeping that order is what preserves which
    ``HaltError`` fires first and the order of a callee's output.

    An ``apply`` over an array *name* is an index, not a call, so it is
    searched but never returned -- indexing has no body to step.
    """
    kind = node[0]
    if kind in ("lit", "done", "var", "length"):
        return None
    if kind == "not":
        return _pending_call(_node(node[1]), store, program, caller)
    if kind == "xor":
        return _pending_call(_node(node[1]), store, program, caller) or _pending_call(
            _node(node[2]), store, program, caller
        )
    if kind != "apply":
        return None
    for arg in _node(node[2]):
        found = _pending_call(_node(arg), store, program, caller)
        if found is not None:
            return found
    name = str(node[1])
    if any(slot == name for slot, _ in store):
        return None  # an array index, evaluated in place
    return node


def _substitute(node: _Expr, target: _Expr, value: int) -> _Expr:
    """Return ``node`` with ``target`` replaced by the literal ``value``.

    A rewritten *copy*: the parsed program is shared by every frame and by
    each lap of a ``While``, so writing into it would corrupt the next
    reader's view of the statement.
    """
    if node is target:
        return ("done", value)
    kind = node[0]
    if kind in ("lit", "done", "var", "length"):
        return node
    if kind == "not":
        return ("not", _substitute(_node(node[1]), target, value))
    if kind == "xor":
        return (
            "xor",
            _substitute(_node(node[1]), target, value),
            _substitute(_node(node[2]), target, value),
        )
    if kind != "apply":
        return node
    return (
        "apply",
        node[1],
        tuple(_substitute(_node(arg), target, value) for arg in _node(node[2])),
    )


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
    return func.locals.get(name) or program.types.get((func.package, name)) or _Type()


def _advance(
    frame: _Frame,
    program: _Program,
    byte: int | None,
    stmt: tuple[object, ...] | None = None,
) -> tuple[_Frame, str | None, bool]:
    """Return the frame after one statement, any output, and whether to read.

    Pure: it reads the frame and returns a new one, reaching no ``IO``.  A
    read is requested by returning True for the third element, and the
    shell calls back with the byte in ``byte`` -- so the transition stays a
    function of its arguments and the two ports remain the shell's.
    """
    if stmt is None:  # pragma: no cover - both call sites pass `prepared`
        stmt = frame.func.body[frame.pc]
    op = stmt[0]
    store = frame.store
    # Name resolution is done from the running function's own package.
    package = frame.func.package
    pc = frame.pc + 1
    out: str | None = None
    result = frame.result

    if op == _PRINT:
        value = _evaluate(_node(stmt[1]), store, program, package)
        out = chr(value % 256)
    elif op == _READ:
        if byte is None:
            return frame, None, True
        store = _write(
            store,
            program,
            str(stmt[1]),
            stmt[2],
            lambda _old: byte,
            package,
        )
    elif op == _INIT:
        kind = _type_of(str(stmt[1]), frame.func, program)
        store = _write(
            store,
            program,
            str(stmt[1]),
            stmt[2],
            lambda _o: kind.low,
            package,
            whole=kind,
        )
    elif op in (_INCR, _DECR):
        step = 1 if op == _INCR else -1
        kind = _type_of(str(stmt[1]), frame.func, program)
        store = _write(
            store,
            program,
            str(stmt[1]),
            stmt[2],
            lambda old: kind.clamp(old + step),
            package,
        )
    elif op == _JUMP_UNLESS:
        guard = _evaluate(_node(stmt[1]), store, program, package)
        if not _truth(guard):
            pc = _int(stmt[2])
    elif op == _JUMP:
        pc = _int(stmt[1])
    # Every opcode the parser emits has an arm above, so the chain is
    # exhaustive and this last test never falls through.
    elif op == _VALUE:  # pragma: no branch
        result = _evaluate(_node(stmt[1]), store, program, package)

    new = _Frame(frame.func, store, pc)
    new.result = result
    return new, out, False


def _write(
    store: _Store,
    program: _Program,
    name: str,
    index: object,
    update: Callable[[int], int],
    caller: str,
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
        at = _evaluate(_node(index), store, program, caller)
        if not 0 <= at < len(value):
            raise HaltError(
                f"index {at} is outside {name!r}",
                hint="keep the index within the bounds stated in the diagnostic",
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

    Handing the rewritten *statement* to :func:`_advance` rather than
    rebuilding the function keeps the parsed program untouched -- it is
    shared by every frame and by each lap of a ``While``.
    """
    stmt = frame.func.body[frame.pc]
    if frame.pending is None:
        return stmt
    slot = _EXPR_SLOT.get(str(stmt[0]))
    if slot is None:  # pragma: no cover - only _JUMP lacks a slot, and a
        # jump never has a pending call, so the check above returns first
        return stmt
    parts = list(stmt)
    parts[slot] = frame.pending
    return tuple(parts)


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

    def __init__(self, code: str, io: IO, *, literal_policy: str = "decimal") -> None:
        self.io = io
        self.program = _parse(code, literal_policy)
        self._input_reads = 0
        self._program_key = (
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
                                (
                                    slot,
                                    kind.low,
                                    kind.high,
                                    kind.under,
                                    kind.over,
                                    kind.length,
                                )
                                for slot, kind in func.locals.items()
                            )
                        ),
                    )
                    for name, func in self.program.functions.items()
                )
            ),
            tuple(sorted(self.program.dependencies.items())),
            tuple(
                sorted(
                    (key, kind.low, kind.high, kind.under, kind.over, kind.length)
                    for key, kind in self.program.globals.items()
                )
            ),
        )
        entry = self.program.entry
        # _parse raises when a program has no entry, so this cannot be None.
        if entry is None:
            raise AssertionError("entry is not None")
        self.frames = [_Frame(entry, _initial_store(entry, self.program))]

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
            cells.extend(value) if isinstance(value, tuple) else cells.append(value)
        return cells

    @property
    def stack(self) -> list[object]:
        """The suspended callers, innermost last.

        A call is a frame now, so there *is* something to observe: each
        entry is the statement its caller is waiting on.
        """
        return [frame.pc for frame in self.frames[:-1]]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Every frame's cursor, store and result, plus how far each has got
        # through resolving the calls in its current statement, plus the
        # input position -- a repeat that ignores consumed input is not a
        # real cycle.  ``pending`` is by value: it is rewritten as each call
        # returns, so it is built fresh rather than fixed at parse time.
        return (
            tuple(
                (frame.key(), repr(frame.pending), frame.returned)
                for frame in self.frames
            ),
            self.io.position(),
            self._input_reads,
            self._program_key,
        )

    def step(self) -> None:
        """Advance the innermost frame, owning the two ports.

        A statement holding calls takes more than one step: each step
        pushes a frame for the leftmost-innermost call that has not
        returned, and the value comes back rewritten into ``pending`` as a
        literal.  The statement itself runs on the step where none is
        left.

        Stepping a halted machine is a no-op rather than an
        ``IndexError``: ``run_until_halt_or_cycle`` steps once more after
        the halt to prove it stayed there.
        """
        if self.halted:
            return
        frame = self.frame
        if frame.pc >= len(frame.func.body):
            self._finish(frame)
            return
        if self._resolve(frame):
            return
        prepared = _resolved(frame)
        result, out, wants_read = _advance(frame, self.program, None, prepared)
        if wants_read:
            # Packlang alone defines exhausted input as newline.  Keep that
            # exception here rather than changing the shared input port.
            try:
                byte = self.io.input_char()
                self._input_reads += 1
            except EOFError:
                byte = 10
            result, out, _ = _advance(frame, self.program, byte, prepared)
        result.pending = None
        result.returned = None
        self.frames[-1] = result
        if out is not None:
            self.io.print_char(out)

    def _resolve(self, frame: _Frame) -> bool:
        """Push a frame for the next unresolved call, if the statement has one.

        Returns whether this step was spent starting a call, in which case
        the statement stays put and is re-entered once the value is in.
        """
        expr = _expression_of(frame.func.body[frame.pc])
        if expr is None:
            return False
        working = frame.pending if frame.pending is not None else expr
        package = frame.func.package
        if frame.returned is not None:
            call = _pending_call(working, frame.store, self.program, package)
            # A value is waiting only because a call was found and stepped,
            # so the same search finds it again here.
            if call is not None:  # pragma: no branch
                working = _substitute(working, call, frame.returned)
            frame.returned = None
        call = _pending_call(working, frame.store, self.program, package)
        if call is None:
            frame.pending = working
            return False
        frame.pending = working
        func = _callee(call, self.program, package)
        values = [
            _evaluate(_node(arg), frame.store, self.program, package)
            for arg in _node(call[2])
        ]
        self.frames.append(_entered(func, values, self.program))
        return True

    def _finish(self, frame: _Frame) -> None:
        """Pop a finished frame, delivering its value to the caller."""
        self.frames.pop()
        if self.frames:
            self.frames[-1].returned = frame.result


def run(code: str, io: IO, *, literal_policy: str = "decimal") -> None:
    """Run a Packlang program to completion."""
    machine = _Machine(code, io, literal_policy=literal_policy)
    drive(machine)


if __name__ == "__main__":
    script_main(run)


def suggest_corrections(source: str) -> tuple[Correction, ...]:
    """Return edits only where Packlang's parser requires a keyword."""
    from esolangs.interpreters.other._packlang_lex import (
        _TOKEN,
        _strip_comments,
        _tokenize,
    )
    from esolangs.interpreters.other._packlang_parse import (
        _DATATYPES,
        _parse_packages,
        _Parser,
        _Type,
    )

    masked = _strip_comments(source, preserve_positions=True)
    tokens = _tokenize(masked)
    positions = [match.start() for match in _TOKEN.finditer(masked)]
    corrections: list[Correction] = []

    class PreviewParser(_Parser):
        _speculating = False

        def correct(self, vocabulary: Iterable[str]) -> None:
            word = self.peek()
            if word is None or self._speculating:
                return
            correction = keyword_correction(word, positions[self.pos], vocabulary)
            if correction is not None:
                self.tokens[self.pos] = correction.after
                corrections.append(correction)

        def package_kind(self) -> str:
            self.correct(("Package", "Dependency"))
            return super().package_kind()

        def parse_type(self) -> _Type:
            self.correct(_DATATYPES)
            return super().parse_type()

        def expect(self, word: str) -> None:
            if word in ("Then", "Do"):
                self.correct((word,))
            super().expect(word)

        def is_declaration(self) -> bool:
            # Array(Integer, n) can also be a call; speculative parsing
            # must not rewrite identifiers in its arguments.
            previous = self._speculating
            self._speculating = True
            try:
                return super().is_declaration()
            finally:
                self._speculating = previous

    _parse_packages(PreviewParser(tokens))
    return tuple(sorted(corrections, key=lambda correction: correction.start))
