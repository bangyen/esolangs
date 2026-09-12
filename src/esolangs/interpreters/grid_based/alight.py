"""Interpreter for Alight.

A two-dimensional language whose commands are words, not single characters.
The pointer starts at ``begin`` -- which may be written forwards, backwards,
up, or down, and that spelling picks the heading -- and walks the grid one
cell at a time, accumulating characters into a command until a ``;``
terminates it.  ``turn`` pivots *at that semicolon's cell* and the next
command begins one cell beyond it in the new heading; the program stops when
it reaches ``end`` travelling in its current direction.

Commands: ``var x``, ``set x <expr>``, ``skip <expr>`` (skip the next command
if true), ``turn <expr>`` (left if true, else right), ``inp x``, ``out x``,
``wait <expr>``, and the empty command as a nop.  Values are numbers, lists,
and the four specials ``nil``/``eof``/``left``/``right`` (``left`` is true).
Lists index from 0.5: ``at{l, 0.5}`` is the first element.  Functions are
defined with ``func name{a, b}`` in place of ``begin`` and return via
``end <value>``, each call getting its own variable namespace.

Input is one line per ``inp``, taking the line's first character; output is
one character per ``out``.  Run a program with ``python -m
esolangs.interpreters.grid_based.alight prog.al``.

The wiki leaves several points open; this interpreter decides them as
follows, and raises :class:`ValueError` for a structurally malformed program
and :class:`~esolangs.exceptions.HaltError` for an invalid runtime
operation.

* **Operator order.**  The prose says operators are postfix, but every
  example on the page is infix -- ``turn c = eof``, ``set x len{l}-0.5``,
  ``skip sign{x} > 0``.  Examples are ground truth, so expressions parse as
  infix applied strictly left to right with no precedence and no grouping:
  ``a+b*c`` is ``(a+b)*c``.  Unary ``!`` appears in no example and is taken
  as prefix, the only reading that does not need an operand it lacks.
* **Three-argument ``at`` sets in place** and returns the same list, where
  the prose says it returns a copy.  The reversed-cat example runs
  ``at{l, len{l}-0.5, c}`` as a bare command, discarding the result: under
  copy semantics that is a no-op, ``l`` stays all ``nil``, and the example
  crashes on its own first ``out``.  In place it reverses its input.  A bare
  *call* is therefore a command too, evaluated for its effect.  Lists are
  consequently references: ``set m l`` aliases, and a function can mutate a
  list argument.
* **EOF.**  ``inp`` past the end of input stores ``eof``, which is what the
  cat examples' ``c = eof`` guard tests.  An empty line is a real line and
  reads as 0, following the repo's ``input_char`` convention.
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
* **No step cap.**  A walk runs until it halts.  A program that loops over
  a fixed grid revisits its whole state, so
  :func:`esolangs.vm.run_until_halt_or_cycle` *proves* the hang instead of
  a counter guessing at one; a walk that never repeats a state is what
  ``esolangs.run``'s wall-clock ``timeout`` is for.  ``grapheme.py``
  documents removing exactly such a budget, as duplicating that timeout.

  That holds inside a called function too: a call *pushes* a walker rather
  than running the callee in the caller's step, so a callee that rings
  forever reaches ``snapshot`` on every command and is proved the same
  way.  ``lamfunc.py`` and ``dinac.py`` frame calls for the same reason.
"""

import sys
from typing import Literal, TypeGuard, cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# : Headings as ``(drow,.
# : so a *left* turn.
type _Heading = tuple[int, int]

_EAST: _Heading = (0, 1)
_WEST: _Heading = (0, -1)
_NORTH: _Heading = (-1, 0)
_SOUTH: _Heading = (1, 0)

# Turning is a rotation of this.
# previous a left one.
# directions cannot disagree.
_CLOCKWISE: tuple[_Heading, ...] = (_NORTH, _EAST, _SOUTH, _WEST)

# : The four special values, as.
# : number -- comparing one.
# : so it needs to be.
# : specials are spelled as.
type _Special = Literal["nil", "eof", "left", "right"]
_SPECIALS: tuple[_Special, ...] = ("nil", "eof", "left", "right")

# : A value: a number, a list.
type _Value = float | list["_Value"] | _Special

