r"""Interpreter for Between."""

import sys
from collections.abc import Callable, Mapping
from typing import Literal, get_args

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The parse tree, as tuples.
# families: an argument, which.
# instruction, which _exec runs.
# aliases quote their forward.
_Str = tuple[Literal["str"], str]
_Int = tuple[Literal["int"], int]
_Var = tuple[Literal["var"], str]
_Cond = tuple[Literal["cond"], bool]

# ``.`` -- the absent second.
# off one is a type error.
_None = tuple[Literal["none"]]

# ``|expr|`` and ``(expr)``:.
# required to produce.
_Group = tuple[Literal["group"], Literal["int", "cond"], "_Instr"]
_Arg = _Str | _Int | _Var | _Cond | _None | _Group

# The thirteen operations,.
# the parser validates against,.
_Op = Literal["p", "v", "s", "c", "+", "*", "=", ">", "r", "n", "f", "i", "x"]
_Instr = tuple[_Op, _Arg, _Arg]

ValueT = str | int | bool | None

_OPS: frozenset[_Op] = frozenset(get_args(_Op))
_WHITESPACE = " \t"


def _scan_string(line: str, i: int) -> int:
    r"""Return one past the closing quote, treating ``''`` as an apostrophe."""
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
    r"""Advance ``i`` past any spaces or tabs."""
    while i < len(line) and line[i] in _WHITESPACE:
        i += 1
    return i


def _parse_expr(line: str, i: int) -> tuple[_Instr, int]:
    r"""Parse ``<arg1><op><arg2>`` at ``i``, returning its node and the."""
    arg1, i = _parse_arg(line, i)
    i = _skip_space(line, i)
    if i >= len(line):
        raise ValueError("missing operation")
    op = line[i]
    if op not in _OPS:
        raise ValueError(f"unknown operation {op!r}")
    arg2, i = _parse_arg(line, i + 1)
    return (op, arg1, arg2), i


def _parse_group(line: str, i: int) -> tuple[_Group, int]:
    r"""Parse a ``|...|`` or ``(...)`` expression group opened at ``i``."""
    kind: Literal["int", "cond"] = "int" if line[i] == "|" else "cond"
    closer = "|" if line[i] == "|" else ")"
    expr, j = _parse_expr(line, i + 1)
    if j >= len(line) or line[j] != closer:
        raise ValueError(f"unbalanced {line[i]!r}")
    return ("group", kind, expr), j + 1


def _parse_arg(line: str, i: int) -> tuple[_Arg, int]:
    r"""Parse one argument at ``i``, returning its node and the next index."""
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
                # "True"/"False" are condition.
                return ("cond", literal == "True"), i + 2 + len(literal)
        return _parse_group(line, i)
    if c == ".":
        return ("none",), i + 1
    raise ValueError(f"invalid argument {c!r}")


def _parse_line(line: str) -> _Instr:
    r"""Parse one instruction line into an ``(op, arg1, arg2)`` node."""
    node, i = _parse_expr(line, 0)
    if _skip_space(line, i) != len(line):
        raise ValueError("trailing characters")
    if node[0] in "pvcin" and node[2] != ("none",):
        raise ValueError(f"operation {node[0]!r} takes no second argument")
    return node


# : The variable store.
# : returns a new mapping.
# : instruction that assigns.
type _Vars = Mapping[str, ValueT]

# : What an instruction decided.
# : to go to, or ``None`` to.
# : rather than written into a.
type _Control = tuple[int | None, bool]

# : Every value a Between.
# : counter, and whether ``x``.
# : temporary :data:`_Control`;.
type _State = tuple[_Vars, int, bool]

# : The two ports.
# : print several times, at.
#: through evaluating it.
type _Read = Callable[[], str]
type _Emit = Callable[[ValueT], None]

_FALL: _Control = (None, False)


def _eval(
    node: _Arg, state: _Vars, control: _Control, read: _Read, emit: _Emit
) -> tuple[ValueT, _Vars, _Control]:
    r"""Evaluate a value node (or run an instruction) and return its value."""
    if node[0] == "str":
        return node[1], state, control
    if node[0] == "int":
        return node[1], state, control
    if node[0] == "cond":
        return node[1], state, control
    if node[0] == "none":
        return None, state, control
    if node[0] == "var":
        if node[1] not in state:
            raise HaltError(f"undeclared variable {node[1]!r}")
        return state[node[1]], state, control
    value, state, control = _exec(node[2], state, control, read, emit)
    expected = node[1]
    if expected == "int" and type(value) is not int:
        raise HaltError("expected an integer expression")
    if expected == "cond" and type(value) is not bool:
        raise HaltError("expected a condition expression")
    return value, state, control


