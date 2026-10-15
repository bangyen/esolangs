r"""Interpreter for Parenthesys.

A program is one expression: everything written side by side is
concatenated.  A character that is not syntax is a literal, a digit a
number and anything else a string; ``(x)`` prints, ``[...]`` reads,
saves, calls or defines by how many ``|`` it holds, and ``{x|y}`` loops.
Values are text, each a number or a string; variable and function names
are evaluated text.  The source compiles to flat ops, one step each; a
run of literal characters is one op.  The wiki's Hello world, cat, truth
machine and A+B run as stated; its 99 bottles needs ``[gt|[x]|1]`` for
``[gt|x|1]``, which takes the literal ``x``.  Its quine prints only its
643-character data half: the second loop starts with ``x`` already 88.
Its Bitwise Cyclic Tag interpreter does not parse: ``[[/|[-|[y]|[c]|4]|y]``
leaves a ``[`` open.

Commands:
    ``(x)`` prints x and returns it; ``$`` reads a line; ``{x}``, ``<x>``
    x as a number, a string; ``[x]`` variable x; ``[x|y]`` saves x in y;
    ``[f|x|y]`` calls f; ``[f|x|y|z]`` defines f on locals x, y; ``{x|y}``
    concatenates y's results while x is non-empty and non-zero; ``\c`` the
    string c.  Built-ins: ``+ - * / % ^ = ! gt lt ind len chr ord tpe``.

Input/output:
    ``$`` reads one line, a number when it is one.  Output is the printed
    text, with no separators.

Errors:
    ProgramError: An unmatched bracket; a ``|`` outside ``[]`` and ``{}``,
        or too many in one; a trailing ``\``.
    InputExhaustedError: ``$`` at EOF.
    HaltError: The spec's TypeError (arithmetic, ``{x}`` or a comparison
        on text that is no number), ValueError (division or ``%`` by 0, a
        fractional power, an index outside the string, a ``chr`` that is
        no character, ``ord`` of empty text) and AccessError (defining a
        built-in).

Decisions:
    * A concatenation is a number when any part is a number and the text
      is a valid number.  The spec glues pairs without an order; this rule
      gives every order the same type.
    * A number keeps its text: ``007`` prints ``007``.  Arithmetic gives
      plain decimals, no exponent or trailing zeros.  ``+ - * %`` and
      integer powers are exact; ``/`` and negative powers round to 28
      significant digits.  ``%`` takes the divisor's sign.
    * Each function has one local namespace, as the spec says, not one per
      call: a recursive call overwrites its caller's locals.  A body sees
      its own locals, then globals.
    * An undefined function returns the empty string ("does nothing").
    * Whitespace is literal: the Hello world prints its space.
    * The loop test's zero is any text that is a number equal to 0.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import (
    MAX_EMAX,
    MAX_PREC,
    MIN_EMIN,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    localcontext,
)
from typing import Literal

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO

_NUMBER = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")
_SYNTAX = frozenset("()[]{}<>|$\\")
_EXACT = Context(prec=MAX_PREC, Emax=MAX_EMAX, Emin=MIN_EMIN)
_ROUNDED = Context(prec=28, Emax=MAX_EMAX, Emin=MIN_EMIN)
_BUILTINS = frozenset(("+", "-", "*", "/", "%", "^", "=", "!", "gt", "lt", "ind"))
_BUILTINS |= {"len", "chr", "ord", "tpe"}
#: The brackets and the most ``|`` each may hold.
_PIPES = {"(": 0, "<": 0, "{": 1, "[": 3}
_CLOSE = {"(": ")", "<": ">", "{": "}", "[": "]"}

#: ``(text, is_number)``.
type _Value = tuple[str, bool]
_EMPTY: _Value = ("", False)
_ZERO: _Value = ("0", True)
_ONE: _Value = ("1", True)
#: The value stack as a linked list, top first.
type _Stack = tuple[_Item, _Stack] | None
#: ``(return op, function name)`` frames, innermost first.
type _Frames = tuple[tuple[int, str], _Frames] | None
type _State = tuple[int, _Stack, _Frames]
#: A function: its body's first op and its two local names.
type _Function = tuple[int, str, str]
#: Saving a variable, defining a function, or a call setting its locals.
type _Effect = (
    tuple[Literal["set"], str, _Value]
    | tuple[Literal["def"], str, _Function]
    | tuple[Literal["call"], str, tuple[tuple[str, _Value], tuple[str, _Value]]]
)
#: Texts as a linked list, newest first.
type _Pieces = tuple[str, _Pieces] | None


@dataclass(frozen=True, slots=True)
class _Acc:
    """A loop's results so far, newest first, and whether one is a number."""

    pieces: _Pieces = None
    number: bool = False


