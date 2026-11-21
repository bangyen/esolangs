r"""Interpreter for Flipscript.

A program is one statement per line.  Execution starts at the topmost
``start(d)`` line moving down (``d`` 0) or up (``d`` 1) and runs one line
at a time in the current direction; it halts on ``stop`` or on leaving the
first or last line.  Lines are checked only when encountered, so
unreachable lines are comments.

Commands:
    ``start(d)``               no-op when met again; takes no modifier
    ``stop``                   halt
    ``flip(cond)``             reverse the direction if ``cond`` holds
    ``jump e``                 move ``e`` lines in the current direction
    ``output(x,...)``          print the items; ``new`` is a newline
    ``num N = e``              assign a number (``e`` may be ``input``)
    ``string N = s``           assign a string (``s`` may be ``input``)
    ``up`` / ``down``          prefix: run only while moving that way
    ``decay(e)``               prefix after ``up``/``down``: run at most ``e`` times

    ``N(e)`` names the variable ``N`` followed by ``e``'s printed value.
    Math ``+ - * / %`` and conditions ``== != > < >= <= $= $!= || &&``
    evaluate strictly left to right, with no parentheses and no spaces.

Input/output:
    Each ``input`` reads one line.  A number is a signed decimal; a string
    is the line itself.  ``output`` prints numbers as integers when whole,
    otherwise as the shortest round-tripping decimal.

Errors:
    ProgramError: no ``start`` line or a malformed one, or an executed line
    that does not parse or exceeds 4000 characters.
    InputExhaustedError: an ``input`` at EOF.
    ArgumentError: a ``num`` input line that is not a decimal number.
    HaltError: an unassigned variable, a type mismatch, division or
    remainder by zero, a non-finite result, a jump that is not a positive
    whole number, or a decay that is not whole.

Decisions:
    * A num is an IEEE double: the page leaves the size to the
      implementation and its brainfuck interpreter floors with
      ``0-X%1+X``, which needs a fractional part and floor remainder.
    * After a flip the next line is the neighbour in the new direction: the
      parity example prints "The number is even" two lines above its flip.
    * Each ``input`` reads one line, since the password example reads a
      string and a number in turn; a ``num`` line may carry surrounding
      whitespace.  EOF raises, as the page gives no value for it.
    * ``decay(k)`` runs its statement the first ``k`` times it is met --
      "the maximum number of times a statement can be executed" -- and a
      line whose ``up``/``down`` guard fails is not met, as the guard comes
      first.  The count is fixed when first met.
    * A guarded line is parsed only when its guard passes ("lines with
      modifiers may additionally not be error checked").
    * ``||`` and ``&&`` evaluate every comparison; the page names no
      short circuit.
    * Lines are stripped of surrounding whitespace; the page's code blocks
      indent every line by one space.
    * The page's brainfuck interpreter is not run as a test: it assigns
      without a type (``down CODELOC = ...``) and reads the undefined
      ``LOOPCOUNTER``, both errors under the page's own rules.
"""

import math
import re
from collections.abc import Mapping
from functools import lru_cache
from typing import Any, NamedTuple

from esolangs.exceptions import ArgumentError, HaltError, ProgramError
from esolangs.languages.flipscript.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._input_retry import RejectedInput
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import IO, _BufferedOutput
from esolangs.runtime.source_hints import syntax_error

_MAX_LINE = 4000
_START = re.compile(r"start\((.*)\)")
_TOKEN = re.compile(
    r'(?P<num>[0-9]+(?:\.[0-9]+)?)|(?P<str>"[^"]*")|(?P<name>[A-Z]+)'
    r"|(?P<op>\$!=|\$=|==|!=|>=|<=|\|\||&&|[-+*/%<>()])"
)
_ASSIGN = re.compile(r"(num|string) ([A-Z]+(?:\(.*\))?) *= *(.*)")
_NUMBER_INPUT = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)")
_MATH = frozenset("+-*/%")
_COMPARE = frozenset({"==", "!=", ">", "<", ">=", "<=", "$=", "$!="})
_LOGIC = frozenset({"||", "&&"})

type _Value = float | str
#: A variable reference: its name and, for ``N(e)``, the suffix expression.
type _Ref = tuple[str, "_Expr | None"]
#: An operand (a literal or a reference), then ``(operator, operand)`` pairs.
type _Expr = tuple[object, tuple[tuple[str, object], ...]]
type _Cond = tuple[
    tuple[_Expr, str, _Expr], tuple[tuple[str, tuple[_Expr, str, _Expr]], ...]
]
#: ``(direction, line index)``: +1 runs down, -1 up.
type _State = tuple[int, int]


class _Line(NamedTuple):
    """A line's modifiers and its unparsed statement."""

    guard: int  # 0 unguarded, else the direction it requires
    decay: "_Expr | None"
    body: str


