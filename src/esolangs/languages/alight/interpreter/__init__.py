"""Interpreter for Alight.

A two-dimensional language whose commands are words, not single characters.
The pointer starts at ``begin`` -- which may be written forwards, backwards,
up, or down, and that spelling picks the heading -- and walks the grid one
cell at a time, accumulating characters into a command until a ``;``
terminates it.  ``turn`` pivots *at that semicolon's cell* and the next
command begins one cell beyond it in the new heading; the program stops when
it reaches ``end`` travelling in its current direction.

Values are exact rationals, homogeneous lists, and ``nil``/``eof``/``left``/
``right``. Lists index from 0.5. Functions use ``func name{a, b}`` headers,
return via ``end <value>``, and have separate variable namespaces. Each
``inp`` reads one Unicode character; each ``out`` writes one.  ``out x``
names a variable, as ``inp x`` does: the wiki writes ``<expr>`` only for
``set``/``skip``/``turn``/``wait``.

The wiki has conflicting prose and examples; this interpreter follows the
examples for operator order and list mutation. The profile choices follow.
Structurally malformed programs raise :class:`ValueError`; invalid runtime
operations raise :class:`~esolangs.exceptions.HaltError`.

* **Operator order.**  The prose says operators are postfix, but every
  example on the page is infix -- ``turn c = eof``, ``set x len{l}-0.5``,
  ``skip sign{x} > 0``.  This repository retains infix syntax for existing
  programs and generators as a spec deviation, applied strictly left to
  right with no precedence and no grouping:
  ``a+b*c`` is ``(a+b)*c``.  The unary ``!`` appears in no example and is taken
  as prefix, the only reading that does not need an operand it lacks.
* **Three-argument ``at`` sets in place** by default (``list_update``).
  The prose says it "return[s] a copy of the list with that point set to
  the value", but the Reversed Cat example runs ``at{l, len{l}-0.5, c};``
  as a bare command and discards the result, so it reverses its input only
  in place.  In place, lists are references: ``set m l`` aliases, and a
  callee can mutate a list argument.  ``list_update="copy"`` follows the
  prose.  Bare calls run for their effect, values discarded.  ``len``'s
  pad count, "a positive integer" in the prose, may also be 0 (no pad).
* **EOF.**  ``inp`` past the end of input stores ``eof``, which is what the
  cat examples' ``c = eof`` guard tests.  An empty line supplies its newline character.
* **Off-grid walking.**  Walking off the grid mid-command is a ``HaltError``.
  Walking off it having just completed ``end`` is a *halt*: both cat
  examples end their program at a grid edge with no trailing ``;``, so an
  edge terminates a command the way a semicolon does.
* **Malformed programs** -- no ``begin``, an unparsable command, an
  unterminated string or bracket -- raise ``ValueError``.  A program is
  scanned only as it walks, so an unreachable cell is never parsed.
* **Invalid runtime operations** -- an undeclared variable, a redeclared
  one, division by zero, a non-integral or out-of-range list index, a type
  mismatch, ``out`` of a value that is not a character number, a guard that
  is not ``left``/``right``, and an unknown function -- raise
  ``HaltError``.  There is no call-depth cap: a call pushes a walker, so
  runaway recursion grows the heap rather than Python's stack, and that
  class is the wall-clock ``timeout``'s to catch.
* **``wait`` is a nop.**  Its argument is evaluated (so an error in it still
  fires) and discarded: a real sleep is unobservable through this repo's I/O
  and would hang the suite.
* **Multiple ``begin``s.**  The first in row-major order wins; the rest are
  ordinary grid text, which is what the Evil Hack already makes of any
  overlap.
* **No step or call-depth cap.**  Calls push heap walkers. Complete snapshots
  prove cycles inside callers and callees; nonperiodic growth is left to
  ``esolangs.run``'s wall-clock timeout.

:func:`_advance` is the pure transition: it takes the whole state and the
one input character a step needs -- raising :class:`_NeedInputError` when
the shell has not read it yet -- and returns the next state and any
character an ``out`` writes.  It edits nothing it is handed: the walker
stack is copied, the innermost frame takes a private ``vars`` copy, and an
in-place ``at`` rebuilds the list and rebinds every alias of it rather than
writing through the shared reference.  :class:`_Machine` is the shell that
reads the input and writes the output.

"""

from fractions import Fraction
from typing import Literal, TypeGuard, cast

