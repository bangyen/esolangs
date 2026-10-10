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
  ``a+b*c`` is ``(a+b)*c``.  Unary ``!`` appears in no example and is taken
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

"""

from fractions import Fraction
from typing import Literal, TypeGuard, cast

from esolangs._dialects import expression_syntax as validate_expression_syntax
from esolangs._dialects import list_update as validate_list_update
from esolangs._drive import drive
from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.grid_based._alight_helpers import _grid
from esolangs.interpreters.grid_based._alight_hints import Hint
from esolangs.interpreters.grid_based._alight_state import _equal, _freeze
from esolangs.interpreters.io import IO
from esolangs.interpreters.memory import parse_integer
from esolangs.interpreters.source_hints import keyword_hint, syntax_error

#: Headings as ``(drow, dcol)`` in screen coordinates -- row grows downward,
#: so a *left* turn (counter-clockwise on the page) takes east to north.
type _Heading = tuple[int, int]

_EAST: _Heading = (0, 1)
_WEST: _Heading = (0, -1)
_NORTH: _Heading = (-1, 0)
_SOUTH: _Heading = (1, 0)

# Turning is a rotation of this cycle: the next entry is a right turn, the
# previous a left one.  Written as a cycle rather than two dicts so the two
# directions cannot disagree.
_CLOCKWISE: tuple[_Heading, ...] = (_NORTH, _EAST, _SOUTH, _WEST)

#: The four special values, as their own singleton type.  A special is not a
#: number -- comparing one against a number is false rather than an error --
#: so it needs to be distinguishable from ``0``, which ``nil`` is not if the
#: specials are spelled as ints.
type _Special = Literal["nil", "eof", "left", "right"]
_SPECIALS: tuple[_Special, ...] = ("nil", "eof", "left", "right")

#: A value: a number, a list of values, or one of the four specials.
type _Value = Fraction | int | list["_Value"] | _Special

#: Reserved words a variable may not be named.  The wiki says variable names
#: are alphanumeric and "not reserved words" without listing them; these are
#: every word the grammar itself gives a meaning.
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
    for _ in range(5):  # ``begin`` is the longest word this is asked for
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
        elif c == "'" and not quoted:
            escape = True
        elif c == '"':
            quoted = not quoted
        elif c == ";" and not quoted:
            return "".join(text), row, col
        text.append(c)
        row += drow
        col += dcol
    if quoted or escape:
        raise Hint.SCANNED_LITERAL.error("unterminated string literal")
    # Stepped off the grid: back up onto the last in-bounds cell, which is
    # the pivot an edge-terminated command ends on.
    return "".join(text), row - drow, col - dcol


class _Parser:
    """Read infix (examples' ``len{l}-0.5``) or postfix (the prose's rule)."""

    def __init__(self, text: str, expression_syntax: str = "infix") -> None:
        self.expression_syntax = validate_expression_syntax(expression_syntax)
        self.text = text
        self.pos = 0

    def skip_space(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
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


# The binary operators, longest spelling first is unnecessary -- all are one
# character -- but the set is named so the parser and the evaluator cannot
# drift on which characters are operators.
_BINARY = frozenset("+-*/=<>&|^")


def _parse_expr(p: _Parser) -> "_Expr":
    """Parse an expression: an operand, then ``op operand`` pairs, left to right."""
    if p.expression_syntax == "postfix":
        return _parse_postfix(p)
    node = _parse_operand(p)
    while True:
        c = p.peek()
        if c not in _BINARY or c == "":
            return node
        # A '-' directly before a digit is still an operator here, never a
        # sign: ``len{l}-0.5`` is a subtraction, and an operand position is
        # the only place a leading '-' could be a negation.  Alight has no
        # unary minus, so there is no ambiguity to resolve.
        p.pos += 1
        node = ("bin", c, node, _parse_operand(p))


def _parse_postfix(p: _Parser) -> "_Expr":
    """Parse one postfix expression, stopping at an argument delimiter."""
    stack: list[_Expr] = []
    while (char := p.peek()) and char not in ",}]":
        if char in _BINARY or char == "!":
            p.pos += 1
            needed = 1 if char == "!" else 2
            if len(stack) < needed:
                raise Hint.OPERAND.error("postfix operator lacks operands")
            right = stack.pop()
            stack.append(
                ("not", right) if char == "!" else ("bin", char, stack.pop(), right)
            )
        else:
            stack.append(_parse_operand(p))
    if len(stack) != 1:
        raise Hint.EXPRESSION.error("postfix expression must leave one value")
    return stack[0]


def _parse_operand(p: _Parser) -> "_Expr":
    """Parse one operand: a literal, a list, a ``!``, a call, or a variable."""
    c = p.peek()
    if c == "":
        raise Hint.OPERAND.error("expression ends early")
    if c == "!":
        p.pos += 1
        return ("not", _parse_operand(p))
    if c == "'":
        p.pos += 1
        if p.pos >= len(p.text):  # pragma: no cover - _scan catches it first
            # Unreachable from a real program: a trailing ``'`` shields the
            # cell after it, so the command either runs on past its
            # terminator or hits the grid edge, where ``_scan`` raises
            # "unterminated string literal".  Kept as a guard because
            # ``_parse_operand`` is also called on hand-built text.
            raise Hint.CHARACTER_LITERAL.error("character literal ends early")
        p.pos += 1
        return ("num", Fraction(ord(p.text[p.pos - 1])))
    if c == '"':
        p.pos += 1
        chars: list[_Expr] = []
        while p.pos < len(p.text) and p.text[p.pos] != '"':
            chars.append(("num", Fraction(ord(p.text[p.pos]))))
            p.pos += 1
        if p.pos >= len(p.text):  # pragma: no cover - _scan catches it first
            # Unreachable from a real program, like the ``'`` guard above:
            # ``_scan`` tracks the same quoting, so a command whose ``"``
            # never closes runs to the grid edge and is refused there with
            # this message.  Kept because the parser is also called on
            # hand-built text, where nothing has scanned it.
            raise Hint.STRING_LITERAL.error("unterminated string literal")
        p.pos += 1
        return ("list", chars)
    if c == "[":
        p.pos += 1
        return ("list", _parse_args(p, "]"))
    start = p.pos
    name = p.word()
    if name and p.peek() == "{":
        p.pos += 1
        return ("call", name, _parse_args(p, "}"))
    p.pos = start
    if (c.isdecimal() and name.isdecimal()) or c == ".":
        return ("num", _parse_number(p))
    name = p.word()
    if not name:
        raise Hint.OPERAND_KIND.error(f"cannot parse operand at {p.text[p.pos :]!r}")
    if name in _SPECIALS:
        return ("special", name)
    return ("var", name)


def _parse_number(p: _Parser) -> Fraction:
    """Read a decimal literal, which may be fractional (indices are ``k+0.5``)."""
    p.skip_space()
    start = p.pos
    while p.pos < len(p.text) and (p.text[p.pos].isdecimal() or p.text[p.pos] == "."):
        p.pos += 1
    text = p.text[start : p.pos]
    whole, dot, tail = text.partition(".")
    try:
        if "." in tail:
            raise ValueError("multiple decimal points")
        return Fraction(parse_integer(whole + tail), 10 ** len(tail) if dot else 1)
    except ValueError:
        raise Hint.NUMBER.error(
            f"bad number literal {p.text[start : p.pos]!r}"
        ) from None


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
            raise Hint.ARGUMENTS.error(f"expected {close!r} or ',' in {p.text!r}")
        p.pos += 1


#: A parsed expression tree.  Tuples rather than classes: they are immutable
#: and hashable, so a snapshot can carry one, and the evaluator dispatches on
#: the tag.
type _Expr = tuple[object, ...]

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


class _Machine:
    """Per-run Alight state: the grid and a stack of walks in progress.

    ``step()`` reads and executes exactly one command of the innermost
    walk, leaving its pointer on the cell the next command starts at.  A
    function call *pushes* a walker rather than running the callee inside
    the step that made it, so every command of every function reaches
    ``snapshot`` and a loop inside a called function is provable by
    :func:`esolangs.vm.run_until_halt_or_cycle`.
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
        self.expression_syntax = validate_expression_syntax(expression_syntax)
        self.list_update = validate_list_update(list_update)
        lines = code.splitlines() if isinstance(code, str) else list(code)
        self.grid = _grid(lines)
        self.io = io
        self._input_reads = 0
        self.halted = False
        if not self.grid or not self.grid[0]:
            raise Hint.PROGRAM.error("empty program")
        start = _find(self.grid, "begin")
        if start is None:
            raise Hint.ENTRY.error("program has no 'begin'")
        row, col, heading = start
        drow, dcol = heading
        # The walk resumes from just past ``begin``'s last character; the
        # ``;`` that terminates it is the first thing ``_scan`` will see.
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
        return ("val", _builtin(name, values, self.list_update)), None

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
        walker.pending, name = self._reduce(walker.pending)
        if name is None:
            return False
        call = _first_call_or_none(walker.pending, name)
        if call is None:  # pragma: no cover - _reduce just found one
            raise HaltError(f"lost the pending call to {name!r}")
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
        word = _Parser(text, self.expression_syntax).word()
        if word == "end":
            if self._resolve(text, word):
                return
            self._finish()
            return
        if self._resolve(text, word):
            return
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

    def _finish(self) -> None:
        """Run an ``end``: halt the program, or return from a call."""
        value = self._return_value()
        if len(self.walkers) == 1:
            self.halted = True
            return
        self.walkers.pop()
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
        """Read one character, or ``eof`` when the input is exhausted."""
        try:
            value = self.io.input_char()
        except EOFError:
            return "eof"
        self._input_reads += 1
        return Fraction(value)

    def _write(self, value: _Value) -> None:
        if not _is_num(value):
            raise Hint.CHARACTER_OUTPUT.halt(
                "cannot output a nonnumeric value as a character"
            )
        if value != int(value) or not 0 <= value < 0x110000:
            raise Hint.CHARACTER_OUTPUT.halt("not a character code")
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