class _Stmt(NamedTuple):
    """A parsed statement: its kind and operands."""

    kind: str  # "", "start", "stop", "flip", "jump", "output", "assign"
    arg: object = None
    ref: "_Ref | None" = None
    typ: str = ""


def _bad(text: str, hint: str) -> ValueError:
    return syntax_error(f"cannot parse {text!r}", hint, error_type=ProgramError)


def _tokens(text: str) -> list[tuple[str, str]]:
    """Split an expression; any character outside a token is an error."""
    out: list[tuple[str, str]] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if m is None:
            raise _bad(text, "operators take no spaces; names are uppercase")
        kind = m.lastgroup or ""
        out.append((kind, m.group()))
        pos = m.end()
    return out


class _Reader:
    """A cursor over one expression's tokens."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.toks = _tokens(text)
        self.pos = 0

    def peek(self) -> tuple[str, str] | None:
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def take(self) -> tuple[str, str]:
        tok = self.peek()
        if tok is None:
            raise _bad(self.text, "an operator needs an operand after it")
        self.pos += 1
        return tok

    def operand(self) -> object:
        kind, text = self.take()
        if kind == "num":
            return float(text)
        if kind == "str":
            return text[1:-1]
        if kind != "name":
            raise _bad(self.text, "expected a number, string or variable")
        index = None
        if self.peek() == ("op", "("):
            self.pos += 1
            index = self.math()
            if self.take() != ("op", ")"):
                raise _bad(self.text, "close a variable suffix with )")
        return (text, index)

    def math(self) -> _Expr:
        first = self.operand()
        rest: list[tuple[str, object]] = []
        while (tok := self.peek()) is not None and tok[1] in _MATH:
            self.pos += 1
            rest.append((tok[1], self.operand()))
        return first, tuple(rest)

    def compare(self) -> tuple[_Expr, str, _Expr]:
        left = self.math()
        tok = self.take()
        if tok[1] not in _COMPARE:
            raise _bad(self.text, "a condition compares two values")
        return left, tok[1], self.math()

    def done(self) -> None:
        if self.peek() is not None:
            raise _bad(self.text, "unexpected text after the expression")


def _expr(text: str) -> _Expr:
    reader = _Reader(text)
    value = reader.math()
    reader.done()
    return value


def _cond(text: str) -> _Cond:
    reader = _Reader(text)
    first = reader.compare()
    rest = []
    while (tok := reader.peek()) is not None and tok[1] in _LOGIC:
        reader.pos += 1
        rest.append((tok[1], reader.compare()))
    reader.done()
    return first, tuple(rest)


def _ref(text: str) -> _Ref:
    reader = _Reader(text)
    value = reader.operand()
    reader.done()
    if not isinstance(value, tuple):
        raise _bad(text, "assign to an uppercase name")
    return value


def _split_items(text: str) -> list[str]:
    """Split ``output`` items at commas outside strings and suffixes."""
    items: list[str] = []
    cur: list[str] = []
    depth, quoted = 0, False
    for ch in text:
        if ch == '"':
            quoted = not quoted
        elif not quoted and ch in "()":
            depth += 1 if ch == "(" else -1
        if ch == "," and not quoted and depth == 0:
            items.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    items.append("".join(cur))
    return items


@lru_cache(maxsize=1 << 16)
def _modifiers(raw: str) -> _Line:
    """Split a line into its guard, decay and statement text."""
    if len(raw) > _MAX_LINE:
        raise syntax_error(
            f"a line of {len(raw)} characters",
            f"keep lines to {_MAX_LINE}",
            error_type=ProgramError,
        )
    body = raw.strip()
    guard = 0
    for word, way in (("up ", -1), ("down ", 1)):
        if body.startswith(word):
            guard, body = way, body[len(word) :].lstrip()
            break
    decay = None
    if body.startswith("decay("):
        close = body.find(") ")
        if close < 0:
            raise _bad(body, "write decay(n) statement")
        decay, body = _expr(body[6:close]), body[close + 2 :].lstrip()
    if (guard or decay is not None) and (
        _START.fullmatch(body) or body.startswith(("up ", "down ", "decay("))
    ):
        raise _bad(raw.strip(), "start takes no modifier; up/down precede decay")
    return _Line(guard, decay, body)


@lru_cache(maxsize=1 << 16)
def _statement(body: str) -> _Stmt:
    """Parse a statement, rejecting anything the page does not define."""
    if not body:
        return _Stmt("")
    if _START.fullmatch(body):
        return _Stmt("start")
    if body == "stop":
        return _Stmt("stop")
    if body.startswith("flip(") and body.endswith(")"):
        return _Stmt("flip", _cond(body[5:-1]))
    if body.startswith("jump "):
        return _Stmt("jump", _expr(body[5:].lstrip()))
    if body.startswith("output(") and body.endswith(")"):
        items = tuple(
            None if item == "new" else _expr(item) for item in _split_items(body[7:-1])
        )
        return _Stmt("output", items)
    if m := _ASSIGN.fullmatch(body):
        typ, name, value = m.groups()
        arg = None if value == "input" else _expr(value)
        return _Stmt("assign", arg, _ref(name), typ)
    raise _bad(body, "use start, stop, flip, jump, output, num or string")


def _show(value: float) -> str:
    """Print a num: whole values as integers, others round-tripping."""
    return str(int(value)) if value.is_integer() else repr(value)


def _name(ref: _Ref, env: Mapping[str, tuple[str, _Value]]) -> str:
    base, index = ref
    if index is None:
        return base
    return base + _show(_number(_eval(index, env), "a variable suffix"))


def _number(value: _Value, what: str) -> float:
    if isinstance(value, str):
        raise HaltError(f"{what} needs a num, got a string")
    return value


def _operand(item: object, env: Mapping[str, tuple[str, _Value]]) -> _Value:
    if not isinstance(item, tuple):
        return item  # type: ignore[return-value]
    key = _name(item, env)
    if key not in env:
        raise HaltError(f"{key} is used before it is assigned")
    return env[key][1]


def _eval(expr: _Expr, env: Mapping[str, tuple[str, _Value]]) -> _Value:
    """Evaluate a math chain strictly left to right."""
    first, rest = expr
    value = _operand(first, env)
    for op, item in rest:
        left = _number(value, f"{op!r}")
        right = _number(_operand(item, env), f"{op!r}")
        if op in "/%" and right == 0:
            raise HaltError(f"{_show(left)}{op}0 divides by zero")
        if op == "+":
            value = left + right
        elif op == "-":
            value = left - right
        elif op == "*":
            value = left * right
        elif op == "/":
            value = left / right
        else:
            value = left % right
        if not math.isfinite(value):
            raise HaltError("a num overflowed", hint="keep values finite")
    return value


def _holds(
    cmp: tuple[_Expr, str, _Expr], env: Mapping[str, tuple[str, _Value]]
) -> bool:
    left, op, right = _eval(cmp[0], env), cmp[1], _eval(cmp[2], env)
    if op in ("$=", "$!="):
        if not (isinstance(left, str) and isinstance(right, str)):
            raise HaltError(f"{op} compares strings")
        return (left == right) == (op == "$=")
    a, b = _number(left, op), _number(right, op)
    return {
        "==": a == b,
        "!=": a != b,
        ">": a > b,
        "<": a < b,
        ">=": a >= b,
        "<=": a <= b,
    }[op]


def _condition(cond: _Cond, env: Mapping[str, tuple[str, _Value]]) -> bool:
    first, rest = cond
    result = _holds(first, env)
    for op, cmp in rest:
        value = _holds(cmp, env)
        result = (result or value) if op == "||" else (result and value)
    return result


def _whole(value: _Value, what: str) -> int:
    number = _number(value, what)
    if not number.is_integer():
        raise HaltError(f"{what} {_show(number)} is not whole")
    return int(number)


def _runs(
    state: _State,
    lines: tuple[str, ...],
    env: Mapping[str, tuple[str, _Value]],
    decays: Mapping[int, int],
) -> tuple[_Stmt | None, int | None]:
    """Return the statement this step executes, if any, and its decay count.

    The count is the remaining budget once this encounter is charged.
    """
    way, ind = state
    line = _modifiers(lines[ind])
    if line.guard and line.guard != way:
        return None, None
    left = None
    if line.decay is not None:
        budget = decays.get(ind)
        if budget is None:
            budget = _whole(_eval(line.decay, env), "a decay")
        if budget < 1:
            return None, budget
        left = budget - 1
    return _statement(line.body), left


def _reads(
    state: _State,
    lines: tuple[str, ...],
    env: Mapping[str, tuple[str, _Value]],
    decays: Mapping[int, int],
) -> str | None:
    """Return the type this step's ``input`` reads, if it reads one."""
    stmt, _ = _runs(state, lines, env, decays)
    if stmt is not None and stmt.kind == "assign" and stmt.arg is None:
        return stmt.typ
    return None