# : Reserved words a variable.
# : are alphanumeric and "not.
# : every word the grammar.
_RESERVED = frozenset(
    {
        "begin",
        "end",
        "func",
        "var",
        "set",
        "skip",
        "turn",
        "inp",
        "out",
        "wait",
        "at",
        "len",
        "trunc",
        "sign",
        *_SPECIALS,
    }
)

# : The four functions the.
# : names is a ``func`` on the.
# : walker rather than by.
_BUILTINS = ("at", "len", "trunc", "sign")

# There is no call-depth cap.
# the callee inside the.
# walker list on the heap and.
# revisits no state, so it is.
# ``timeout`` is for -- the.


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
        """Return the walker as a hashable value for :meth:`snapshot`."""
        return (
            self.row,
            self.col,
            self.heading,
            _freeze(self.vars),
            _freeze(self.pending),
            _freeze(self.returned),
        )


def _grid(code: list[str]) -> list[str]:
    """Pad ``code`` to a rectangle, so every in-bounds cell is a character.

    Ragged lines are the norm -- the wiki's examples have a row whose only
    content is a trailing space, and one that is short of the widest -- and
    padding once here is what lets the walker index a cell without a length
    test at every read.
    """
    width = max((len(line) for line in code), default=0)
    return [line.ljust(width) for line in code]


def _find(grid: list[str], word: str) -> tuple[int, int, _Heading] | None:
    """Return where ``word`` is spelled on the grid, and the heading it runs in.

    Row-major over start cells, and for each cell the four headings in a
    fixed order, so a grid spelling the word twice picks the first
    deterministically.  The cell returned is the word's *first* character;
    the walk continues from just past its last.
    """
    for row, line in enumerate(grid):
        for col in range(len(line)):
            for heading in (_EAST, _SOUTH, _WEST, _NORTH):
                if _read_word(grid, row, col, heading) == word:
                    return row, col, heading
    return None


def _read_word(grid: list[str], row: int, col: int, heading: _Heading) -> str:
    """Return ``len(word)`` characters from ``(row, col)`` along ``heading``.

    Returns ``""`` when the run would leave the grid, so a word cannot be
    matched half off the edge.
    """
    drow, dcol = heading
    out: list[str] = []
    for _ in range(5):  # ``begin`` is the longest word.
        if not (0 <= row < len(grid) and 0 <= col < len(grid[0])):
            return "".join(out)
        out.append(grid[row][col])
        row += drow
        col += dcol
    return "".join(out)


def _scan(
    grid: list[str], row: int, col: int, heading: _Heading
) -> tuple[str, int, int]:
    """Read one command from ``(row, col)`` along ``heading``.

    Returns the command's text and the cell the terminating ``;`` sat on --
    the *pivot*, since a ``turn`` turns as if the semicolon were the command
    and the next one starts one cell beyond it.  That rule is what closes
    the wiki's cat loop: the ``;`` ending ``var c`` is the same cell the
    vertical ``turn right`` ends on, read from the other direction.

    A run that reaches the grid edge without a ``;`` ends there, with the
    last cell as the pivot.  Both cat examples finish on an edge-terminated
    ``end``, so the edge has to close a command; whether *walking on* from
    there is legal is the caller's, and only ``end`` survives it.

    Quotes shield their contents: a ``;`` inside ``"..."`` is a character of
    the string (the wiki says so explicitly), and ``'`` shields the single
    character after it, so ``';`` is a semicolon literal.
    """
    drow, dcol = heading
    height, width = len(grid), len(grid[0])
    text: list[str] = []
    quoted = False
    escape = False
    while 0 <= row < height and 0 <= col < width:
        c = grid[row][col]
        if escape:
            escape = False
        elif c == "'":
            escape = True
        elif c == '"':
            quoted = not quoted
        elif c == ";" and not quoted:
            return "".join(text), row, col
        text.append(c)
        row += drow
        col += dcol
    if quoted or escape:
        raise ValueError("unterminated string literal")
    # Stepped off the grid: back up.
    # the pivot an edge-terminated.
    return "".join(text), row - drow, col - dcol