from esolangs.exceptions import HaltError
from esolangs.languages.alight.interpreter._dialect import (
    expression_syntax as validate_expression_syntax,
)
from esolangs.languages.alight.interpreter._dialect import (
    list_update as validate_list_update,
)
from esolangs.languages.alight.interpreter._hints import Hint
from esolangs.languages.alight.interpreter._parse import (
    _RESERVED,
    _SPECIALS,
    _command_expr,
    _Expr,
    _first_call_or_none,
    _parse_number,
    _Parser,
    _replace_first,
    _Special,
    _Value,
)
from esolangs.languages.alight.interpreter._state import _equal, _freeze
from esolangs.languages.alight.interpreter._walk import (
    _find,
    _find_func,
    _grid,
    _Heading,
    _scan,
    _turned,
)
from esolangs.runtime._drive import drive
from esolangs.runtime.io import IO
from esolangs.runtime.memory import parse_integer
from esolangs.runtime.source_hints import keyword_hint, syntax_error

#: The four functions the language supplies.  Everything else a call
#: names is a ``func`` on the grid, which ``step`` runs by pushing a
#: walker rather than by evaluating it in place.
_BUILTINS = ("at", "len", "trunc", "sign")


class _Walker:
    """One walk in progress: where it is, what it can see, and its call.

    A call is a *separate walk* with its own pointer and namespace, which
    is what makes the Evil Hack -- a function's code sharing cells with
    the caller's -- need nothing special: whoever is walking reads the
    cell in their own direction.

    ``pending`` is the current command's expression with the calls that
    have already returned rewritten into it as literals, and ``returned``
    the value a just-finished callee is handing back.  Both are what let a
    call inside an expression suspend: the command is re-entered once per
    call it contains, each time with one more resolved.
    """

    __slots__ = ("col", "heading", "pending", "returned", "row", "vars")

    def __init__(
        self,
        row: int,
        col: int,
        heading: tuple[int, int],
        variables: dict[str, "_Value"],
    ) -> None:
        self.row = row
        self.col = col
        self.heading = heading
        self.vars = variables
        self.pending: _Expr | None = None
        self.returned: _Value | None = None

    def key(self) -> tuple[object, ...]:
        """Return the walker fields for the shared snapshot graph."""
        return (
            self.row,
            self.col,
            self.heading,
            self.vars,
            self.pending,
            self.returned,
        )


#: One instant of a walk: ``(row, col, heading, vars)`` -- where the pointer
#: is, which way it is going, and the frame it is going there with.  The grid
#: is not in it: no command writes to the program, so it is a constant of the
#: run rather than state, and holding it here would make every snapshot carry
#: a copy of the source.
#:
#: ``vars`` is frozen to an alias-preserving graph by :func:`_freeze` before a snapshot
#: stores it because lists can be aliased. A live reference would let a later
#: command mutate a snapshot the cycle detector had already banked.
type _State = tuple[int, int, _Heading, tuple[object, ...]]


def _truth(value: _Value) -> bool:
    """Return a guard's boolean, which only ``left``/``right`` may be.

    The wiki gives booleans exactly two values and no truthiness rule for
    anything else, so a number or a list in a guard is an invalid operation
    rather than a silent coercion.
    """
    if value == "left":
        return True
    if value == "right":
        return False
    raise Hint.BOOLEAN_GUARD.halt("guard is not a boolean")


def _boolean(flag: bool) -> _Special:  # noqa: FBT001 - a conversion, not a mode
    """Return the special value for a Python boolean: ``left`` or ``right``.

    The boolean trap the lint guards against is a *mode selector* -- an
    argument the caller has to look up to read.  Here the argument is the
    datum being converted, so naming it at each call site would only repeat
    the function's own name.
    """
    return "left" if flag else "right"


def _is_num(value: _Value) -> TypeGuard[Fraction | int]:
    """Whether a value is a number.

    A ``TypeGuard`` rather than a plain ``bool`` so that a caller's branch
    narrows: every arithmetic path below tests this first, and without the
    narrowing each one needed an ``assert isinstance`` afterwards purely to
    restate what the test had already established.
    """
    return isinstance(value, Fraction | int) and not isinstance(value, bool)


def _compare(op: str, left: _Value, right: _Value) -> _Special:
    """Compare two values, returning ``left``/``right``.

    ``=`` compares any two values -- objects of different types are unequal
    rather than an error, which is what lets ``c = eof`` be asked of a
    character.  ``<`` and ``>`` are false on anything but two numbers, per
    the wiki.
    """
    if op == "=":
        if _is_num(left) != _is_num(right):
            return "right"
        return _boolean(_equal(left, right))
    if not (_is_num(left) and _is_num(right)):
        return "right"
    return _boolean(left < right if op == "<" else left > right)


