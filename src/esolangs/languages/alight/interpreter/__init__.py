"""Interpreter for Alight, a two-dimensional language of word commands.

The language spec is the wiki page, https://esolangs.org/wiki/Alight; where
its prose and its examples disagree this interpreter follows the examples
(infix operators evaluated left to right, in-place three-argument ``at``),
as recorded in ``docs/limitations.md`` under "Interpreter conventions".
An in-place ``at`` is seen through every variable naming that list.
``inp`` at EOF reads ``eof``; invalid runtime operations raise
:class:`~esolangs.exceptions.HaltError`.
"""

from fractions import Fraction
from typing import TypeGuard, assert_never, overload

from esolangs.exceptions import HaltError
from esolangs.languages.alight.interpreter._dialect import (
    expression_syntax as validate_expression_syntax,
)
from esolangs.languages.alight.interpreter._dialect import (
    list_update as validate_list_update,
)
from esolangs.languages.alight.interpreter._hints import Hint
from esolangs.languages.alight.interpreter._parse import (
    _NODE_TYPES,
    _RESERVED,
    _SPECIALS,
    _Bin,
    _Call,
    _command_expr,
    _Expr,
    _first_call_or_none,
    _List,
    _Not,
    _Num,
    _parse_number,
    _Parser,
    _replace_first,
    _Special,
    _SpecialNode,
    _Val,
    _valid_name,
    _Value,
    _Var,
)
from esolangs.languages.alight.interpreter._state import _equal, _freeze
from esolangs.languages.alight.interpreter._walk import (
    _find,
    _find_func,
    _grid,
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

    The grid is not here: no command writes to the program, so it is a
    constant of the run.  ``vars`` is frozen to an alias-preserving graph by
    :func:`_freeze` before a snapshot stores it, because lists can be
    aliased and a live reference would let a later command mutate a
    snapshot the cycle detector had already banked.
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


def _has_input(value: _Value | object) -> TypeGuard[_Value]:
    """Whether the step was handed its input character already.

    A ``TypeGuard`` rather than a plain ``bool`` so the reader below
    narrows: ``value is _MISSING`` alone does not narrow the sentinel out
    for the type checker.
    """
    return value is not _MISSING


class _NeedInputError(Exception):
    """Ask the shell for the one input character an ``inp`` command needs."""


class _Views:
    """The VM shell's read-only view of a run: position, memory, call stack.

    ``ip``, ``memory`` and ``stack`` are what the driver and the cycle
    detector observe; they read the core's state but never write through it.
    Separate from the frame accessors (``walker``/``row``/``col``/
    ``heading``/``vars``) the components write through, so a reader can tell
    observation from mutation.
    """

    def __init__(self, core: "_Core") -> None:
        self._core = core

    @property
    def ip(self) -> tuple[int, ...]:
        """The current instruction position: the cell and the heading.

        The heading is part of it because the same cell means a different
        command in each direction -- ``end`` read backwards is ``dne``, which
        the wiki says is not a halt -- so a position without it is ambiguous.
        """
        core = self._core
        return (core.walker.row, core.walker.col, *core.walker.heading)

    @property
    def memory(self) -> list[int]:
        """The VM's addressable view: the numeric variables, by name."""
        return [
            int(v)
            for _, v in sorted(self._core.vars.items())
            if isinstance(v, Fraction | int) and not isinstance(v, bool)
        ]

    @property
    def stack(self) -> list[object]:
        """The suspended callers, outermost first.

        Alight has no *operand* stack, but a call is a walker now, so
        there is something to observe: each entry is the cell its caller
        is waiting on.
        """
        return [(w.row, w.col) for w in self._core.walkers[:-1]]


class _Expressions:
    """Alight expression evaluation, against the innermost walk's namespace.

    ``reduce`` resolves the calls in an expression left to right, stopping
    at the first user-defined call -- builtins run immediately, replaced by
    their values so a re-entered command never runs one twice.
    ``evaluate`` computes the value of a fully reduced expression.
    ``rebind`` carries an in-place ``at`` through every alias of the list.
    """

    def __init__(self, core: "_Core") -> None:
        self._core = core

    def reduce(self, expr: _Expr) -> tuple[_Expr, str | None]:
        """Resolve calls left to right, stopping at the first user one.

        Returns the rewritten expression and the name of the user call to
        push, or None when nothing is left to run.  Every call it passes
        -- **builtins included** -- is replaced by its value, so a
        builtin is evaluated once even when a command resumes after a
        user call.

        Resolved operands and operators are retained too: ``1/0+at{l,.5,66}``
        must fail before the setter changes ``l``.
        """
        if isinstance(expr, (_Num, _Val, _SpecialNode)):
            return expr, None
        if isinstance(expr, _Var):
            return _Val("val", self.evaluate(expr)), None
        if isinstance(expr, _Not):
            inner, pending = self.reduce(expr.operand)
            node: _Expr = _Not("not", inner)
            if pending is not None:
                return node, pending
            return _Val("val", self.evaluate(node)), None
        if isinstance(expr, _Bin):
            left, pending = self.reduce(expr.left)
            if pending is not None:
                return _Bin("bin", expr.op, left, expr.right), pending
            right, pending = self.reduce(expr.right)
            node = _Bin("bin", expr.op, left, right)
            if pending is not None:
                return node, pending
            return _Val("val", self.evaluate(node)), None
        if isinstance(expr, _List):
            items: list[_Expr] = []
            rest = list(expr.items)
            while rest:
                item, pending = self.reduce(rest.pop(0))
                items.append(item)
                if pending is not None:
                    return _List("list", [*items, *rest]), pending
            return _Val("val", self.evaluate(_List("list", items))), None
        if isinstance(expr, _Call):
            args: list[_Expr] = []
            rest = list(expr.args)
            while rest:
                arg, pending = self.reduce(rest.pop(0))
                args.append(arg)
                if pending is not None:
                    return _Call("call", expr.name, [*args, *rest]), pending
            if expr.name not in _BUILTINS:
                return _Call("call", expr.name, args), expr.name
            # A builtin with every argument resolved: run it now and keep the
            # value, so a re-entry never runs it again.
            values = [self.evaluate(a) for a in args]
            result = _builtin(expr.name, values, self._core.list_update)
            if isinstance(result, _InPlace):
                self.rebind(result.old, result.updated)
                result = result.updated
            return _Val("val", result), None
        assert_never(expr)

    def evaluate(self, expr: _Expr) -> _Value:
        """Evaluate a parsed expression in this frame's namespace.

        The nodes are typed, so each tag dispatches to typed fields.
        Nodes are built by the parser, by ``_Expressions.reduce``
        (which folds resolved calls into values and rebuilds nodes
        with reduced children), and by ``_parse._replace_first``
        (which rebuilds the path to a replaced call).  A node is
        still a tuple underneath -- immutable, so a snapshot can
        carry one -- with the tag first, which is what keeps the
        legacy ``("tag", ...)`` spelling working.
        """
        if isinstance(expr, _Num):
            return expr.value
        if isinstance(expr, _Val):
            # A call ``reduce`` already ran, carrying its value so that a
            # re-entry of this command does not run it a second time.
            return expr.value
        if isinstance(expr, _SpecialNode):
            return expr.name
        if isinstance(expr, _Var):
            if expr.name not in self._core.vars:
                raise Hint.VARIABLE_REFERENCE.halt(f"no such variable: {expr.name!r}")
            return self._core.vars[expr.name]
        if isinstance(expr, _List):
            return _list_value([self.evaluate(e) for e in expr.items])
        if isinstance(expr, _Not):
            return _boolean(not _truth(self.evaluate(expr.operand)))
        if isinstance(expr, _Bin):
            left = self.evaluate(expr.left)
            right = self.evaluate(expr.right)
            if expr.op in "=<>":
                return _compare(expr.op, left, right)
            if expr.op in "&|^":
                return _logic(expr.op, left, right)
            return _arith(expr.op, left, right)
        if isinstance(expr, _Call):
            # ``reduce`` replaces every call before evaluation.
            raise HaltError("unresolved expression")  # pragma: no cover
        assert_never(expr)

    def evaluate_rest(self) -> _Value:
        """Evaluate the expression already validated and reduced by step."""
        pending = self._core.walker.pending
        if pending is None:  # pragma: no cover - resolve() sets pending first
            raise HaltError("no pending expression")
        return self.evaluate(pending)

    def rebind(self, old: list[_Value], updated: list[_Value]) -> None:
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
        for walker in self._core.walkers:
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
            copy = _Walker(walker.row, walker.col, walker.heading, variables)
            copy.pending = pending
            copy.returned = returned
            walkers.append(copy)
        self._core.walkers = walkers


#: ``_replace`` preserves its input's type: it returns the input with ``old``
#: swapped for ``updated``.  The overloads carry that to callers; the
#: implementation below works in ``object``.
@overload
def _replace(
    root: dict[str, _Value],
    old: list[_Value],
    updated: list[_Value],
    memo: dict[int, object],
) -> dict[str, _Value]: ...


@overload
def _replace[T](
    root: T, old: list[_Value], updated: list[_Value], memo: dict[int, object]
) -> T: ...


def _replace(
    root: object,
    old: list[_Value],
    updated: list[_Value],
    memo: dict[int, object],
) -> object:
    """Return ``root`` with every occurrence of ``old`` replaced by ``updated``.

    A structural copy that preserves sharing: containers that do not hold
    ``old`` are returned unchanged, and one rebuilt container is reused
    through ``memo`` wherever the original was aliased.  Cyclic lists --
    which the language can build -- are pre-registered so the walk
    terminates; a rebuilt cycle keeps pointing at the original, which no
    registry-corpus program reaches.

    AST nodes are rebuilt as their own type, so a pending expression that
    referenced ``old`` stays a typed tree rather than decaying to plain
    tuples.
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
    if isinstance(root, _NODE_TYPES):
        return _replace_node(root, old, updated, memo)
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


def _replace_node(
    root: _Expr, old: list[_Value], updated: list[_Value], memo: dict[int, object]
) -> _Expr:
    """Rebuild an AST node with ``old`` replaced by ``updated`` inside.

    Numbers, variables, and specials hold no list; every other node is
    rebuilt field by field, returning the original node when nothing inside
    changed.  Nodes are immutable trees, so unlike lists they cannot be
    cyclic -- only the values they wrap can, and those go through
    :func:`_replace`.
    """
    key = id(root)
    if isinstance(root, (_Num, _Var, _SpecialNode)):
        memo[key] = root
        return root
    if isinstance(root, _Val):
        value = _replace(root.value, old, updated, memo)
        node: _Expr = root if value is root.value else _Val("val", value)
        memo[key] = node
        return node
    if isinstance(root, _Not):
        operand = _replace(root.operand, old, updated, memo)
        node = root if operand is root.operand else _Not("not", operand)
        memo[key] = node
        return node
    if isinstance(root, _Bin):
        left = _replace(root.left, old, updated, memo)
        right = _replace(root.right, old, updated, memo)
        if left is root.left and right is root.right:
            memo[key] = root
            return root
        node = _Bin("bin", root.op, left, right)
        memo[key] = node
        return node
    if isinstance(root, _List):
        items = [_replace(item, old, updated, memo) for item in root.items]
        if all(new is current for new, current in zip(items, root.items, strict=True)):
            memo[key] = root
            return root
        node = _List("list", items)
        memo[key] = node
        return node
    args = [_replace(arg, old, updated, memo) for arg in root.args]
    if all(new is current for new, current in zip(args, root.args, strict=True)):
        memo[key] = root
        return root
    node = _Call("call", root.name, args)
    memo[key] = node
    return node


class _Handlers:
    """The non-control commands: var/set/inp/out/wait and bare calls.

    Owns the step's I/O registers: ``input`` is the character the shell
    handed this step -- or the missing sentinel, when ``inp`` must ask for
    it by raising :class:`_NeedInputError` -- and ``output`` the character
    an ``out`` wrote.
    """

    def __init__(self, core: "_Core") -> None:
        self._core = core
        self.input: _Value | object = _MISSING
        self.output: int | None = None

    def execute(self, text: str, word: str) -> None:
        """Run one non-control command."""
        core = self._core
        if word == "":
            # A command of nothing but whitespace is the wiki's nop.  Every
            # cell between two semicolons is legal there, which is what lets
            # a vertical command carry a blank row.
            if text.strip():
                raise Hint.COMMAND.error(f"cannot parse command {text!r}")
            return
        if word == "var":
            name = self._name(text)
            if name in core.vars:
                raise Hint.VARIABLE_DECLARATION.halt(
                    f"variable {name!r} already exists"
                )
            core.vars[name] = "nil"
            return
        if word == "set":
            name = _Parser(text.removeprefix("set")).word()
            core.vars[name] = core.expressions.evaluate_rest()
            return
        if word == "inp":
            core.vars[self._existing(text)] = self._read()
            return
        if word == "out":
            self._write(core.vars[self._existing(text)])
            return
        if word == "wait":
            # Evaluated for its errors and discarded: a sleep is unobservable
            # through this repo's IO and would only hang the suite.
            core.expressions.evaluate_rest()
            return
        # A bare *call* is a command, run for its effect and its value
        # discarded.
        # Only a call, not any expression: the example shows no other kind,
        # and a call is the only expression that can have an effect at all.
        if _is_call(text, word):
            core.expressions.evaluate_rest()
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
        p = _Parser(text, self._core.expression_syntax)
        p.word()
        name = p.word()
        self._check_name(name)
        if not p.at_end():
            raise Hint.VARIABLE_OPERANDS.error(
                f"trailing text after variable name: {text!r}"
            )
        return name

    def _check_name(self, name: str) -> None:
        if not _valid_name(name):
            raise Hint.VARIABLE_NAME.error(f"bad variable name {name!r}")

    def _existing(self, text: str) -> str:
        name = self._name(text)
        if name not in self._core.vars:
            raise Hint.VARIABLE_REFERENCE.halt(f"no such variable: {name!r}")
        return name

    def _read(self) -> _Value:
        """Return the input value a step supplies, or ask for it.

        The shell reads the character; the transition only sees the value
        (or the ``eof`` special the shell substitutes).
        """
        value = self.input
        if not _has_input(value):
            raise _NeedInputError
        return value

    def _write(self, value: _Value) -> None:
        """Validate the character an ``out`` names and record it."""
        if not _is_num(value):
            raise Hint.CHARACTER_OUTPUT.halt(
                "cannot output a nonnumeric value as a character"
            )
        if value != int(value) or not 0 <= value < 0x110000:
            raise Hint.CHARACTER_OUTPUT.halt("not a character code")
        self.output = int(value)


class _Calls:
    """Call machinery: resolving, pushing, and returning from calls.

    A call is a separate walk with its own pointer and namespace, pushed
    onto the core's walker stack.  ``resolve`` spends a step starting the
    command's next unresolved call; ``finish`` runs ``end``.
    """

    def __init__(self, core: "_Core") -> None:
        self._core = core

    def resolve(self, text: str, word: str) -> bool:
        """Push a walker for the command's next unresolved call, if any.

        Returns whether this step was spent starting a call, in which case
        the command stays put and is re-entered once the value is in.
        """
        core = self._core
        walker = core.walker
        if word not in ("turn", "skip", "wait", "set", "end") and not _is_call(
            text, word
        ):
            return False
        if walker.pending is None:
            expr = _command_expr(text, word, core.expression_syntax)
            if expr is None:
                return False
            if word == "set":
                p = _Parser(text)
                p.word()
                target_name = p.word()
                if target_name not in core.vars:
                    raise HaltError(f"no such variable: {target_name!r}")
            walker.pending = expr
        if walker.returned is not None:
            walker.pending = _replace_first(walker.pending, walker.returned)[0]
            walker.returned = None
        # ``reduce`` may evaluate an in-place builtin, which rebuilds the
        # walker stack; re-read the (possibly new) innermost walk before
        # writing the reduced expression back.
        pending, name = core.expressions.reduce(walker.pending)
        core.walker.pending = pending
        if name is None:
            return False
        call = _first_call_or_none(pending, name)
        if call is None:  # pragma: no cover - reduce() just found one
            raise HaltError(f"lost the pending call to {name!r}")
        self._push_call(name, [core.expressions.evaluate(a) for a in call.args])
        return True

    def _push_call(self, name: str, args: list[_Value]) -> None:
        """Start a user call by pushing a walker for its body.

        The callee is a separate walk with its own pointer and variables, so
        the Evil Hack -- a function's code sharing cells with the caller's --
        needs nothing special: whoever is walking reads the cell in their own
        direction and keeps their own frame until they hit an ``end``.
        """
        core = self._core
        found = _find_func(core.grid, name)
        if found is None:
            raise Hint.FUNCTION_REFERENCE.halt(f"no such function: {name!r}")
        row, col, heading, params = found
        if len(params) != len(args):
            raise Hint.CALL_ARITY.halt(
                f"function {name!r} takes {len(params)} arguments, got {len(args)}"
            )
        core.walkers.append(
            _Walker(row, col, heading, dict(zip(params, args, strict=True)))
        )

    def finish(self) -> None:
        """Run an ``end``: halt the program, or return from a call."""
        core = self._core
        value = self._return_value()
        if len(core.walkers) == 1:
            core.halted = True
            return
        core.walkers.pop()
        # The caller is shared with the run handed in, and setting its
        # ``returned`` would edit it, so take a private copy first.
        core.walkers[-1] = _own(core.walkers[-1])
        core.walker.returned = value

    def _return_value(self) -> _Value:
        """Evaluate the expression an ``end <value>`` returns, or ``nil``.

        Like the other commands, the value comes from ``pending`` when
        there is one -- ``end inner{n}+1`` holds a call, and that call is
        resolved by a pushed walker before this runs.
        """
        pending = self._core.walker.pending
        return "nil" if pending is None else self._core.expressions.evaluate(pending)


class _Core:
    """The state of one Alight run and its one-command transition.

    Owns the grid, the dialect choices, the walker stack, and the halted
    flag.  The semantics are split across three components that collaborate
    through this core: :class:`_Expressions` evaluates, :class:`_Calls`
    pushes walkers and returns from them, :class:`_Handlers` runs the
    non-control commands.  :meth:`command` is the one orchestration point;
    it does no evaluation, pushing, or I/O itself.  :attr:`views` is the VM
    shell's read-only observation of the run.
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
        self.expressions = _Expressions(self)
        self.handlers = _Handlers(self)
        self.calls = _Calls(self)
        self.views = _Views(self)

    @property
    def walker(self) -> _Walker:
        """The innermost walk: the one ``command`` advances."""
        return self.walkers[-1]

    @property
    def vars(self) -> dict[str, _Value]:
        """The innermost walk's namespace, which a call does not share."""
        return self.walker.vars

    def command(self, value: _Value | object = _MISSING) -> int | None:
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
        self.handlers.input = value
        self.handlers.output = None
        if self.halted:
            return None
        text, row, col = _scan(
            self.grid, self.walker.row, self.walker.col, self.walker.heading
        )
        word = _Parser(text, self.expression_syntax).word()
        if self.calls.resolve(text, word):
            return self.handlers.output
        if word == "end":
            self.calls.finish()
            return self.handlers.output
        heading = self.walker.heading
        if word == "turn":
            guard = _truth(self.expressions.evaluate_rest())
            heading = _turned(heading, left=guard)
        elif word == "skip":
            if _truth(self.expressions.evaluate_rest()):
                # Consume the next command without running it, from just
                # past this one's pivot.
                drow, dcol = heading
                _, row, col = _scan(self.grid, row + drow, col + dcol, heading)
        else:
            self.handlers.execute(text, word)
        drow, dcol = heading
        self.walker.pending = None
        self.walker.returned = None
        walker = self.walker
        walker.row, walker.col, walker.heading = row + drow, col + dcol, heading
        if not self._in_bounds(walker.row, walker.col):
            raise Hint.GRID_PATH.halt("walked off the grid")
        return self.handlers.output

    def _in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < len(self.grid) and 0 <= col < len(self.grid[0])


class _InPlace:
    """Marker for an in-place ``at``: replace ``old`` by ``updated`` everywhere."""

    __slots__ = ("old", "updated")

    def __init__(self, old: list[_Value], updated: list[_Value]) -> None:
        self.old = old
        self.updated = updated


def _own(walker: _Walker) -> _Walker:
    """Return a private copy of ``walker`` that a step may edit.

    The copy takes a fresh ``vars`` mapping -- the one store a command
    writes -- while the call frame's scalars and the pending expression are
    copied by value.  It is deliberately shallow: shared list values stay
    shared, because the one operation that changes a list replaces it
    everywhere (see :meth:`_Expressions.rebind`) rather than editing it.
    """
    copy = _Walker(walker.row, walker.col, walker.heading, dict(walker.vars))
    copy.pending = walker.pending
    copy.returned = walker.returned
    return copy


# :func:`_advance` is the pure transition: it takes the whole state and the one input
# character a step needs -- raising :class:`_NeedInputError` when the shell has not
# read it yet -- and returns the next state and any character an ``out`` writes.  It
# edits nothing it is handed: the walker stack is copied, the innermost frame takes a
# private ``vars`` copy, and an in-place ``at`` rebuilds the list and rebinds every
# alias of it rather than writing through the shared reference.  :class:`_Machine` is
# the shell that reads the input and writes the output.
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
    output = next_core.command(value)
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
        return self.core.views.ip

    @property
    def memory(self) -> list[int]:
        """The VM's addressable view: the numeric variables, by name."""
        return self.core.views.memory

    @property
    def stack(self) -> list[object]:
        """The suspended callers, outermost first."""
        return self.core.views.stack

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
            raise Hint.BUILTIN_LIST.halt("len takes a list and optionally a count")
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
        raise Hint.BUILTIN_LIST.halt(
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
