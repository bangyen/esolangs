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
  is not ``left``/``right``, an unknown function, and exceeding the call
  depth cap -- raise ``HaltError``.
* **``wait`` is a nop.**  Its argument is evaluated (so an error in it still
  fires) and discarded: a real sleep is unobservable through this repo's I/O
  and would hang the suite.
* **Multiple ``begin``s.**  The first in row-major order wins; the rest are
  ordinary grid text, which is what the Evil Hack already makes of any
  overlap.
* **Step cap.**  A walk is bounded (:data:`_STEP_CAP`) so that a program
  looping over a fixed grid terminates rather than hanging the fuzz suite.
"""

import sys
from typing import Literal, TypeGuard, cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

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
type _Value = float | list["_Value"] | _Special

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

# Walking bound.  The language has no halt guarantee of its own -- the cat
# examples loop until EOF -- so a program whose guard never fires walks
# forever.  The fuzz and robustness suites feed random grids, so the walk is
# capped and a program that exceeds it raises rather than hangs.  The
# generated programs here are straight lines of a few hundred commands, so
# this is three orders of magnitude of headroom.
_STEP_CAP = 1_000_000

# Depth cap on nested calls, for the same reason: a function that calls
# itself unconditionally would otherwise exhaust the Python stack with a
# RecursionError rather than a HaltError.
_CALL_DEPTH_CAP = 200


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
    # Stepped off the grid: back up onto the last in-bounds cell, which is
    # the pivot an edge-terminated command ends on.
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

    def _skip_space(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] == " ":
            self.pos += 1

    def peek(self) -> str:
        self._skip_space()
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def at_end(self) -> bool:
        return self.peek() == ""

    def word(self) -> str:
        """Read one alphanumeric identifier, or ``""`` if none is here."""
        self._skip_space()
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
            # Unreachable from a real program: a trailing ``'`` shields the
            # cell after it, so the command either runs on past its
            # terminator or hits the grid edge, where ``_scan`` raises
            # "unterminated string literal".  Kept as a guard because
            # ``_parse_operand`` is also called on hand-built text.
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
            # Unreachable from a real program, like the ``'`` guard above:
            # ``_scan`` tracks the same quoting, so a command whose ``"``
            # never closes runs to the grid edge and is refused there with
            # this message.  Kept because the parser is also called on
            # hand-built text, where nothing has scanned it.
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
    p._skip_space()  # noqa: SLF001 - the parser's own cursor
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
#: ``vars`` is frozen to nested tuples by :func:`_freeze` before a snapshot
#: stores it, because a variable may hold a list -- and since three-argument
#: ``at`` writes in place, a live reference would let a later command mutate
#: a snapshot the cycle detector had already banked.
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
        # Repetition is commutative in the spelling: ``3 * "ab"`` and
        # ``"ab" * 3`` are the same list.
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
    """Per-run Alight state: the grid, the pointer, and the variable frames.

    ``step()`` reads and executes exactly one command, leaving the pointer on
    the cell the next command starts at.  A function call runs to completion
    inside the step that made it -- the callee is a separate walk with its own
    pointer and namespace -- so ``snapshot`` describes the caller between
    commands, never mid-call.
    """

    def __init__(self, code: list[str] | str, io: IO) -> None:
        lines = code.splitlines() if isinstance(code, str) else list(code)
        self.grid = _grid(lines)
        self.io = io
        self.halted = False
        self.steps = 0
        if not self.grid or not self.grid[0]:
            raise ValueError("empty program")
        start = _find(self.grid, "begin")
        if start is None:
            raise ValueError("program has no 'begin'")
        row, col, heading = start
        drow, dcol = heading
        # The walk resumes from just past ``begin``'s last character; the
        # ``;`` that terminates it is the first thing ``_scan`` will see.
        self.row = row + 5 * drow
        self.col = col + 5 * dcol
        self.heading = heading
        self.vars: dict[str, _Value] = {}
        self.depth = 0

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.row,
            self.col,
            self.heading,
            _freeze(self.vars),
            self.halted,
            self.io.position(),
        )

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
        """No operand stack in this language."""
        return []

    def step(self) -> None:
        """Execute one command, leaving the pointer at the next one's start."""
        if self.halted:
            return
        self.steps += 1
        if self.steps > _STEP_CAP:
            raise HaltError(f"program exceeded {_STEP_CAP} commands")
        text, row, col = _scan(self.grid, self.row, self.col, self.heading)
        word = _Parser(text).word()
        if word == "end":
            self.halted = True
            return
        heading = self.heading
        if word == "turn":
            heading = _turned(heading, left=_truth(self._eval_rest(text, "turn")))
        elif word == "skip":
            if _truth(self._eval_rest(text, "skip")):
                # Consume the next command without running it, from just
                # past this one's pivot.
                drow, dcol = heading
                _, row, col = _scan(self.grid, row + drow, col + dcol, heading)
        else:
            self._exec(text, word)
        drow, dcol = heading
        self.row, self.col, self.heading = row + drow, col + dcol, heading
        if not self._in_bounds(self.row, self.col):
            raise HaltError("walked off the grid")

    def _in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < len(self.grid) and 0 <= col < len(self.grid[0])

    def _eval_rest(self, text: str, word: str) -> _Value:
        """Parse and evaluate the expression following a keyword."""
        p = _Parser(text)
        p.word()
        expr = _parse_expr(p)
        if not p.at_end():
            raise ValueError(f"trailing text after {word!r} expression: {text!r}")
        return self._eval(expr)

    def _exec(self, text: str, word: str) -> None:
        """Run one non-control command."""
        if word == "":
            # A command of nothing but whitespace is the wiki's nop.  Every
            # cell between two semicolons is legal there, which is what lets
            # a vertical command carry a blank row.
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
            self.vars[name] = self._eval(expr)
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
            self._eval_rest(text, "wait")
            return
        # A bare *call* is a command, run for its effect and its value
        # discarded -- the reversed-cat example's ``at{l, len{l}-0.5, c};``.
        # Only a call, not any expression: the example shows no other kind,
        # and a call is the only expression that can have an effect at all.
        p = _Parser(text)
        p.word()
        if p.peek() == "{":
            p.pos += 1
            args = _parse_args(p, "}")
            if p.at_end():
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
        # An empty line is a real line with no character on it; 0 is what
        # ``input_char`` and every other interpreter here return for one.
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
        """Apply a builtin or a grid-defined function."""
        if name in ("at", "len", "trunc", "sign"):
            return _builtin(name, args)
        return self._user_call(name, args)

    def _user_call(self, name: str, args: list[_Value]) -> _Value:
        """Run a ``func`` defined on the grid, in a fresh namespace.

        The callee is a separate walk with its own pointer and variables, so
        the Evil Hack -- a function's code sharing cells with the caller's --
        needs nothing special: whoever is walking reads the cell in their own
        direction and keeps their own frame until they hit an ``end``.
        """
        if self.depth >= _CALL_DEPTH_CAP:
            raise HaltError(f"call depth exceeded {_CALL_DEPTH_CAP}")
        found = _find_func(self.grid, name)
        if found is None:
            raise HaltError(f"no such function: {name!r}")
        row, col, heading, params = found
        if len(params) != len(args):
            raise HaltError(
                f"function {name!r} takes {len(params)} arguments, got {len(args)}"
            )
        callee = object.__new__(_Machine)
        callee.grid = self.grid
        callee.io = self.io
        callee.halted = False
        callee.steps = 0
        callee.row, callee.col, callee.heading = row, col, heading
        callee.vars = dict(zip(params, args, strict=True))
        callee.depth = self.depth + 1
        while not callee.halted:
            text, prow, pcol = _scan(
                callee.grid, callee.row, callee.col, callee.heading
            )
            if _Parser(text).word() == "end":
                return callee._return_value(text)  # noqa: SLF001 - same class
            callee.step()
            self.steps += callee.steps
            callee.steps = 0
            if self.steps > _STEP_CAP:
                raise HaltError(f"program exceeded {_STEP_CAP} commands")
            del prow, pcol
        return "nil"  # pragma: no cover - the loop returns at the ``end``

    def _return_value(self, text: str) -> _Value:
        """Evaluate the expression an ``end <value>`` returns, or ``nil``."""
        p = _Parser(text)
        p.word()
        if p.at_end():
            return "nil"
        expr = _parse_expr(p)
        if not p.at_end():
            raise ValueError(f"trailing text after end value: {text!r}")
        return self._eval(expr)


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
        # Out of bounds reads as nil, per the wiki -- only the three-argument
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
    # Sets in place, against the prose's "returns a copy" -- see the module
    # docstring.  The reversed-cat example's bare ``at{l, len{l}-0.5, c};``
    # command is a pure no-op under copy semantics, which leaves ``l`` all
    # nil and makes the example crash on its own first ``out``; in place it
    # reverses.  The example wins.
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