class _Parser:
    """A recursive-descent reader for one Alight expression.

    Infix, strictly left to right, no precedence: the examples are all
    infix (``len{l}-0.5``, ``sign{x} > 0``) though the prose says postfix,
    and examples are ground truth.  So an expression is one operand
    followed by any number of ``<operator> <operand>`` pairs, each folded
    into the accumulated left-hand side as it is read.
    """

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def skip_space(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] == " ":
            self.pos += 1

    def peek(self) -> str:
        self.skip_space()
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def at_end(self) -> bool:
        return self.peek() == ""

    def word(self) -> str:
        """Read one alphanumeric identifier, or ``""`` if none is here."""
        self.skip_space()
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos].isalnum():
            self.pos += 1
        return self.text[start : self.pos]


# The binary operators, longest.
# character -- but the set is.
# drift on which characters are.
_BINARY = frozenset("+-*/=<>&|^")


def _parse_expr(p: _Parser) -> "_Expr":
    """Parse an expression: an operand, then ``op operand`` pairs, left to right."""
    node = _parse_operand(p)
    while True:
        c = p.peek()
        if c not in _BINARY or c == "":
            return node
        # A '-' directly before a digit.
        # sign: ``len{l}-0.5`` is a.
        # the only place a leading '-'.
        # unary minus, so there is no.
        p.pos += 1
        node = ("bin", c, node, _parse_operand(p))


def _parse_operand(p: _Parser) -> "_Expr":
    """Parse one operand: a literal, a list, a ``!``, a call, or a variable."""
    c = p.peek()
    if c == "":
        raise ValueError("expression ends early")
    if c == "!":
        p.pos += 1
        return ("not", _parse_operand(p))
    if c == "'":
        p.pos += 1
        if p.pos >= len(p.text):  # pragma: no cover - _scan catches it first
            # Unreachable from a real.
            # cell after it, so the command.
            # terminator or hits the grid.
            # "unterminated string literal".
            # ``_parse_operand`` is also.
            raise ValueError("character literal ends early")
        p.pos += 1
        return ("num", float(ord(p.text[p.pos - 1])))
    if c == '"':
        p.pos += 1
        chars: list[_Expr] = []
        while p.pos < len(p.text) and p.text[p.pos] != '"':
            chars.append(("num", float(ord(p.text[p.pos]))))
            p.pos += 1
        if p.pos >= len(p.text):  # pragma: no cover - _scan catches it first
            # Unreachable from a real.
            # ``_scan`` tracks the same.
            # never closes runs to the grid.
            # this message.
            # hand-built text, where.
            raise ValueError("unterminated string literal")
        p.pos += 1
        return ("list", chars)
    if c == "[":
        p.pos += 1
        return ("list", _parse_args(p, "]"))
    if c.isdigit() or c == ".":
        return ("num", _parse_number(p))
    name = p.word()
    if not name:
        raise ValueError(f"cannot parse operand at {p.text[p.pos :]!r}")
    if p.peek() == "{":
        p.pos += 1
        return ("call", name, _parse_args(p, "}"))
    if name in _SPECIALS:
        return ("special", name)
    return ("var", name)


def _parse_number(p: _Parser) -> float:
    """Read a decimal literal, which may be fractional (indices are ``k+0.5``)."""
    p.skip_space()
    start = p.pos
    while p.pos < len(p.text) and (p.text[p.pos].isdigit() or p.text[p.pos] == "."):
        p.pos += 1
    try:
        return float(p.text[start : p.pos])
    except ValueError:
        raise ValueError(f"bad number literal {p.text[start : p.pos]!r}") from None


def _parse_args(p: _Parser, close: str) -> list["_Expr"]:
    """Read a comma-separated argument or element list up to ``close``."""
    args: list[_Expr] = []
    if p.peek() == close:
        p.pos += 1
        return args
    while True:
        args.append(_parse_expr(p))
        c = p.peek()
        if c == close:
            p.pos += 1
            return args
        if c != ",":
            raise ValueError(f"expected {close!r} or ',' in {p.text!r}")
        p.pos += 1


# : A parsed expression tree.
# : and hashable, so a snapshot.
#: the tag.
type _Expr = tuple[object, ...]

# : One instant of a walk:.
# : is, which way it is going,.
# : is not in it: no command.
# : run rather than state, and.
#: a copy of the source.
# :.
# : ``vars`` is frozen to.
# : stores it, because a.
# : ``at`` writes in place, a.
# : a snapshot the cycle.
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
    raise HaltError(f"guard is not a boolean: {value!r}")