type _Item = _Value | _Acc


@dataclass(frozen=True, slots=True)
class _Op:
    """One step; ``at`` is its source offset."""

    kind: str
    at: int
    text: str = ""
    count: int = 0
    digit: bool = False
    target: int = 0


def _valid(text: str) -> bool:
    return _NUMBER.fullmatch(text) is not None


def _join(texts: list[str], *, number: bool) -> _Value:
    """Concatenate; a number when any part is one and the text is valid."""
    text = "".join(texts)
    return (text, number and _valid(text))


def _fail(at: int, message: str) -> ValueError:
    return ValueError(f"Parenthesys SyntaxError at offset {at}: {message}")


def _pipes(code: str) -> dict[int, int]:
    """Match brackets; each opener's offset maps to its top-level ``|`` count."""
    pipes: dict[int, int] = {}
    stack: list[int] = []
    k = 0
    while k < len(code):
        c = code[k]
        if c == "\\":
            if k + 1 == len(code):
                raise _fail(k, "a trailing \\")
            k += 2
            continue
        if c in _PIPES:
            stack.append(k)
            pipes[k] = 0
        elif c in ")]}>":
            if not stack or _CLOSE[code[stack[-1]]] != c:
                raise _fail(k, f"unmatched {c!r}")
            stack.pop()
        elif c == "|":
            if not stack or pipes[stack[-1]] == _PIPES[code[stack[-1]]]:
                raise _fail(k, "a '|' outside [] and {}, or too many")
            pipes[stack[-1]] += 1
        k += 1
    if stack:
        raise _fail(stack[-1], f"unmatched {code[stack[-1]]!r}")
    return pipes


@dataclass(slots=True)
class _Open:
    """An open bracket: which part it is in, that part's items and run."""

    opener: int
    pipes: int
    index: int = 0
    items: int = 0
    digit: bool = False
    run: str = ""
    run_digit: bool = False
    run_at: int = 0
    #: A loop's test op or a definition's skip op, patched at the close.
    patch: int = -1
    #: A loop's first condition op.
    start: int = 0


def compile_ops(code: str) -> list[_Op]:
    """Compile a source to ops; a malformed one raises ``ValueError``."""
    pipes = _pipes(code)
    ops: list[_Op] = []
    stack = [_Open(-1, 0)]

    def flush() -> None:
        top = stack[-1]
        if top.run:
            ops.append(_Op("lit", top.run_at, top.run, digit=top.run_digit))
            top.items += 1
            top.digit |= top.run_digit
            top.run, top.run_digit = "", False

    def end_part(at: int) -> None:
        flush()
        top = stack[-1]
        if top.items == 0:
            ops.append(_Op("lit", at))
        elif top.items > 1:
            ops.append(_Op("cat", at, count=top.items, digit=top.digit))
        top.items, top.digit = 0, False

    k = 0
    while k < len(code):
        c = code[k]
        top = stack[-1]
        if c == "\\" or c not in _SYNTAX:
            if not top.run:
                top.run_at = k
            top.run += code[k + 1] if c == "\\" else c
            # An escaped digit is a string; a bare one is a number.
            top.run_digit |= "0" <= c <= "9"
            k += 2 if c == "\\" else 1
            continue
        if c == "$":
            flush()
            ops.append(_Op("input", k))
            top.items += 1
        elif c in _PIPES:
            flush()
            if c == "{" and pipes[k]:
                ops.append(_Op("acc", k))
            stack.append(_Open(k, pipes[k], start=len(ops)))
        elif c == "|":
            end_part(k)
            top.index += 1
            if code[top.opener] == "{" or top.index == 3:
                top.patch = len(ops)
                ops.append(_Op("test" if code[top.opener] == "{" else "def", k))
        else:
            end_part(k)
            stack.pop()
            if c == ")":
                ops.append(_Op("print", k))
            elif c == ">":
                ops.append(_Op("str", k))
            elif c == "}" and not top.pipes:
                ops.append(_Op("num", k))
            elif c == "}":
                ops.append(_Op("add", k))
                ops.append(_Op("jump", k, target=top.start))
                ops[top.patch] = _Op("test", ops[top.patch].at, target=len(ops))
                ops.append(_Op("done", k))
            elif top.pipes == 3:
                ops.append(_Op("ret", k))
                ops[top.patch] = _Op("def", ops[top.patch].at, target=len(ops))
            else:
                ops.append(_Op(("get", "set", "call")[top.pipes], k))
            stack[-1].items += 1
        k += 1
    end_part(len(code))
    return ops


def _type_error(text: str) -> HaltError:
    return HaltError(f"Parenthesys TypeError: {text!r} is not a valid number")