def _builtin(name: str, args: list[_Value], list_update: str) -> _Value:
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
    result = seq if list_update == "in_place" else seq.copy()
    result[slot] = args[2]
    return result


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
                # The body begins one cell past the ``func`` command's
                # semicolon, exactly as a ``turn``'s next command does.
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
    return (
        bool(word)
        and (word not in _RESERVED or word in (*_BUILTINS, *_SPECIALS))
        and p.peek() == "{"
    )


def _command_expr(
    text: str, word: str, expression_syntax: str = "infix"
) -> "_Expr | None":
    """Return the expression a command evaluates, or None if it has none.

    The caller passes only commands that evaluate: ``set`` names a variable
    and then evaluates; ``turn``/``skip``/``wait``/``end`` are a keyword and
    an expression; a bare call is itself the expression.
    """
    p = _Parser(text, expression_syntax)
    p.word()
    if word == "set":
        name = p.word()
        if not name or not name.isalnum() or name in _RESERVED:
            raise ValueError(f"bad variable name {name!r}")
    elif word not in ("turn", "skip", "wait", "end"):
        p = _Parser(text, expression_syntax)  # a bare call: parse the whole command
    if word == "end" and p.at_end():
        return None
    expr = _parse_expr(p)
    if not p.at_end():
        if word == "set":
            raise ValueError(f"trailing text in set: {text!r}")
        if word == "end":
            raise ValueError(f"trailing text after end value: {text!r}")
        if word in ("turn", "skip", "wait"):
            raise ValueError(f"trailing text after {word!r} expression: {text!r}")
        raise ValueError(f"unknown command {word!r} in {text!r}")
    return expr


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
    index = 1 if tag == "list" else 2
    children = list(cast(list[_Expr], expr[index]))
    for i, child in enumerate(children):
        children[i], done = _replace_first(child, value)
        if done:
            if tag == "list":
                return ("list", children), True
            return ("call", expr[1], children), True
    if tag == "list":
        return ("list", children), False
    return ("val", value), True


def _first_call_or_none(expr: "_Expr", name: str) -> "_Expr | None":
    """Return the leftmost ``call`` to ``name``, or None if there is none."""
    tag = expr[0]
    if tag in ("num", "special", "var", "val"):
        return None
    if tag == "not":
        children = [cast(_Expr, expr[1])]
    elif tag == "bin":
        children = [cast(_Expr, expr[2]), cast(_Expr, expr[3])]
    else:
        children = cast(list[_Expr], expr[1 if tag == "list" else 2])
    for child in children:
        found = _first_call_or_none(child, name)
        if found is not None:
            return found
    return expr if tag == "call" and expr[1] == name else None


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


if __name__ == "__main__":
    script_main(run, shape="strip")
