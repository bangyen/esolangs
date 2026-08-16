"""Interpreter for Between.

Each instruction is one line of the form ``<arg1><operation><arg2>``; the
five value types are strings (``'...'``), integers (``|...|``), variables
(``[...]``), conditions (``(...)``), and none (``.``).  Arguments may be
nested expressions, so ``|[a]+[b]|`` evaluates ``[a]+[b]`` as an integer and
``([in]='1')`` evaluates ``[in]='1'`` as a condition.  ``f`` jumps to a
0-indexed instruction, making Between a goto-based language.

Decisions for gaps in the wiki spec (documented):
- instruction addresses are 0-indexed (the wiki's truth machine example only
  behaves like a truth machine under 0-indexing, where ``|5|f.`` loops back
  to line 5 to reprint ``1``);
- ``p`` writes with no trailing newline;
- variables are declared (``v``) holding integer 0;
- strings double apostrophes to include one (``''``), so the parser treats
  ``''`` inside a literal as an escaped apostrophe (the wiki's ``can't``
  example is untested and does not round-trip);
- blank lines and lines starting with ``#`` are comments and skipped; line
  numbers count only real instructions;
- a ``goto`` target outside the program, or running off the end of the
  program without ``x``, halts the program;
- an undeclared variable, or an operation fed a value of the wrong type
  (e.g. ``*`` on strings), is an invalid runtime operation and raises
  :class:`~esolangs.exceptions.HaltError`; a malformed line (unbalanced
  brackets, an unknown operation, trailing characters) raises
  :class:`ValueError`.

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import sys
from typing import Any, cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

Node = tuple[Any, ...]
ValueT = str | int | bool | None

_OPS = frozenset("pvsc+*=>rnfix")
_WHITESPACE = " \t"


def _scan_string(line: str, i: int) -> int:
    """Return one past the closing quote, treating ``''`` as an apostrophe."""
    j = i + 1
    while j < len(line):
        if line[j] == "'":
            if j + 1 < len(line) and line[j + 1] == "'":
                j += 2
                continue
            return j + 1
        j += 1
    raise ValueError("unterminated string literal")


def _skip_space(line: str, i: int) -> int:
    """Advance ``i`` past any spaces or tabs."""
    while i < len(line) and line[i] in _WHITESPACE:
        i += 1
    return i


def _parse_expr(line: str, i: int) -> tuple[Node, int]:
    """Parse ``<arg1><op><arg2>`` at ``i``, returning its node and the next index."""
    arg1, i = _parse_arg(line, i)
    i = _skip_space(line, i)
    if i >= len(line):
        raise ValueError("missing operation")
    op = line[i]
    if op not in _OPS:
        raise ValueError(f"unknown operation {op!r}")
    arg2, i = _parse_arg(line, i + 1)
    return (op, arg1, arg2), i


def _parse_group(line: str, i: int) -> tuple[Node, int]:
    """Parse a ``|...|`` or ``(...)`` expression group opened at ``i``."""
    kind = "int" if line[i] == "|" else "cond"
    closer = "|" if line[i] == "|" else ")"
    expr, j = _parse_expr(line, i + 1)
    if j >= len(line) or line[j] != closer:
        raise ValueError(f"unbalanced {line[i]!r}")
    return ("group", kind, expr), j + 1


def _parse_arg(line: str, i: int) -> tuple[Node, int]:
    """Parse one argument at ``i``, returning its node and the next index."""
    i = _skip_space(line, i)
    if i >= len(line):
        raise ValueError("missing argument")
    c = line[i]
    if c == "'":
        end = _scan_string(line, i)
        return ("str", line[i + 1 : end - 1].replace("''", "'")), end
    if c == "|":
        j = i + 1
        while j < len(line) and line[j].isdigit():
            j += 1
        if j < len(line) and line[j] == "|" and j > i + 1:
            return ("int", int(line[i + 1 : j])), j + 1
        return _parse_group(line, i)
    if c == "[":
        j = line.find("]", i + 1)
        if j == -1:
            raise ValueError("unbalanced '['")
        return ("var", line[i + 1 : j]), j + 1
    if c == "(":
        for literal in ("True", "False"):
            if (
                line.startswith(literal, i + 1)
                and line[i + 1 + len(literal) : i + 2 + len(literal)] == ")"
            ):
                # "True"/"False" are condition literals, not hardcoded secrets.
                return ("cond", literal == "True"), i + 2 + len(literal)
        return _parse_group(line, i)
    if c == ".":
        return ("none",), i + 1
    raise ValueError(f"invalid argument {c!r}")


def _parse_line(line: str) -> Node:
    """Parse one instruction line into an ``(op, arg1, arg2)`` node."""
    node, i = _parse_expr(line, 0)
    if _skip_space(line, i) != len(line):
        raise ValueError("trailing characters")
    if node[0] in "pvcin" and node[2] != ("none",):
        raise ValueError(f"operation {node[0]!r} takes no second argument")
    return node


def _eval(
    node: Node, state: dict[str, ValueT], control: dict[str, Any], io: IO
) -> ValueT:
    """Evaluate a value node (or run an instruction) and return its value."""
    kind = node[0]
    if kind == "str":
        return cast(str, node[1])
    if kind == "int":
        return cast(int, node[1])
    if kind == "cond":
        return cast(bool, node[1])
    if kind == "none":
        return None
    if kind == "var":
        try:
            return state[node[1]]
        except KeyError:
            raise HaltError(f"undeclared variable {node[1]!r}") from None
    if kind == "group":
        value = _exec(node[2], state, control, io)
        expected = node[1]
        if expected == "int" and type(value) is not int:
            raise HaltError("expected an integer expression")
        if expected == "cond" and type(value) is not bool:
            raise HaltError("expected a condition expression")
        return value
    raise AssertionError(f"evaluated an instruction as a value: {node!r}")


def _exec(
    instr: Node, state: dict[str, ValueT], control: dict[str, Any], io: IO
) -> ValueT:
    """Execute one instruction, returning the value it produces (usually none)."""
    op, arg1, arg2 = instr[0], instr[1], instr[2]
    if op == "p":
        value = _eval(arg1, state, control, io)
        if type(value) is str or type(value) is int:
            io.print_value(value)
        else:
            raise HaltError("p cannot print this value")
        return None
    if op == "v":
        name = _eval(arg1, state, control, io)
        if type(name) is not str:
            raise HaltError("variable name must be a string")
        state[name] = 0
        return None
    if op == "s":
        if arg1[0] != "var":
            raise HaltError("s needs a variable on the left")
        state[arg1[1]] = _eval(arg2, state, control, io)
        return None
    if op == "c":
        value = _eval(arg1, state, control, io)
        if type(value) is int:
            return str(value)
        if type(value) is str and value.isdigit():
            return int(value)
        raise HaltError("c needs a string of numerals or an integer")
    if op == "+":
        left = _eval(arg1, state, control, io)
        right = _eval(arg2, state, control, io)
        if type(left) is int and type(right) is int:
            return left + right
        if type(left) is str and type(right) is str:
            return left + right
        raise HaltError("+ needs two integers or two strings")
    if op == "*":
        left = _eval(arg1, state, control, io)
        right = _eval(arg2, state, control, io)
        if type(left) is int and type(right) is int:
            return left * right
        raise HaltError("* needs two integers")
    if op == "=":
        left = _eval(arg1, state, control, io)
        right = _eval(arg2, state, control, io)
        return type(left) is type(right) and left == right
    if op == ">":
        left = _eval(arg1, state, control, io)
        right = _eval(arg2, state, control, io)
        if type(left) is int and type(right) is int:
            return left > right
        raise HaltError("> needs two integers")
    if op == "r":
        left = _eval(arg1, state, control, io)
        right = _eval(arg2, state, control, io)
        if type(left) is bool and type(right) is bool:
            return left or right
        raise HaltError("r needs two conditions")
    if op == "n":
        value = _eval(arg1, state, control, io)
        if type(value) is bool:
            return not value
        raise HaltError("n needs a condition")
    if op == "f":
        target = _eval(arg1, state, control, io)
        if type(target) is not int:
            raise HaltError("goto target must be an integer")
        if arg2 == ("none",):
            control["jump"] = target
        else:
            value = _eval(arg2, state, control, io)
            if type(value) is not bool:
                raise HaltError("goto condition must be a condition")
            if value:
                control["jump"] = target
        return None
    if op == "i":
        if arg1[0] != "var":
            raise HaltError("i needs a variable on the left")
        state[arg1[1]] = io.input_str()
        return None
    if op == "x":
        control["exit"] = True
        return None
    raise AssertionError(f"unhandled operation {op!r}")


def run(code: list[str], io: IO) -> None:
    """Run a Between program, executing instructions until it exits or falls off."""
    program: list[Node] = []
    for line in code:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        program.append(_parse_line(stripped))
    state: dict[str, ValueT] = {}
    control: dict[str, Any] = {"jump": None, "exit": False}
    pc = 0
    while 0 <= pc < len(program):
        control["jump"] = None
        _exec(program[pc], state, control, io)
        if control["exit"]:
            return
        pc = control["jump"] if control["jump"] is not None else pc + 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.readlines(), IO())