def _boolean(flag: bool) -> _Special:  # noqa: FBT001 - a conversion, not a mode
    """Return the special value for a Python boolean: ``left`` or ``right``.

    The boolean trap the lint guards against is a *mode selector* -- an
    argument the caller has to look up to read.  Here the argument is the
    datum being converted, so naming it at each call site would only repeat
    the function's own name.
    """
    return "left" if flag else "right"


def _is_num(value: _Value) -> TypeGuard[float]:
    """Whether a value is a number.

    A ``TypeGuard`` rather than a plain ``bool`` so that a caller's branch
    narrows: every arithmetic path below tests this first, and without the
    narrowing each one needed an ``assert isinstance`` afterwards purely to
    restate what the test had already established.
    """
    return isinstance(value, float | int) and not isinstance(value, bool)


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
        return _boolean(left == right)
    if not (_is_num(left) and _is_num(right)):
        return "right"
    return _boolean(left < right if op == "<" else left > right)


def _arith(op: str, left: _Value, right: _Value) -> _Value:
    """Apply an arithmetic operator, including the list forms.

    ``+`` concatenates two lists and ``*`` repeats one by a count, which is
    how the wiki defines them; every other combination of a list with a
    number is a type error.
    """
    if isinstance(left, list) and isinstance(right, list):
        if op != "+":
            raise HaltError(f"cannot apply {op!r} to two lists")
        return [*left, *right]
    if isinstance(left, list):
        return _repeat(op, left, right)
    if isinstance(right, list):
        # Repetition is commutative in.
        # ``"ab" * 3`` are the same.
        return _repeat(op, right, left)
    if not (_is_num(left) and _is_num(right)):
        raise HaltError(f"cannot apply {op!r} to {left!r} and {right!r}")
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if right == 0:
        raise HaltError("division by zero")
    return left / right


def _repeat(op: str, seq: list[_Value], count: _Value) -> _Value:
    """Repeat a list by a count, the only list-and-number operation there is."""
    if op != "*" or not _is_num(count):
        raise HaltError(f"cannot apply {op!r} to a list and {count!r}")
    if count != int(count) or count < 0:
        raise HaltError(f"list repeat count is not a whole number: {count!r}")
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
        raise HaltError(f"list index is not a number: {value!r}")
    slot = value - 0.5
    if slot != int(slot) or slot < 0:
        raise HaltError(f"list index is not 0.5 + k: {value!r}")
    return int(slot)


