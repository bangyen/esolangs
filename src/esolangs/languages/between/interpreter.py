"""Interpreter for Between.

One instruction a line, ``<arg1><operation><arg2>``, run from the top; the
page leaves the line-number base, the unset value and nesting to its
examples.  An argument is a string ``'x'``, an integer ``|x|``, a variable
``[x]``, a condition ``(x)`` or none ``.``.  ``|..|`` and ``(..)`` also
group an expression whose value must be an integer or a condition, so
``|[a]+[b]|`` and ``([in]='1')`` nest.  Running off the last line halts.

Commands:
    ``'v'v.``      declare variable ``v``, holding the integer 0
    ``[v]s a``     set ``v`` to a string or integer
    ``a p .``      print a string or integer, no newline
    ``[v]i.``      set ``v`` to the next input line
    ``a c .``      a string of numerals to an integer, an integer to a string
    ``a + b``      add two integers, or join two strings
    ``a * b``      multiply two integers
    ``a = b``      equal: same type and value
    ``a > b``      greater: two integers
    ``a r b``      or: two conditions
    ``a n .``      not: a condition
    ``n f c``      go to line ``n`` (0-based) if condition ``c``; ``c`` none always
    ``.x.``        exit

Input/output:
    ``i`` reads a whole line, kept as a string; ``p`` writes its argument
    with no newline.

Errors:
    ProgramError: a malformed line, an operand the operation never takes
    (``s`` or ``i`` on a non-variable, a missing or extra second argument),
    or an operation that returns none inside a group.
    InputExhaustedError: ``i`` at EOF.
    HaltError: an undeclared variable, an operand of the wrong type, a goto
    outside the program, a group of the wrong kind, or ``c`` on non-numerals.

Decisions:
    * Goto lines are 0-based: the truth machine only loops on ``1`` if
      ``|5|f.`` reaches its ``|1|p.``; the subtraction example's
      ``|13|f`` reaches its error message only 0-based.  Blank lines and
      ``#`` comments are not counted.  Line ``len(program)`` halts; any
      other target outside the program is a HaltError.
    * ``v`` stores the integer 0, so an unset variable reads as Int 0 (the
      Fibonacci example adds ``[a]`` before setting it).  Declaring again
      resets it.
    * ``s`` and ``i`` need a declared variable, as every example declares
      first; reading one that is not raises.
    * A string ends at the first apostrophe followed by what may follow the
      argument: an operation after ``arg1``, the end of the line, ``|`` or
      ``)`` after ``arg2``.  The subtraction example's ``can't`` thus reads
      whole; ``'rock'n'roll'p.`` does not.  There is no escape.
    * ``(True)`` and ``(False)`` are condition literals; the page shows a
      Condition's values but no spelling.
    * ``p`` prints no newline, and prints only a string or an integer.
    * ``=`` needs equal types, so ``'1'=|1|`` is false; ``s`` takes only
      strings and integers.
    * A line is stripped and has no interior blanks outside a string.
    * Inside a group only ``c + * = > r n`` are allowed, the operations that
      return a value; the rest always fail as a group, and rejecting them at
      parse keeps evaluation free of side effects.
    * The Fibonacci example never leaves 0 (``a`` and ``b`` start at 0) and
      is run as written, not repaired.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

type _Value = str | int | bool | None
#: ``(kind, payload)``: ``str``/``int``/``cond`` literals, ``var`` name,
#: ``none``, or ``group`` holding ``(kind, instruction)``.
type _Arg = tuple[str, Any]
type _Instr = tuple[str, _Arg, _Arg]
type _Vars = Mapping[str, str | int]
#: ``(variables, line index, exited)``.
type _State = tuple[_Vars, int, bool]

_OPS = "pvscn+*=>rfix"
_VALUE_OPS = "c+*=>rn"
_UNARY = "pvcnix"
_BINARY = "s+*=>r"
_NONE: _Arg = ("none", None)
_NUMERALS = re.compile(r"[0-9]+")


def _follows(line: str, j: int, *, second: bool) -> bool:
    """Whether ``line[j:]`` may follow an argument in this position."""
    if not second:
        return j < len(line) and line[j] in _OPS
    return j >= len(line) or line[j] in "|)"


def _string(line: str, i: int, *, second: bool) -> tuple[_Arg, int]:
    """Parse the string opened at ``i``, closed by the first fitting apostrophe."""
    j = line.find("'", i + 1)
    while j != -1 and not _follows(line, j + 1, second=second):
        j = line.find("'", j + 1)
    if j == -1:
        raise syntax_error(
            "unterminated string", "close the string with ' before the operation"
        )
    return ("str", line[i + 1 : j]), j + 1


def _group(line: str, i: int) -> tuple[_Arg, int]:
    """Parse the ``|..|`` or ``(..)`` expression opened at ``i``."""
    kind, closer = ("int", "|") if line[i] == "|" else ("cond", ")")
    instr, j = _expr(line, i + 1)
    if instr[0] not in _VALUE_OPS:
        raise syntax_error(
            f"{instr[0]!r} returns none inside a group",
            "group only c, +, *, =, >, r or n",
        )
    if j >= len(line) or line[j] != closer:
        raise syntax_error(f"unbalanced {line[i]!r}", f"close the group with {closer}")
    return ("group", (kind, instr)), j + 1


def _arg(line: str, i: int, *, second: bool) -> tuple[_Arg, int]:
    """Parse one argument at ``i``."""
    if i >= len(line):
        raise syntax_error("missing argument", "write the argument or . for none")
    c = line[i]
    if c == "'":
        return _string(line, i, second=second)
    if c == "|":
        literal = _NUMERALS.match(line, i + 1)
        if literal and line.startswith("|", literal.end()):
            return ("int", int(literal.group())), literal.end() + 1
        return _group(line, i)
    if c == "[":
        j = line.find("]", i)
        if j == -1:
            raise syntax_error("unbalanced '['", "close the variable with ]")
        return ("var", line[i + 1 : j]), j + 1
    if c == "(":
        for word in ("True", "False"):
            if line.startswith(word + ")", i + 1):
                return ("cond", word == "True"), i + len(word) + 2
        return _group(line, i)
    if c == ".":
        return _NONE, i + 1
    raise syntax_error(f"invalid argument {c!r}", "start with ', |, [, ( or .")


def _expr(line: str, i: int) -> tuple[_Instr, int]:
    """Parse ``<arg1><op><arg2>`` at ``i``."""
    first, i = _arg(line, i, second=False)
    if i >= len(line) or line[i] not in _OPS:
        raise syntax_error("missing or unknown operation", f"use one of {_OPS}")
    op = line[i]
    second, i = _arg(line, i + 1, second=True)
    return (op, first, second), i


def _instruction(line: str) -> _Instr:
    """Parse one instruction line and check the operands it never takes."""
    instr, end = _expr(line, 0)
    op, first, second = instr
    if end != len(line):
        raise syntax_error("trailing characters", "one instruction per line")
    if op in "si" and first[0] != "var":
        raise syntax_error(f"{op!r} needs a variable first", "write [name] first")
    if op in _UNARY and second != _NONE:
        raise syntax_error(f"{op!r} takes no second argument", "end it with .")
    if op in _BINARY and second == _NONE:
        raise syntax_error(f"{op!r} needs a second argument", "give it a value")
    if op == "x" and first != _NONE:
        raise syntax_error("'x' takes no arguments", "write .x.")
    return instr


def _parse(code: str) -> tuple[_Instr, ...]:
    """Return the instructions, skipping blank and ``#`` lines."""
    lines = (row.strip() for row in code.splitlines())
    return tuple(_instruction(row) for row in lines if row and row[0] != "#")