def _advance(
    state: _State,
    lines: tuple[str, ...],
    env: Mapping[str, tuple[str, _Value]],
    decays: Mapping[int, int],
    read: _Value | None = None,
) -> tuple[_State, str | None, tuple[str, tuple[str, _Value]] | None, int | None]:
    """Run one line: the next state, printed text, a store and a decay count.

    Pure: ``read`` is the value an ``input`` line received.  A ``stop``
    moves past the last line.
    """
    way, ind = state
    stmt, left = _runs(state, lines, env, decays)
    nxt, out, store = ind + way, None, None
    if stmt is None or stmt.kind in ("", "start"):
        pass
    elif stmt.kind == "stop":
        nxt = len(lines)
    elif stmt.kind == "flip":
        if _condition(stmt.arg, env):  # type: ignore[arg-type]
            way = -way
            nxt = ind + way
    elif stmt.kind == "jump":
        offset = _whole(_eval(stmt.arg, env), "a jump")  # type: ignore[arg-type]
        if offset < 1:
            raise HaltError(f"jump {offset} is not positive")
        nxt = ind + way * offset
    elif stmt.kind == "output":
        parts = []
        for item in stmt.arg:  # type: ignore[attr-defined]
            value = "\n" if item is None else _eval(item, env)
            parts.append(value if isinstance(value, str) else _show(value))
        out = "".join(parts)
    else:
        assert stmt.ref is not None
        got = read if stmt.arg is None else _eval(stmt.arg, env)  # type: ignore[arg-type]
        assert got is not None
        value = got
        if isinstance(value, str) != (stmt.typ == "string"):
            raise HaltError(f"a {stmt.typ} cannot hold that value")
        key = _name(stmt.ref, env)
        if key in env and env[key][0] != stmt.typ:
            raise HaltError(f"{key} is already a {env[key][0]}")
        store = (key, (stmt.typ, value))
    return (way, nxt), out, store, left