class _Machine:
    """Per-run Alight state: the grid and a stack of walks in progress.

    ``step()`` reads and executes exactly one command of the innermost
    walk, leaving its pointer on the cell the next command starts at.  A
    function call *pushes* a walker rather than running the callee inside
    the step that made it, so every command of every function reaches
    ``snapshot`` and a loop inside a called function is provable by
    :func:`esolangs.vm.run_until_halt_or_cycle`.
    """

    # : Whether a read past the end.
    # : rather than raising.
    # :.
    # : package norm and what.
    # : not, so an underfed program.
    # : instead of refusing, and a.
    #: that it happened.
    # :.
    # : Declared rather than.
    # : audited against every wiki.
    # : (``docs/limitations.md``,.
    # : would be a decision about.
    # : What was wrong was that.
    # : was false for seven.
    #: out which.
    eof_is_a_value = True

    def __init__(self, code: list[str] | str, io: IO) -> None:
        lines = code.splitlines() if isinstance(code, str) else list(code)
        self.grid = _grid(lines)
        self.io = io
        self.halted = False
        if not self.grid or not self.grid[0]:
            raise ValueError("empty program")
        start = _find(self.grid, "begin")
        if start is None:
            raise ValueError("program has no 'begin'")
        row, col, heading = start
        drow, dcol = heading
        # The walk resumes from just.
        # ``;`` that terminates it is.
        self.walkers = [_Walker(row + 5 * drow, col + 5 * dcol, heading, {})]

    @property
    def walker(self) -> _Walker:
        """The innermost walk: the one ``step`` advances."""
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

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Every walker, not only the.
        # caller standing somewhere.
        # that consumed a line is not a.
        return (
            tuple(walker.key() for walker in self.walkers),
            self.halted,
            self.io.position(),
        )

    # : ``ip`` is a cell of the.
    # : parts are a row and a.
    # : this a caller cannot tell.
    # : stack, which look identical.
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
            if isinstance(v, float | int) and not isinstance(v, bool)
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
        -- **builtins included** -- is replaced by its value, so an
        effectful ``at{l, i, v}`` runs exactly once no matter how many
        times the command is re-entered.  Re-evaluating the whole
        expression instead would fire it once per contained call:
        measured, ``set v at{l,0.5,67}+f{1}+g{2}`` would write three
        times.

        Left to right, innermost first, which is ``_eval``'s own order --
        so which ``HaltError`` fires first, and the order of any output a
        callee prints, are both unchanged.
        """
        tag = expr[0]
        if tag in ("num", "special", "var", "val"):
            return expr, None
        if tag == "not":
            inner, pending = self._reduce(cast(_Expr, expr[1]))
            return ("not", inner), pending
        if tag == "bin":
            left, pending = self._reduce(cast(_Expr, expr[2]))
            if pending is not None:
                return ("bin", expr[1], left, expr[3]), pending
            right, pending = self._reduce(cast(_Expr, expr[3]))
            return ("bin", expr[1], left, right), pending
        if tag == "list":
            items: list[_Expr] = []
            rest = list(cast(list[_Expr], expr[1]))
            while rest:
                item, pending = self._reduce(rest.pop(0))
                items.append(item)
                if pending is not None:
                    return ("list", [*items, *rest]), pending
            return ("list", items), None
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
        # A builtin with every argument.
        # value, so a re-entry never.
        return ("val", _builtin(name, [self._eval(a) for a in args])), None

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
            expr = _command_expr(text, word)
            if expr is None:
                return False
            walker.pending = expr
        if walker.returned is not None:
            walker.pending = _substitute_first(walker.pending, walker.returned)
            walker.returned = None
        walker.pending, name = self._reduce(walker.pending)
        if name is None:
            return False
        call = _first_call(walker.pending, name)
        self._push_call(name, [self._eval(a) for a in cast(list[_Expr], call[2])])
        return True

    def step(self) -> None:
        """Execute one command, leaving the pointer at the next one's start.

        A command holding calls takes more than one step: each step runs
        the leftmost-innermost user call by *pushing* a walker for it, and
        the value comes back rewritten into ``pending`` as a literal.  The
        command itself runs on the step where none is left, so no part of
        an Alight program executes inside another command's step.
        """
        if self.halted:
            return
        text, row, col = _scan(self.grid, self.row, self.col, self.heading)
        word = _Parser(text).word()
        if word == "end":
            if self._resolve(text, word):
                return
            self._finish(text)
            return
        if self._resolve(text, word):
            return
        heading = self.heading
        if word == "turn":
            heading = _turned(heading, left=_truth(self._eval_rest(text, "turn")))
        elif word == "skip":
            if _truth(self._eval_rest(text, "skip")):
                # Consume the next command.
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
            raise HaltError("walked off the grid")

    def _finish(self, text: str) -> None:
        """Run an ``end``: halt the program, or return from a call."""
        value = self._return_value(text)
        if len(self.walkers) == 1:
            self.halted = True
            return
        self.walkers.pop()
        self.walker.returned = value

    def _in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < len(self.grid) and 0 <= col < len(self.grid[0])

    def _eval_rest(self, text: str, word: str) -> _Value:
        """Evaluate the expression following a keyword.

        The parse still happens, so a trailing-text error is raised where
        it always was; the *value* comes from ``pending``, which holds the
        same expression with its calls already resolved.
        """
        p = _Parser(text)
        p.word()
        expr = _parse_expr(p)
        if not p.at_end():
            raise ValueError(f"trailing text after {word!r} expression: {text!r}")
        return self._eval(self.walker.pending or expr)

    def _exec(self, text: str, word: str) -> None:
        """Run one non-control command."""
        if word == "":
            # A command of nothing but.
            # cell between two semicolons.
            # a vertical command carry a.
            if text.strip():
                raise ValueError(f"cannot parse command {text!r}")
            return
        if word == "var":
            name = self._name(text)
            if name in self.vars:
                raise HaltError(f"variable {name!r} already exists")
            self.vars[name] = "nil"
            return
        if word == "set":
            p = _Parser(text)
            p.word()
            name = p.word()
            self._check_name(name)
            if name not in self.vars:
                raise HaltError(f"no such variable: {name!r}")
            expr = _parse_expr(p)
            if not p.at_end():
                raise ValueError(f"trailing text in set: {text!r}")
            self.vars[name] = self._eval(self.walker.pending or expr)
            return
        if word == "inp":
            self.vars[self._existing(text)] = self._read()
            return
        if word == "out":
            self._write(self.vars[self._existing(text)])
            return
        if word == "wait":
            # Evaluated for its errors and.
            # through this repo's IO and.
            self._eval_rest(text, "wait")
            return
        # A bare *call* is a command,.
        # discarded -- the reversed-cat.
        # Only a call, not any.
        # and a call is the only.
        p = _Parser(text)
        p.word()
        if p.peek() == "{":
            p.pos += 1
            args = _parse_args(p, "}")
            if p.at_end():
                # ``pending`` already holds.
                # the builtin's own effect, run.
                if self.walker.pending is not None:
                    self._eval(self.walker.pending)
                else:
                    self._call(word, [self._eval(a) for a in args])
                return
        raise ValueError(f"unknown command {word!r} in {text!r}")

    def _name(self, text: str) -> str:
        """Read the single variable name a ``var``/``inp``/``out`` names."""
        p = _Parser(text)
        p.word()
        name = p.word()
        self._check_name(name)
        if not p.at_end():
            raise ValueError(f"trailing text after variable name: {text!r}")
        return name

    def _check_name(self, name: str) -> None:
        if not name or not name.isalnum() or name in _RESERVED:
            raise ValueError(f"bad variable name {name!r}")

    def _existing(self, text: str) -> str:
        name = self._name(text)
        if name not in self.vars:
            raise HaltError(f"no such variable: {name!r}")
        return name

    def _read(self) -> _Value:
        """Read one character, or ``eof`` when the input is exhausted."""
        try:
            line = self.io.input_str()
        except EOFError:
            return "eof"
        # An empty line is a real line.
        # ``input_char`` and every.
        return float(ord(line[0])) if line else 0.0

    def _write(self, value: _Value) -> None:
        if not _is_num(value):
            raise HaltError(f"cannot output {value!r} as a character")
        if value != int(value) or not 0 <= value < 0x110000:
            raise HaltError(f"not a character code: {value!r}")
        self.io.print_char(chr(int(value)))

    def _eval(self, expr: _Expr) -> _Value:
        """Evaluate a parsed expression in this frame's namespace.

        The ``cast``s restate what the parser guarantees about each tag's
        payload.  ``_Expr`` is a plain tuple -- immutable and hashable, so a
        snapshot can hold one -- which costs the element types; the tag is
        what recovers them, and only the parser above ever builds one.
        """
        tag = expr[0]
        if tag == "num":
            return cast(float, expr[1])
        if tag == "val":
            # A call ``_reduce`` already.
            # re-entry of this command does.
            return cast(_Value, expr[1])
        if tag == "special":
            return cast(_Special, expr[1])
        if tag == "var":
            name = cast(str, expr[1])
            if name not in self.vars:
                raise HaltError(f"no such variable: {name!r}")
            return self.vars[name]
        if tag == "list":
            return [self._eval(e) for e in cast(list[_Expr], expr[1])]
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
        args = [self._eval(a) for a in cast(list[_Expr], expr[2])]
        return self._call(cast(str, expr[1]), args)

    def _call(self, name: str, args: list[_Value]) -> _Value:
        """Apply a builtin.  A user call never reaches here.

        ``step`` resolves every user call by pushing a walker for it and
        rewriting its value into the expression, so what survives to
        evaluation is builtins alone.
        """
        if name in _BUILTINS:
            return _builtin(name, args)
        raise HaltError(  # pragma: no cover - step resolves every user call
            f"unresolved call to {name!r}"
        )

    def _push_call(self, name: str, args: list[_Value]) -> None:
        """Start a user call by pushing a walker for its body.

        The callee is a separate walk with its own pointer and variables, so
        the Evil Hack -- a function's code sharing cells with the caller's --
        needs nothing special: whoever is walking reads the cell in their own
        direction and keeps their own frame until they hit an ``end``.
        """
        found = _find_func(self.grid, name)
        if found is None:
            raise HaltError(f"no such function: {name!r}")
        row, col, heading, params = found
        if len(params) != len(args):
            raise HaltError(
                f"function {name!r} takes {len(params)} arguments, got {len(args)}"
            )
        self.walkers.append(
            _Walker(row, col, heading, dict(zip(params, args, strict=True)))
        )

    def _return_value(self, text: str) -> _Value:
        """Evaluate the expression an ``end <value>`` returns, or ``nil``.

        Like the other commands, the value comes from ``pending`` when
        there is one -- ``end inner{n}+1`` holds a call, and that call is
        resolved by a pushed walker before this runs.
        """
        p = _Parser(text)
        p.word()
        if p.at_end():
            return "nil"
        expr = _parse_expr(p)
        if not p.at_end():
            raise ValueError(f"trailing text after end value: {text!r}")
        return self._eval(self.walker.pending or expr)


def _builtin(name: str, args: list[_Value]) -> _Value:
    """Apply one of the four builtin functions."""
    if name in ("trunc", "sign"):
        if len(args) != 1 or not _is_num(args[0]):
            raise HaltError(f"{name} takes one number")
        value = args[0]
        if name == "trunc":
            return float(int(value))
        return float((value > 0) - (value < 0))
    if len(args) < 1 or not isinstance(args[0], list):
        raise HaltError(f"{name} takes a list")
    seq = args[0]
    if name == "len":
        if len(args) == 1:
            return float(len(seq))
        if len(args) != 2 or not _is_num(args[1]):
            raise HaltError("len takes a list and optionally a count")
        count = args[1]
        if count != int(count) or count < 0:
            raise HaltError(f"len pad count is not a whole number: {count!r}")
        padding: list[_Value] = ["nil"] * int(count)
        return [*seq, *padding]
    if len(args) == 2:
        # Out of bounds reads as nil,.
        # *set* form raises.
        slot = _index(args[1])
        return seq[slot] if slot < len(seq) else "nil"
    if len(args) != 3:
        raise HaltError("at takes a list, an index, and optionally a value")
    slot = _index(args[1])
    if slot >= len(seq):
        raise HaltError(f"at index {args[1]!r} past the end of a {len(seq)}-list")
    if seq and isinstance(seq[0], list) != isinstance(args[2], list):
        raise HaltError("at would put the wrong type of value in a list")
    # Sets in place, against the.
    # docstring.
    # command is a pure no-op under.
    # nil and makes the example.
    # reverses.
    seq[slot] = args[2]
    return seq


def _find_func(
    grid: list[str], name: str
) -> tuple[int, int, _Heading, list[str]] | None:
    """Locate ``func <name>{...}`` on the grid; return its entry and parameters.

    Returns the cell and heading the body starts at -- just past the ``}`` --
    with the parameter names, or ``None`` when no such function is written.
    """
    for row, line in enumerate(grid):
        for col in range(len(line)):
            for heading in (_EAST, _SOUTH, _WEST, _NORTH):
                if _read_word(grid, row, col, heading)[:4] != "func":
                    continue
                drow, dcol = heading
                text, prow, pcol = _scan(grid, row, col, heading)
                p = _Parser(text)
                if p.word() != "func" or p.word() != name or p.peek() != "{":
                    continue
                p.pos += 1
                params = _func_params(p)
                if params is None:
                    continue
                del prow, pcol
                # The body begins one cell past.
                # semicolon, exactly as a.
                _, srow, scol = _scan(grid, row, col, heading)
                return srow + drow, scol + dcol, heading, params
    return None


def _func_params(p: _Parser) -> list[str] | None:
    """Read a ``func`` header's parameter names, or ``None`` if malformed."""
    params: list[str] = []
    if p.peek() == "}":
        p.pos += 1
        return params if p.at_end() else None
    while True:
        name = p.word()
        if not name or not name.isalnum() or name in _RESERVED:
            return None
        params.append(name)
        c = p.peek()
        p.pos += 1
        if c == "}":
            return params if p.at_end() else None
        if c != ",":
            return None