def _int(value: _Value, what: str) -> int:
    """Return ``value`` if it is an integer (not a condition)."""
    if type(value) is not int:
        raise HaltError(f"{what} needs an integer, got {value!r}")
    return value


def _same(left: _Value, right: _Value, op: str) -> bool:
    """True if both operands are strings or both integers, else HaltError."""
    if type(left) not in (str, int) or type(right) is not type(left):
        raise HaltError(f"{op} needs two strings or two integers")
    return True


def _plus(left: _Value, right: _Value) -> _Value:
    _same(left, right, "+")
    return left + right  # type: ignore[operator]


def _convert(value: _Value, _: _Value) -> _Value:
    if type(value) is int:
        return str(value)
    if type(value) is str and _NUMERALS.fullmatch(value):
        return int(value)
    raise HaltError(f"c needs an integer or a string of numerals, got {value!r}")


def _or(left: _Value, right: _Value) -> _Value:
    if type(left) is not bool or type(right) is not bool:
        raise HaltError("r needs two conditions")
    return left or right


def _not(value: _Value, _: _Value) -> _Value:
    if type(value) is not bool:
        raise HaltError("n needs a condition")
    return not value


_PURE: dict[str, Callable[[_Value, _Value], _Value]] = {
    "c": _convert,
    "+": _plus,
    "*": lambda a, b: _int(a, "*") * _int(b, "*"),
    "=": lambda a, b: _same(a, b, "=") and a == b,
    ">": lambda a, b: _int(a, ">") > _int(b, ">"),
    "r": _or,
    "n": _not,
}