def _list_value(values: list[_Value]) -> list[_Value]:
    """Validate homogeneous list elements; specials belong to either kind."""
    kinds = {isinstance(value, list) for value in values if not isinstance(value, str)}
    if len(kinds) > 1:
        raise HaltError("list contains the wrong type of value")
    return values


def _arith(op: str, left: _Value, right: _Value) -> _Value:
    """Apply an arithmetic operator, including the list forms.

    ``+`` concatenates two lists and ``*`` repeats one by a count, which is
    how the wiki defines them; every other combination of a list with a
    number is a type error.
    """
    if isinstance(left, list) and isinstance(right, list):
        if op != "+":
            raise Hint.OPERAND_TYPES.halt(f"cannot apply {op!r} to two lists")
        return _list_value([*left, *right])
    if isinstance(left, list):
        return _repeat(op, left, right)
    if isinstance(right, list):
        # Repetition is commutative in the spelling: ``3 * "ab"`` and
        # ``"ab" * 3`` are the same list.
        return _repeat(op, right, left)
    if not (_is_num(left) and _is_num(right)):
        specials = ", ".join(value for value in (left, right) if isinstance(value, str))
        raise Hint.OPERAND_TYPES.halt(
            f"cannot apply {op!r} to these values: {specials}"
        )
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if right == 0:
        raise Hint.DIVISOR.halt("division by zero")
    return Fraction(left) / right


def _repeat(op: str, seq: list[_Value], count: _Value) -> _Value:
    """Repeat a list by a count, the only list-and-number operation there is."""
    if op != "*" or not _is_num(count):
        raise Hint.OPERAND_TYPES.halt(f"cannot apply {op!r} to a list and a scalar")
    if count != int(count) or count < 0:
        raise Hint.REPEAT_COUNT.halt("list repeat count is not a whole number")
    return seq * int(count)


def _logic(op: str, left: _Value, right: _Value) -> _Special:
    """Apply a logic operator to two booleans."""
    a, b = _truth(left), _truth(right)
    if op == "&":
        return _boolean(a and b)
    if op == "|":
        return _boolean(a or b)
    return _boolean(a != b)


def _index(value: _Value) -> int:
    """Turn an Alight list index into a Python one.

    Indices are ``0.5 + k``; anything else is an error, which is the
    language's one genuinely strange rule and the reason this is a function
    rather than an inline ``int(i)``.
    """
    if not _is_num(value):
        raise Hint.NUMERIC_INDEX.halt(f"list index is not a number: {value!r}")
    slot = value - Fraction(1, 2)
    if slot != int(slot) or slot < 0:
        raise Hint.INDEX_FORM.halt(f"list index is not 0.5 + k: {value!r}")
    return int(slot)


#: Sentinels the pure layer and the shell pass each other.  ``_MISSING`` is
#: the value a step passes for input before the shell has read a character.
_MISSING: object = object()


class _NeedInputError(Exception):
    """Ask the shell for the one input character an ``inp`` command needs."""