def _exec(
    instr: _Instr, state: _Vars, control: _Control, read: _Read, emit: _Emit
) -> tuple[ValueT, _Vars, _Control]:
    r"""Execute one instruction, returning the value it produces (usually."""
    op, arg1, arg2 = instr[0], instr[1], instr[2]
    if op == "p":
        value, state, control = _eval(arg1, state, control, read, emit)
        if type(value) is str or type(value) is int:
            emit(value)
        else:
            raise HaltError("p cannot print this value")
        return None, state, control
    if op == "v":
        name, state, control = _eval(arg1, state, control, read, emit)
        if type(name) is not str:
            raise HaltError("variable name must be a string")
        return None, {**state, name: 0}, control
    if op == "s":
        if arg1[0] != "var":
            raise HaltError("s needs a variable on the left")
        value, state, control = _eval(arg2, state, control, read, emit)
        return None, {**state, arg1[1]: value}, control
    if op == "c":
        value, state, control = _eval(arg1, state, control, read, emit)
        if type(value) is int:
            return str(value), state, control
        if type(value) is str and value.isdigit():
            return int(value), state, control
        raise HaltError("c needs a string of numerals or an integer")
    if op == "+":
        left, state, control = _eval(arg1, state, control, read, emit)
        right, state, control = _eval(arg2, state, control, read, emit)
        if type(left) is int and type(right) is int:
            return left + right, state, control
        if type(left) is str and type(right) is str:
            return left + right, state, control
        raise HaltError("+ needs two integers or two strings")
    if op == "*":
        left, state, control = _eval(arg1, state, control, read, emit)
        right, state, control = _eval(arg2, state, control, read, emit)
        if type(left) is int and type(right) is int:
            return left * right, state, control
        raise HaltError("* needs two integers")
    if op == "=":
        left, state, control = _eval(arg1, state, control, read, emit)
        right, state, control = _eval(arg2, state, control, read, emit)
        return type(left) is type(right) and left == right, state, control
    if op == ">":
        left, state, control = _eval(arg1, state, control, read, emit)
        right, state, control = _eval(arg2, state, control, read, emit)
        if type(left) is int and type(right) is int:
            return left > right, state, control
        raise HaltError("> needs two integers")
    if op == "r":
        left, state, control = _eval(arg1, state, control, read, emit)
        right, state, control = _eval(arg2, state, control, read, emit)
        if type(left) is bool and type(right) is bool:
            return left or right, state, control
        raise HaltError("r needs two conditions")
    if op == "n":
        value, state, control = _eval(arg1, state, control, read, emit)
        if type(value) is bool:
            return not value, state, control
        raise HaltError("n needs a condition")
    if op == "f":
        target, state, control = _eval(arg1, state, control, read, emit)
        if type(target) is not int:
            raise HaltError("goto target must be an integer")
        if arg2 == ("none",):
            return None, state, (target, control[1])
        value, state, control = _eval(arg2, state, control, read, emit)
        if type(value) is not bool:
            raise HaltError("goto condition must be a condition")
        if value:
            return None, state, (target, control[1])
        return None, state, control
    if op == "i":
        if arg1[0] != "var":
            raise HaltError("i needs a variable on the left")
        return None, {**state, arg1[1]: read()}, control
    # The twelve arms above are the.
    # ``x``.
    return None, state, (control[0], True)


class _Machine:
    r"""One Between run: the parsed program, variables, and counter."""

    def __init__(self, code: list[str], io: IO) -> None:
        self.io = io
        program: list[_Instr] = []
        for line in code:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            program.append(_parse_line(stripped))
        self.program = tuple(program)
        self.state: dict[str, ValueT] = {}
        self.pc = 0
        self._exited = False

    @property
    def halted(self) -> bool:
        r"""Whether ``x`` fired or the counter ran off the program."""
        return self._exited or not 0 <= self.pc < len(self.program)

    # The VM's language-shaped.
    # memory the ints.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.pc

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return [v for v in self.state.values() if type(v) is int]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            self.pc,
            tuple(sorted(self.state.items())),
            self.io.position(),
            self._exited,
        )

    @property
    def _state(self) -> _State:
        r"""The complete changing state at the instruction boundary."""
        return (self.state, self.pc, self._exited)

    def _restore(self, state: _State) -> None:
        r"""Write a completed instruction transition back onto the shell."""
        variables, self.pc, self._exited = state
        self.state = dict(variables)

    def step(self) -> None:
        r"""Execute one instruction, advancing (or jumping) the counter."""
        if self.halted:
            return
        variables, pc, exited = self._state
        _, variables, control = _exec(
            self.program[pc],
            variables,
            _FALL,
            self.io.input_str,
            self.io.print_value,
        )
        jump, stopped = control
        self._restore(
            (
                variables,
                pc if stopped else jump if jump is not None else pc + 1,
                exited or stopped,
            )
        )


def run(code: list[str], io: IO) -> None:
    r"""Run a Between program, executing instructions until it exits or."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.readlines(), IO())