def _turned(heading: _Heading, *, left: bool) -> _Heading:
    """Return the heading after a quarter turn.

    ``left`` is counter-clockwise on the page.  The wiki's cat pins this:
    the true branch of ``turn c = eof`` travelling east reads ``end``
    *upward*, so a left turn from east is north.
    """
    i = _CLOCKWISE.index(heading)
    return _CLOCKWISE[(i - 1) % 4] if left else _CLOCKWISE[(i + 1) % 4]


def _is_call(text: str, word: str) -> bool:
    """Whether a command is a bare call, run for its effect."""
    p = _Parser(text)
    p.word()
    return bool(word) and word not in _RESERVED and p.peek() == "{"


def _command_expr(text: str, word: str) -> "_Expr | None":
    """Return the expression a command evaluates, or None if it has none.

    ``var``/``inp``/``out`` name a variable and evaluate nothing; ``set``
    names one and then evaluates; the rest are a keyword and an
    expression, or a bare call which is itself the expression.
    """
    p = _Parser(text)
    p.word()
    if word == "set":
        p.word()
    elif word not in ("turn", "skip", "wait", "end"):
        if not _is_call(text, word):
            return None
        p = _Parser(text)  # a bare call: parse the whole.
    if word == "end" and p.at_end():
        return None
    return _parse_expr(p)