def _start(code: str) -> tuple[tuple[str, ...], _State]:
    """Split the source and find the topmost start line."""
    lines = tuple(code.replace("\r\n", "\n").split("\n"))
    for ind, raw in enumerate(lines):
        m = _START.fullmatch(raw.strip())
        if m:
            if m.group(1) not in ("0", "1"):
                raise _bad(raw.strip(), "start(0) runs down, start(1) up")
            return lines, (1 if m.group(1) == "0" else -1, ind)
    raise syntax_error(
        "no start statement", "add start(0) or start(1)", error_type=ProgramError
    )


_WORKSPACE_MODEL = WorkspaceModel(
    "flipscript-v1", ("line", "direction", "variables", "decays", "input_cursor")
)


class _Machine:
    """A Flipscript run: direction, line, variables and decay counts."""

    ip_shape = "line"

    def __init__(self, code: str | tuple[tuple[str, ...], _State], io: IO) -> None:
        self.lines, (self.way, self.ind) = (
            _start(code) if isinstance(code, str) else code
        )
        self.io = io
        self.env: dict[str, tuple[str, _Value]] = {}
        self.decays: dict[int, int] = {}
        self._writer = _BufferedOutput()
        self._rejected = RejectedInput()

    @property
    def halted(self) -> bool:
        return not 0 <= self.ind < len(self.lines)

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture semantic components independently of cycle grouping."""
        accepted = self._writer.accepted
        return _WORKSPACE_MODEL.capture(
            line=(
                WorkspaceVariant("pending_output", (self.ind, accepted))
                if accepted
                else self.ind
            ),
            direction=self.way,
            variables=frozenset(self.env.items()),
            decays=frozenset(self.decays.items()),
            input_cursor=self._rejected.cursor(self.io.progress()),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        boundary = self._rejected.snapshot(
            (
                self.way,
                self.ind,
                tuple(sorted(self.env.items())),
                tuple(sorted(self.decays.items())),
                self.io.progress(),
            )
        )
        accepted = self._writer.accepted
        return (*boundary, accepted) if accepted else boundary

    def step(self) -> None:
        """Run one line; an ``input`` is read here."""
        if self.halted:
            return
        state = (self.way, self.ind)
        typ = _reads(state, self.lines, self.env, self.decays)
        read = None if typ is None else self._read(typ)
        try:
            (self.way, ind), out, store, left = _advance(
                state, self.lines, self.env, self.decays, read
            )
        except (HaltError, ValueError) as error:
            if read is not None:
                self._rejected.remember(error)
            raise
        if out:
            self._writer.write(self.io, out)
        if store is not None:
            self.env[store[0]] = store[1]
        if left is not None:
            self.decays[self.ind] = left
        self.ind = ind

    def _read(self, typ: str) -> _Value:
        raw = self._rejected.read(self.io, self.io.input_str)
        if typ == "string":
            return raw
        text = raw.strip()
        if _NUMBER_INPUT.fullmatch(text):
            return float(text)
        error = ArgumentError(f"num input {raw!r} is not a decimal number")
        self._rejected.remember(error)
        raise error


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Locate the start line once and allocate state per invocation."""
    if not isinstance(source, str):
        raise TypeError("flipscript machines require text source")
    if options:
        raise TypeError("flipscript machines accept no runtime options")
    image = _start(source)
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(code: str | tuple[tuple[str, ...], _State], io: IO) -> CompletionReport:
    """Run a Flipscript program until it stops or leaves the file."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run a Flipscript program until it stops or leaves the file."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