class _Core:
    """The pure semantics of one Alight instant: grid and walks in progress.

    ``_command`` executes exactly one command of the innermost walk and
    returns the character an ``out`` writes (or ``None``); the one input an
    ``inp`` command needs is raised as :class:`_NeedInputError` for the shell to
    answer.  It does no I/O.  A function call *pushes* a walker rather than
    running the callee inside the step that made it, so every command of
    every function reaches ``snapshot`` and a loop inside a called function
    is provable by :func:`esolangs.vm.run_until_halt_or_cycle`.
    """

    def __init__(
        self,
        grid: list[str],
        expression_syntax: str,
        list_update: str,
        walkers: list[_Walker],
        *,
        halted: bool = False,
    ) -> None:
        self.grid = grid
        self.expression_syntax = expression_syntax
        self.list_update = list_update
        self.walkers = walkers
        self.halted = halted
        self._input: _Value | object = _MISSING
        self._output: int | None = None

    @property
    def walker(self) -> _Walker:
        """The innermost walk: the one ``_command`` advances."""
        return self.walkers[-1]

    @property
    def row(self) -> int:
        return self.walker.row

    @row.setter
    def row(self, value: int) -> None:
        self.walker.row = value

    @property
    def col(self) -> int:
        return self.walker.col

    @col.setter
    def col(self, value: int) -> None:
        self.walker.col = value

    @property
    def heading(self) -> tuple[int, int]:
        return self.walker.heading

    @heading.setter
    def heading(self, value: tuple[int, int]) -> None:
        self.walker.heading = value

    @property
    def vars(self) -> dict[str, _Value]:
        """The innermost walk's namespace, which a call does not share."""
        return self.walker.vars

    #: ``ip`` is a cell of the program's own rectangle: the first two
    #: parts are a row and a column, and the rest is a heading.  Without
    #: this a caller cannot tell the pair from a call depth or a frame
    #: stack, which look identical and mean somewhere else entirely.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...]:
        """The current instruction position: the cell and the heading.

        The heading is part of it because the same cell means a different
        command in each direction -- ``end`` read backwards is ``dne``, which
        the wiki says is not a halt -- so a position without it is ambiguous.
        """
        return (self.row, self.col, *self.heading)

    @property
    def memory(self) -> list[int]:
        """The VM's addressable view: the numeric variables, by name."""
        return [
            int(v)
            for _, v in sorted(self.vars.items())
            if isinstance(v, Fraction | int) and not isinstance(v, bool)
        ]

    @property
    def stack(self) -> list[object]:
        """The suspended callers, outermost first.

        Alight has no *operand* stack, but a call is a walker now, so
        there is something to observe: each entry is the cell its caller
        is waiting on.
        """
        return [(w.row, w.col) for w in self.walkers[:-1]]

    def _reduce(self, expr: _Expr) -> tuple[_Expr, str | None]:
        """Resolve calls left to right, stopping at the first user one.

        Returns the rewritten expression and the name of the user call to
        push, or None when nothing is left to run.  Every call it passes
        -- **builtins included** -- is replaced by its value, so a
        builtin is evaluated once even when a command resumes after a
        user call.

        Resolved operands and operators are retained too: ``1/0+at{l,.5,66}``
        must fail before the setter changes ``l``.
        """
        tag = expr[0]
        if tag in ("num", "special", "val"):
            return expr, None
        if tag == "var":
            return ("val", self._eval(expr)), None
        if tag == "not":
            inner, pending = self._reduce(cast(_Expr, expr[1]))
            node: _Expr = ("not", inner)
            return (node, pending) if pending else (("val", self._eval(node)), None)
        if tag == "bin":
            left, pending = self._reduce(cast(_Expr, expr[2]))
            if pending is not None:
                return ("bin", expr[1], left, expr[3]), pending
            right, pending = self._reduce(cast(_Expr, expr[3]))
            node = ("bin", expr[1], left, right)
            return (node, pending) if pending else (("val", self._eval(node)), None)
        if tag == "list":
            items: list[_Expr] = []
            rest = list(cast(list[_Expr], expr[1]))
            while rest:
                item, pending = self._reduce(rest.pop(0))
                items.append(item)
                if pending is not None:
                    return ("list", [*items, *rest]), pending
            return ("val", self._eval(("list", items))), None
        args: list[_Expr] = []
        rest = list(cast(list[_Expr], expr[2]))
        while rest:
            arg, pending = self._reduce(rest.pop(0))
            args.append(arg)
            if pending is not None:
                return ("call", expr[1], [*args, *rest]), pending
        name = cast(str, expr[1])
        if name not in _BUILTINS:
            return ("call", name, args), name
        # A builtin with every argument resolved: run it now and keep the
        # value, so a re-entry never runs it again.
        values = [self._eval(a) for a in args]
        result = _builtin(name, values, self.list_update)
        if isinstance(result, _InPlace):
            self._rebind(result.old, result.updated)
            result = result.updated
        return ("val", result), None

    def _resolve(self, text: str, word: str) -> bool:
        """Push a walker for the command's next unresolved call, if any.

        Returns whether this step was spent starting a call, in which case
        the command stays put and is re-entered once the value is in.
        """
        walker = self.walker
        if word not in ("turn", "skip", "wait", "set", "end") and not _is_call(
            text, word
        ):
            return False
        if walker.pending is None:
            expr = _command_expr(text, word, self.expression_syntax)
            if expr is None:
                return False
            if word == "set":
                p = _Parser(text)
                p.word()
                target_name = p.word()
                if target_name not in self.vars:
                    raise HaltError(f"no such variable: {target_name!r}")
            walker.pending = expr
        if walker.returned is not None:
            walker.pending = _replace_first(walker.pending, walker.returned)[0]
            walker.returned = None
        # ``_reduce`` may evaluate an in-place builtin, which rebuilds the
        # walker stack; re-read the (possibly new) innermost walk before
        # writing the reduced expression back.
        pending, name = self._reduce(walker.pending)
        self.walker.pending = pending
        if name is None:
            return False
        call = _first_call_or_none(pending, name)
        if call is None:  # pragma: no cover - _reduce just found one
            raise HaltError(f"lost the pending call to {name!r}")
        self._push_call(name, [self._eval(a) for a in cast(list[_Expr], call[2])])
        return True

    def _command(self, value: _Value | object = _MISSING) -> int | None:
        """Execute one command, leaving the pointer at the next one's start.

        Pure: the input character an ``inp`` command needs arrives as
        ``value`` (or the command asks for it by raising :class:`_NeedInputError`
        when ``value`` is the missing sentinel); the character an ``out``
        writes is returned rather than written.  A command holding calls
        takes more than one step: each step runs the leftmost-innermost user
        call by *pushing* a walker for it, and the value comes back rewritten
        into ``pending`` as a literal.  The command itself runs on the step
        where none is left, so no part of an Alight program executes inside
        another command's step.
        """
        self._input = value
        self._output = None
        if self.halted:
            return None
        text, row, col = _scan(self.grid, self.row, self.col, self.heading)
        word = _Parser(text, self.expression_syntax).word()
        if word == "end":
            if self._resolve(text, word):
                return self._output
            self._finish()
            return self._output
        if self._resolve(text, word):
            return self._output
        heading = self.heading
        if word == "turn":
            heading = _turned(heading, left=_truth(self._eval_rest()))
        elif word == "skip":
            if _truth(self._eval_rest()):
                # Consume the next command without running it, from just
                # past this one's pivot.
                drow, dcol = heading
                _, row, col = _scan(self.grid, row + drow, col + dcol, heading)
        else:
            self._exec(text, word)
        drow, dcol = heading
        self.walker.pending = None
        self.walker.returned = None
        self.row, self.col, self.heading = row + drow, col + dcol, heading
        if not self._in_bounds(self.row, self.col):
            raise Hint.GRID_PATH.halt("walked off the grid")
        return self._output

    def _finish(self) -> None:
        """Run an ``end``: halt the program, or return from a call."""
        value = self._return_value()
        if len(self.walkers) == 1:
            self.halted = True
            return
        self.walkers.pop()
        # The caller is shared with the run handed in, and setting its
        # ``returned`` would edit it, so take a private copy first.
        self.walkers[-1] = _own(self.walkers[-1])
        self.walker.returned = value

    def _in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < len(self.grid) and 0 <= col < len(self.grid[0])

    def _eval_rest(self) -> _Value:
        """Evaluate the expression already validated and reduced by step."""
        return self._eval(cast(_Expr, self.walker.pending))

    def _exec(self, text: str, word: str) -> None:
        """Run one non-control command."""
        if word == "":
            # A command of nothing but whitespace is the wiki's nop.  Every
            # cell between two semicolons is legal there, which is what lets
            # a vertical command carry a blank row.
            if text.strip():
                raise Hint.COMMAND.error(f"cannot parse command {text!r}")
            return
        if word == "var":
            name = self._name(text)
            if name in self.vars:
                raise Hint.VARIABLE_DECLARATION.halt(
                    f"variable {name!r} already exists"
                )
            self.vars[name] = "nil"
            return
        if word == "set":
            name = _Parser(text.removeprefix("set")).word()
            self.vars[name] = self._eval(cast(_Expr, self.walker.pending))
            return
        if word == "inp":
            self.vars[self._existing(text)] = self._read()
            return
        if word == "out":
            self._write(self.vars[self._existing(text)])
            return
        if word == "wait":
            # Evaluated for its errors and discarded: a sleep is unobservable
            # through this repo's IO and would only hang the suite.
            self._eval_rest()
            return
        # A bare *call* is a command, run for its effect and its value
        # discarded.
        # Only a call, not any expression: the example shows no other kind,
        # and a call is the only expression that can have an effect at all.
        if _is_call(text, word):
            self._eval(cast(_Expr, self.walker.pending))
            return
        raise syntax_error(
            f"unknown command {word!r} in {text!r}",
            keyword_hint(
                word,
                ("var", "set", "inp", "out", "wait"),
                "use var/set/inp/out/wait or a function call name{arguments}",
            ),
        )

    def _name(self, text: str) -> str:
        """Read the single variable name a ``var``/``inp``/``out`` names."""
        p = _Parser(text, self.expression_syntax)
        p.word()
        name = p.word()
        self._check_name(name)
        if not p.at_end():
            raise Hint.VARIABLE_OPERANDS.error(
                f"trailing text after variable name: {text!r}"
            )
        return name

    def _check_name(self, name: str) -> None:
        if not name or not name.isalnum() or name in _RESERVED:
            raise Hint.VARIABLE_NAME.error(f"bad variable name {name!r}")

    def _existing(self, text: str) -> str:
        name = self._name(text)
        if name not in self.vars:
            raise Hint.VARIABLE_REFERENCE.halt(f"no such variable: {name!r}")
        return name

    def _read(self) -> _Value:
        """Return the input value a step supplies, or ask for it.

        The shell reads the character; the transition only sees the value
        (or the ``eof`` special the shell substitutes).
        """
        if self._input is _MISSING:
            raise _NeedInputError
        return cast(_Value, self._input)

    def _write(self, value: _Value) -> None:
        """Validate the character an ``out`` names and record it."""
        if not _is_num(value):
            raise Hint.CHARACTER_OUTPUT.halt(
                "cannot output a nonnumeric value as a character"
            )
        if value != int(value) or not 0 <= value < 0x110000:
            raise Hint.CHARACTER_OUTPUT.halt("not a character code")
        self._output = int(value)

    def _eval(self, expr: _Expr) -> _Value:
        """Evaluate a parsed expression in this frame's namespace.

        The ``cast``s restate what the parser guarantees about each tag's
        payload.  ``_Expr`` is a plain tuple -- immutable and hashable, so a
        snapshot can hold one -- which costs the element types; the tag is
        what recovers them, and only the parser above ever builds one.
        """
        tag = expr[0]
        if tag == "num":
            return cast(Fraction | int, expr[1])
        if tag == "val":
            # A call ``_reduce`` already ran, carrying its value so that a
            # re-entry of this command does not run it a second time.
            return cast(_Value, expr[1])
        if tag == "special":
            return cast(_Special, expr[1])
        if tag == "var":
            name = cast(str, expr[1])
            if name not in self.vars:
                raise Hint.VARIABLE_REFERENCE.halt(f"no such variable: {name!r}")
            return self.vars[name]
        if tag == "list":
            return _list_value([self._eval(e) for e in cast(list[_Expr], expr[1])])
        if tag == "not":
            return _boolean(not _truth(self._eval(cast(_Expr, expr[1]))))
        if tag == "bin":
            op = cast(str, expr[1])
            left = self._eval(cast(_Expr, expr[2]))
            right = self._eval(cast(_Expr, expr[3]))
            if op in "=<>":
                return _compare(op, left, right)
            if op in "&|^":
                return _logic(op, left, right)
            return _arith(op, left, right)
        # _reduce replaces every call before evaluation.
        raise HaltError("unresolved expression")  # pragma: no cover

    def _rebind(self, old: list[_Value], updated: list[_Value]) -> None:
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
        for walker in self.walkers:
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
            copy = _Walker(
                walker.row,
                walker.col,
                walker.heading,
                cast("dict[str, _Value]", variables),
            )
            copy.pending = cast("_Expr | None", pending)
            copy.returned = cast("_Value | None", returned)
            walkers.append(copy)
        self.walkers = walkers

    def _push_call(self, name: str, args: list[_Value]) -> None:
        """Start a user call by pushing a walker for its body.

        The callee is a separate walk with its own pointer and variables, so
        the Evil Hack -- a function's code sharing cells with the caller's --
        needs nothing special: whoever is walking reads the cell in their own
        direction and keeps their own frame until they hit an ``end``.
        """
        found = _find_func(self.grid, name)
        if found is None:
            raise Hint.FUNCTION_REFERENCE.halt(f"no such function: {name!r}")
        row, col, heading, params = found
        if len(params) != len(args):
            raise Hint.CALL_ARITY.halt(
                f"function {name!r} takes {len(params)} arguments, got {len(args)}"
            )
        self.walkers.append(
            _Walker(row, col, heading, dict(zip(params, args, strict=True)))
        )

    def _return_value(self) -> _Value:
        """Evaluate the expression an ``end <value>`` returns, or ``nil``.

        Like the other commands, the value comes from ``pending`` when
        there is one -- ``end inner{n}+1`` holds a call, and that call is
        resolved by a pushed walker before this runs.
        """
        pending = self.walker.pending
        return "nil" if pending is None else self._eval(pending)