def _value_error(message: str) -> HaltError:
    return HaltError(f"Parenthesys ValueError: {message}")


def _number(value: _Value) -> Decimal:
    if not _valid(value[0]):
        raise _type_error(value[0])
    return Decimal(value[0])


def _integer(value: _Value, name: str) -> int:
    number = _number(value)
    if number != number.to_integral_value():
        raise _value_error(f"{name} needs an integer, got {value[0]}")
    return int(number)


def _show(number: Decimal) -> _Value:
    """A result as plain decimal text: no exponent, no trailing zeros."""
    if not number:
        return _ZERO
    return (format(number.normalize(_EXACT), "f"), True)


def _power(a: Decimal, b: Decimal) -> Decimal:
    if b != b.to_integral_value():
        raise _value_error(f"a fractional power {b}")
    k = int(b)
    if k >= 0:
        return Decimal(1) if k == 0 else a**k
    if not a:
        raise _value_error("0 to a negative power")
    with localcontext(_ROUNDED):
        return 1 / a**-k


def _arithmetic(name: str, a: Decimal, b: Decimal) -> Decimal:
    if name == "+":
        return a + b
    if name == "-":
        return a - b
    if name == "*":
        return a * b
    if name == "^":
        return _power(a, b)
    if not b:
        raise _value_error(f"{name} by 0")
    if name == "/":
        with localcontext(_ROUNDED):
            return a / b
    rest = a % b
    return rest + b if rest and (rest < 0) != (b < 0) else rest


def _builtin(name: str, x: _Value, y: _Value) -> _Value:
    """Apply a built-in function to ``x`` and ``y``."""
    if name in ("=", "!"):
        return _ONE if (x[0] == y[0]) == (name == "=") else _ZERO
    if name == "tpe":
        return _ONE if x[1] == y[1] else _ZERO
    if name == "len":
        return (str(len(x[0])), True)
    if name == "ord":
        if not x[0]:
            raise _value_error("ord of empty text")
        return (str(ord(x[0][0])), True)
    if name == "ind":
        index = _integer(x, name)
        if not 0 <= index < len(y[0]):
            raise _value_error(f"index {index} outside {y[0]!r}")
        return (y[0][index], False)
    if name == "chr":
        code = _integer(x, name)
        if not 0 <= code <= 0x10FFFF or 0xD800 <= code <= 0xDFFF:
            raise _value_error(f"chr {code} is no character")
        return (chr(code), False)
    a, b = _number(x), _number(y)
    if name in ("gt", "lt"):
        return _ONE if (a > b if name == "gt" else a < b) else _ZERO
    with localcontext(_EXACT):
        try:
            return _show(_arithmetic(name, a, b))
        except (InvalidOperation, DivisionByZero) as exc:
            raise _value_error(f"{a} {name} {b}") from exc


def _falsy(value: _Value) -> bool:
    return not value[0] or (_valid(value[0]) and not Decimal(value[0]))


def _pop(stack: _Stack) -> tuple[_Value, _Stack]:
    assert stack is not None
    item, rest = stack
    assert not isinstance(item, _Acc)
    return item, rest


def _pop_acc(stack: _Stack) -> tuple[_Acc, _Stack]:
    assert stack is not None
    item, rest = stack
    assert isinstance(item, _Acc)
    return item, rest


def _advance_value(op: _Op, stack: _Stack, line: str | None) -> _Stack:
    """Run a literal, concatenation, ``$``, ``{x}`` or ``<x>`` op."""
    kind = op.kind
    if kind == "lit":
        return ((op.text, op.digit and _valid(op.text)), stack)
    if kind == "input":
        assert line is not None
        return ((line, _valid(line)), stack)
    if kind in ("num", "str"):
        item, stack = _pop(stack)
        if kind == "num" and not _valid(item[0]):
            raise _type_error(item[0])
        return ((item[0], kind == "num"), stack)
    texts: list[str] = []
    number = op.digit
    for _ in range(op.count):
        item, stack = _pop(stack)
        texts.append(item[0])
        number |= item[1]
    return (_join(texts[::-1], number=number), stack)


def _advance_loop(op: _Op, stack: _Stack, nxt: int) -> tuple[_Stack, int]:
    """Run a ``{x|y}`` op: start, test, collect a result, or finish."""
    kind = op.kind
    if kind == "acc":
        return (_Acc(), stack), nxt
    if kind == "test":
        item, stack = _pop(stack)
        return stack, op.target if _falsy(item) else nxt
    if kind == "add":
        item, stack = _pop(stack)
        acc, stack = _pop_acc(stack)
        return (_Acc((item[0], acc.pieces), acc.number or item[1]), stack), nxt
    if kind == "jump":
        return stack, op.target
    acc, stack = _pop_acc(stack)
    texts: list[str] = []
    node = acc.pieces
    while node is not None:
        texts.append(node[0])
        node = node[1]
    return (_join(texts[::-1], number=acc.number), stack), nxt