def _substitute_first(expr: "_Expr", value: "_Value") -> "_Expr":
    """Replace the leftmost unresolved ``call`` node with ``value``.

    The leftmost remaining call *is* the one that just returned: a walker
    is pushed for it and nothing else runs until it does, so no identity
    tracking is needed.
    """
    replaced, _ = _replace_first(expr, value)
    return replaced


def _replace_first(expr: "_Expr", value: "_Value") -> tuple["_Expr", bool]:
    """Return ``expr`` with its first call replaced, and whether one was."""
    tag = expr[0]
    if tag in ("num", "special", "var", "val"):
        return expr, False
    if tag == "not":
        inner, done = _replace_first(cast(_Expr, expr[1]), value)
        return ("not", inner), done
    if tag == "bin":
        left, done = _replace_first(cast(_Expr, expr[2]), value)
        if done:
            return ("bin", expr[1], left, expr[3]), True
        right, done = _replace_first(cast(_Expr, expr[3]), value)
        return ("bin", expr[1], left, right), done
    if tag == "list":
        items = list(cast(list[_Expr], expr[1]))
        for i, item in enumerate(items):
            items[i], done = _replace_first(item, value)
            if done:
                return ("list", items), True
        return ("list", items), False
    args = list(cast(list[_Expr], expr[2]))
    for i, arg in enumerate(args):
        args[i], done = _replace_first(arg, value)
        if done:
            return ("call", expr[1], args), True
    return ("val", value), True