class _InPlace:
    """Marker for an in-place ``at``: replace ``old`` by ``updated`` everywhere."""

    __slots__ = ("old", "updated")

    def __init__(self, old: list[_Value], updated: list[_Value]) -> None:
        self.old = old
        self.updated = updated


def _replace(
    root: object, old: list[_Value], updated: list[_Value], memo: dict[int, object]
) -> object:
    """Return ``root`` with every occurrence of ``old`` replaced by ``updated``.

    A structural copy that preserves sharing: containers that do not hold
    ``old`` are returned unchanged, and one rebuilt container is reused
    through ``memo`` wherever the original was aliased.  Cyclic lists --
    which the language can build -- are pre-registered so the walk
    terminates; a rebuilt cycle keeps pointing at the original, which no
    registry-corpus program reaches.
    """
    if root is old:
        return updated
    if not isinstance(root, list | tuple | dict):
        return root
    key = id(root)
    if key in memo:
        return memo[key]
    if isinstance(root, dict):
        rebuilt: dict[object, object] = {}
        memo[key] = rebuilt
        changed = False
        for name, value in root.items():
            replaced = _replace(value, old, updated, memo)
            rebuilt[name] = replaced
            changed = changed or replaced is not value
        if changed:
            return rebuilt
        memo[key] = root
        return root
    if isinstance(root, tuple):
        items = tuple(_replace(item, old, updated, memo) for item in root)
        changed = any(a is not b for a, b in zip(items, root, strict=True))
        memo[key] = items if changed else root
        return memo[key]
    rebuilt_list: list[object] = []
    memo[key] = rebuilt_list
    changed = False
    for item in root:
        replaced = _replace(item, old, updated, memo)
        rebuilt_list.append(replaced)
        changed = changed or replaced is not item
    if not changed:
        memo[key] = root
        return root
    return rebuilt_list