def _advance(
    state: _State,
    ops: list[_Op],
    line: str | None = None,
    value: _Value | None = None,
    function: _Function | None = None,
) -> tuple[_State, tuple[_Effect, ...], str | None]:
    """Return the state after one op, its effects, and what it prints.

    Pure: ``$``'s line, the variable ``[x]`` names and the function
    ``[f|x|y]`` calls arrive as arguments.
    """
    ip, stack, frames = state
    op = ops[ip]
    kind = op.kind
    nxt = ip + 1
    effects: tuple[_Effect, ...] = ()
    out = None
    if kind in ("lit", "cat", "input", "num", "str"):
        stack = _advance_value(op, stack, line)
    elif kind in ("acc", "test", "add", "jump", "done"):
        stack, nxt = _advance_loop(op, stack, nxt)
    elif kind == "print":
        out = _pop(stack)[0][0]
    elif kind == "get":
        assert value is not None
        stack = (value, _pop(stack)[1])
    elif kind == "set":
        name, stack = _pop(stack)
        effects = (("set", name[0], _pop(stack)[0]),)
    elif kind == "ret":
        assert frames is not None
        (nxt, _), frames = frames
    else:
        y, stack = _pop(stack)
        x, stack = _pop(stack)
        f, stack = _pop(stack)
        if kind == "def":
            if f[0] in _BUILTINS:
                raise HaltError(f"Parenthesys AccessError: {f[0]!r} is built in")
            effects = (("def", f[0], (ip + 1, x[0], y[0])),)
            stack, nxt = (f, stack), op.target
        elif f[0] in _BUILTINS:
            stack = (_builtin(f[0], x, y), stack)
        elif function is None:
            stack = (_EMPTY, stack)
        else:
            effects = (("call", f[0], ((function[1], x), (function[2], y))),)
            frames = ((nxt, f[0]), frames)
            nxt = function[0]
    return (nxt, stack, frames), effects, out


class _Machine:
    """The shell around :func:`_advance`: variables, functions, I/O."""

    def __init__(self, code: str, io: IO) -> None:
        self.ops = compile_ops(code)
        self.io = io
        self.end = len(code)
        self.state: _State = (0, None, None)
        self.globals: dict[str, _Value] = {}
        self.functions: dict[str, _Function] = {}
        #: Each function's one local namespace, set by its latest call.
        self.locals: dict[str, dict[str, _Value]] = {}

    @property
    def halted(self) -> bool:
        return self.state[0] >= len(self.ops)

    @property
    def ip(self) -> int:
        """The next op's source offset; the source length once halted."""
        return self.end if self.halted else self.ops[self.state[0]].at

    @property
    def stack(self) -> list[object]:
        """The value stack's texts, bottom first."""
        texts: list[object] = []
        node = self.state[1]
        while node is not None:
            item, node = node
            texts.append(item[0] if isinstance(item, tuple) else "<loop>")
        return texts[::-1]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            *self.state,
            frozenset(self.globals.items()),
            frozenset(self.functions.items()),
            frozenset((f, frozenset(v.items())) for f, v in self.locals.items()),
            self.io.progress(),
        )

    def _scope(self, name: str) -> dict[str, _Value]:
        """The running function's locals if ``name`` is one, else globals."""
        frames = self.state[2]
        if frames is not None:
            names = self.locals.get(frames[0][1], {})
            if name in names:
                return names
        return self.globals

    def step(self) -> None:
        """Run one op, fetching what it reads first."""
        ip, stack, _ = self.state
        if ip >= len(self.ops):
            return
        kind = self.ops[ip].kind
        line = value = function = None
        if kind == "input":
            line = self.io.input_str()
        elif kind == "get" and stack is not None:
            key = _pop(stack)[0][0]
            value = self._scope(key).get(key, _ZERO)
        elif kind == "call":
            f = _pop(_pop(_pop(stack)[1])[1])[0]
            function = self.functions.get(f[0])
        self.state, effects, out = _advance(self.state, self.ops, line, value, function)
        for effect in effects:
            match effect:
                case ("set", name, item):
                    self._scope(name)[name] = item
                case ("def", name, body):
                    self.functions[name] = body
                case ("call", name, pairs):
                    self.locals[name] = dict(pairs)
        if out is not None:
            self.io.print_str(out)


def run(code: str, io: IO) -> None:
    """Run a Parenthesys program."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