def _eval(arg: _Arg, variables: _Vars) -> _Value:
    """Return an argument's value; pure."""
    kind, payload = arg
    if kind == "var":
        if payload not in variables:
            raise HaltError(f"undeclared variable {payload!r}")
        return variables[payload]
    if kind != "group":
        return None if kind == "none" else payload
    expect, (op, first, second) = payload
    value = _PURE[op](_eval(first, variables), _eval(second, variables))
    if type(value) is not (int if expect == "int" else bool):
        raise HaltError(f"a {expect} group produced {value!r}")
    return value


def _declared(arg: _Arg, variables: _Vars) -> str:
    """Return the name of a variable ``s`` or ``i`` writes; it must exist."""
    if arg[1] not in variables:
        raise HaltError(f"undeclared variable {arg[1]!r}")
    return str(arg[1])


def _with(variables: _Vars, name: str, value: str | int) -> _Vars:
    """Return ``variables`` with ``name`` bound to ``value``."""
    return MappingProxyType({**variables, name: value})


def _advance(
    state: _State, code: tuple[_Instr, ...], line: str | None = None
) -> tuple[_State, str | None]:
    """Return the state after the current instruction, and what it prints; pure.

    An ``i`` receives its input line as ``line``.
    """
    variables, ind, _ = state
    op, first, second = code[ind]
    if op == "x":
        return (variables, ind, True), None
    nxt = ind + 1
    out = None
    if op == "p":
        value = _eval(first, variables)
        if type(value) not in (str, int):
            raise HaltError(f"p cannot print {value!r}")
        out = str(value)
    elif op == "v":
        name = _eval(first, variables)
        if type(name) is not str:
            raise HaltError("a variable name must be a string")
        variables = _with(variables, name, 0)
    elif op == "s":
        value = _eval(second, variables)
        if type(value) not in (str, int):
            raise HaltError(f"s takes a string or integer, got {value!r}")
        variables = _with(variables, _declared(first, variables), value)  # type: ignore[arg-type]
    elif op == "i":
        assert line is not None
        variables = _with(variables, _declared(first, variables), line)
    elif op == "f":
        target = _int(_eval(first, variables), "f")
        if second == _NONE or _eval(second, variables) is True:
            if not 0 <= target <= len(code):
                raise HaltError(f"goto {target} is outside the program")
            nxt = target
    else:
        _PURE[op](_eval(first, variables), _eval(second, variables))
    return (variables, nxt, False), out


class _Machine:
    """A Between run: the variables and the index of the next instruction."""

    def __init__(self, code: str, io: IO) -> None:
        self.code = _parse(code)
        self.io = io
        self.variables: _Vars = MappingProxyType({})
        self.ind = 0
        self.exited = False

    @property
    def halted(self) -> bool:
        return self.exited or self.ind >= len(self.code)

    @property
    def _state(self) -> _State:
        return (self.variables, self.ind, self.exited)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            tuple(sorted(self.variables.items())),
            self.exited,
            self.io.progress(),
        )

    def step(self) -> None:
        """Run one instruction; an ``i`` reads its line here."""
        if self.halted:
            return
        line = self.io.input_str() if self.code[self.ind][0] == "i" else None
        (self.variables, self.ind, self.exited), out = _advance(
            self._state, self.code, line
        )
        if out is not None:
            self.io.print_str(out)


def run(code: str, io: IO) -> None:
    """Run a Between program until ``x`` or the last line."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