def _own(walker: _Walker) -> _Walker:
    """Return a private copy of ``walker`` that a step may edit.

    The copy takes a fresh ``vars`` mapping -- the one store a command
    writes -- while the call frame's scalars and the pending expression are
    copied by value.  It is deliberately shallow: shared list values stay
    shared, because the one operation that changes a list replaces it
    everywhere (see :meth:`_Core._rebind`) rather than editing it.
    """
    copy = _Walker(walker.row, walker.col, walker.heading, dict(walker.vars))
    copy.pending = walker.pending
    copy.returned = walker.returned
    return copy


def _advance(
    core: _Core, value: _Value | object = _MISSING
) -> tuple[_Core, int | None]:
    """Return the core after one command, and any character to write.

    Pure.  The whole state is the immutable ``core`` and the one input
    character a step may need arrives as ``value``.  The walker stack is
    copied -- and the innermost walk, the only one a command edits, given a
    private copy -- so the core handed in is never touched; shared list
    values are replaced, not edited, wherever they change.
    """
    walkers = list(core.walkers)
    if walkers:
        walkers[-1] = _own(walkers[-1])
    next_core = _Core(
        core.grid,
        core.expression_syntax,
        core.list_update,
        walkers,
        halted=core.halted,
    )
    output = next_core._command(value)  # noqa: SLF001 -- the semantics function
    return next_core, output