def _first_call(expr: "_Expr", name: str) -> "_Expr":
    """Return the leftmost ``call`` node to ``name`` in ``expr``.

    ``_reduce`` has already replaced every call to its left, so this is
    the one it stopped at.
    """
    found = _first_call_or_none(expr, name)
    if found is None:  # pragma: no cover - _reduce just found one
        raise HaltError(f"lost the pending call to {name!r}")
    return found


def _first_call_or_none(expr: "_Expr", name: str) -> "_Expr | None":
    """Return the leftmost ``call`` to ``name``, or None if there is none."""
    tag = expr[0]
    if tag in ("num", "special", "var", "val"):
        return None
    if tag == "not":
        return _first_call_or_none(cast(_Expr, expr[1]), name)
    if tag == "bin":
        return _first_call_or_none(cast(_Expr, expr[2]), name) or _first_call_or_none(
            cast(_Expr, expr[3]), name
        )
    if tag == "list":
        for item in cast(list[_Expr], expr[1]):
            found = _first_call_or_none(item, name)
            if found is not None:
                return found
        return None
    for arg in cast(list[_Expr], expr[2]):
        found = _first_call_or_none(arg, name)
        if found is not None:
            return found
    return expr if expr[1] == name else None


def _freeze(value: object) -> object:
    """Return a hashable copy of a value, for :meth:`_Machine.snapshot`.

    Variables hold lists, which are not hashable, and a snapshot that
    dropped them would call two different states equal -- so the freeze is
    recursive rather than a ``str()``.
    """
    if isinstance(value, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, tuple):
        # A pending expression is a.
        # lists -- a ``("list",.
        # evaluated ``at`` left behind.
        # a snapshot that a later.
        return tuple(_freeze(v) for v in value)
    return value


def run(code: list[str] | str, io: IO) -> None:
    """Run an Alight program to its ``end``."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read().splitlines(), IO())