class _Machine:
    """Per-run Alight shell around the pure :func:`_advance`.

    ``step`` reads the one character an ``inp`` command needs and writes
    the one an ``out`` command produces, then stores the core the pure
    transition returns.
    """

    #: Whether a read past the end of the input yields a *value* here
    #: rather than raising.  A few languages do; the rest raise
    #: :class:`~esolangs.exceptions.InputExhaustedError`, which is the
    #: package norm and what :func:`esolangs.run` documents; this one does
    #: not, so an underfed program answers a different row of its table
    #: instead of refusing, and a caller has no way to tell from the output
    #: that it happened.
    #:
    #: Declared rather than changed.  The zero-beyond-input convention was
    #: audited against every wiki page and settled deliberately
    #: (``docs/limitations.md``, Interpreter conventions); rewriting it
    #: would be a decision about what these languages *mean*, not a fix.
    #: What was wrong was that nothing said so, so the promise ``run`` made
    #: was false for seven languages and a generic caller could not find
    #: out which.
    eof_is_a_value = True

    def __init__(
        self,
        code: list[str] | str,
        io: IO,
        *,
        expression_syntax: str = "infix",
        list_update: str = "in_place",
    ) -> None:
        self.io = io
        self._input_reads = 0
        grid = _grid(code.splitlines() if isinstance(code, str) else list(code))
        if not grid or not grid[0]:
            raise Hint.PROGRAM.error("empty program")
        start = _find(grid, "begin")
        if start is None:
            raise Hint.ENTRY.error("program has no 'begin'")
        row, col, heading = start
        drow, dcol = heading
        # The walk resumes from just past ``begin``'s last character; the
        # ``;`` that terminates it is the first thing ``_scan`` will see.
        self.core = _Core(
            grid,
            validate_expression_syntax(expression_syntax),
            validate_list_update(list_update),
            [_Walker(row + 5 * drow, col + 5 * dcol, heading, {})],
        )

    @property
    def walkers(self) -> list[_Walker]:
        """The stack of walks in progress, innermost last."""
        return self.core.walkers

    @property
    def walker(self) -> _Walker:
        """The innermost walk: the one ``step`` advances."""
        return self.core.walker

    @property
    def vars(self) -> dict[str, _Value]:
        """The innermost walk's namespace, which a call does not share."""
        return self.core.vars

    @property
    def halted(self) -> bool:
        """Whether the program has reached its outer ``end``."""
        return self.core.halted

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Every walker, not only the innermost: a callee that returns to a
        # caller standing somewhere else is a different state, and a lap
        # that consumed a line is not a repeat.
        return (
            _freeze(tuple(walker.key() for walker in self.walkers)),
            self.halted,
            self._input_reads,
        )

    #: ``ip`` is a cell of the program's own rectangle: the first two
    #: parts are a row and a column, and the rest is a heading.  Without
    #: this a caller cannot tell the pair from a call depth or a frame
    #: stack, which look identical and mean somewhere else entirely.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...]:
        """The current instruction position: the cell and the heading."""
        return self.core.ip

    @property
    def memory(self) -> list[int]:
        """The VM's addressable view: the numeric variables, by name."""
        return self.core.memory

    @property
    def stack(self) -> list[object]:
        """The suspended callers, outermost first."""
        return self.core.stack

    def _read_char(self) -> _Value:
        """Read one character, or ``eof`` when the input is exhausted."""
        try:
            raw = self.io.input_char()
        except EOFError:
            return "eof"
        self._input_reads += 1
        return Fraction(raw)

    def step(self) -> None:
        """Execute one command through the pure transition, reading and writing.

        The shell: an ``inp`` command's character is read here and handed to
        :func:`_advance`, and the character it returns is written here.
        """
        if self.halted:
            return
        value: _Value | object = _MISSING
        while True:
            try:
                self.core, output = _advance(self.core, value)
                break
            except _NeedInputError:
                value = self._read_char()
        if output is not None:
            self.io.print_char(chr(output))


def _builtin(name: str, args: list[_Value], list_update: str) -> _Value | _InPlace:
    """Apply one of the four builtin functions."""
    if name in ("trunc", "sign"):
        if len(args) != 1 or not _is_num(args[0]):
            raise Hint.BUILTIN_NUMBER.halt(f"{name} takes one number")
        value = args[0]
        if name == "trunc":
            return Fraction(int(value))
        return Fraction((value > 0) - (value < 0))
    if len(args) < 1 or not isinstance(args[0], list):
        raise Hint.BUILTIN_LIST.halt(f"{name} takes a list")
    seq = args[0]
    if name == "len":
        if len(args) == 1:
            return Fraction(len(seq))
        if len(args) != 2 or not _is_num(args[1]):
            raise Hint.LEN_ARGUMENTS.halt("len takes a list and optionally a count")
        count = args[1]
        if count != int(count) or count < 0:
            raise Hint.PADDING_COUNT.halt("len pad count is not a whole number")
        padding: list[_Value] = ["nil"] * int(count)
        return [*seq, *padding]
    if len(args) == 2:
        # Out of bounds reads as nil, per the wiki -- only the three-argument
        # *set* form raises.
        slot = _index(args[1])
        return seq[slot] if slot < len(seq) else "nil"
    if len(args) != 3:
        raise Hint.AT_ARGUMENTS.halt(
            "at takes a list, an index, and optionally a value"
        )
    slot = _index(args[1])
    if slot >= len(seq):
        raise Hint.INDEXED_WRITE.halt(f"at index past the end of a {len(seq)}-list")
    _list_value([*seq, args[2]])
    if list_update == "in_place":
        # The value is a fresh list; the caller replaces the old one
        # everywhere it is aliased rather than editing it, so a state a
        # caller banked cannot change under it.
        updated = list(seq)
        updated[slot] = args[2]
        return _InPlace(seq, updated)
    result = seq.copy()
    result[slot] = args[2]
    return result


def _is_call(text: str, word: str) -> bool:
    """Whether a command is a bare call, run for its effect."""
    p = _Parser(text)
    p.word()
    return (
        bool(word)
        and (word not in _RESERVED or word in (*_BUILTINS, *_SPECIALS))
        and p.peek() == "{"
    )


def run(
    code: list[str] | str,
    io: IO,
    *,
    expression_syntax: str = "infix",
    list_update: str = "in_place",
) -> None:
    """Run an Alight program to its ``end``."""
    machine = _Machine(
        code, io, expression_syntax=expression_syntax, list_update=list_update
    )
    drive(machine)
