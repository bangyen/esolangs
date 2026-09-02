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

The interpreter runs on a :class:`_Machine` (the parsed program, variable
state, and program counter), so it is step-capable: ``step()`` executes
one instruction and ``halted`` is true once ``x`` fires or the counter
runs off the program.

Evaluation is pure over an immutable ``_Vars``: :func:`_eval` and
:func:`_exec` take the variables they see and return the value together
with the variables and the control decision the instruction left behind.
Neither edits what it is handed.  The control decision -- a jump target,
or that ``x`` fired -- used to be a dictionary passed down the recursion
and written into from the bottom; it is a returned value now, so an arm
that sets it cannot be confused with one that merely reads it.

The two ports stay callbacks rather than being hoisted into the shell,
since :func:`_eval` recurses and the shell cannot know ahead of time how
many reads a line will make.  In practice a *nested* argument never has a
side effect at all: a group must produce an integer or a condition, and
every operation that reads, prints, declares, assigns or exits returns
none, so none of them can sit inside one.  The threading through nested
arguments is therefore uniform rather than load-bearing, and two mutants
that break it -- discarding the variables an ``s``'s value expression
returns, and swapping the order the two operands of a binary operation are
evaluated in -- are equivalent for that reason rather than untested.
"""

import sys
from collections.abc import Callable, Mapping
from typing import Literal, get_args

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The parse tree, as tuples discriminated by their first element.  Two
# families: an argument, which _eval reduces to a value, and an
# instruction, which _exec runs.  A group holds an instruction, so the
# aliases quote their forward references.
_Str = tuple[Literal["str"], str]
_Int = tuple[Literal["int"], int]
_Var = tuple[Literal["var"], str]
_Cond = tuple[Literal["cond"], bool]

# ``.`` -- the absent second argument.  A bare one-tuple, so reading [1]
# off one is a type error rather than an IndexError.
_None = tuple[Literal["none"]]

# ``|expr|`` and ``(expr)``: the kind names which of the two the group is
# required to produce.
_Group = tuple[Literal["group"], Literal["int", "cond"], "_Instr"]
_Arg = _Str | _Int | _Var | _Cond | _None | _Group

# The thirteen operations, spelled once here and derived into the set
# the parser validates against, so the two cannot drift apart.
_Op = Literal["p", "v", "s", "c", "+", "*", "=", ">", "r", "n", "f", "i", "x"]
_Instr = tuple[_Op, _Arg, _Arg]

ValueT = str | int | bool | None

_OPS: frozenset[_Op] = frozenset(get_args(_Op))
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


def _parse_expr(line: str, i: int) -> tuple[_Instr, int]:
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


def _parse_group(line: str, i: int) -> tuple[_Group, int]:
    """Parse a ``|...|`` or ``(...)`` expression group opened at ``i``."""
    kind: Literal["int", "cond"] = "int" if line[i] == "|" else "cond"
    closer = "|" if line[i] == "|" else ")"
    expr, j = _parse_expr(line, i + 1)
    if j >= len(line) or line[j] != closer:
        raise ValueError(f"unbalanced {line[i]!r}")
    return ("group", kind, expr), j + 1


def _parse_arg(line: str, i: int) -> tuple[_Arg, int]:
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


def _parse_line(line: str) -> _Instr:
    """Parse one instruction line into an ``(op, arg1, arg2)`` node."""
    node, i = _parse_expr(line, 0)
    if _skip_space(line, i) != len(line):
        raise ValueError("trailing characters")
    if node[0] in "pvcin" and node[2] != ("none",):
        raise ValueError(f"operation {node[0]!r} takes no second argument")
    return node


#: The variable store.  A value, not a record: every function below
#: returns a new mapping rather than editing the one it was handed, so an
#: instruction that assigns and then raises leaves the caller's copy alone.
type _Vars = Mapping[str, ValueT]

#: What an instruction decided about control: ``(jump, exit)`` -- the line
#: to go to, or ``None`` to fall through, and whether ``x`` fired.  Returned
#: rather than written into a dictionary handed down the recursion.
type _Control = tuple[int | None, bool]

#: The two ports.  Callbacks, because arguments nest: one line can read and
#: print several times, at points that depend on values computed part-way
#: through evaluating it.
type _Read = Callable[[], str]
type _Emit = Callable[[ValueT], None]

_FALL: _Control = (None, False)


def _eval(
    node: _Arg, state: _Vars, control: _Control, read: _Read, emit: _Emit
) -> tuple[ValueT, _Vars, _Control]:
    """Evaluate a value node (or run an instruction) and return its value.

    Pure in its state: it reads ``state`` and returns a new one.  The
    control decision is threaded through so a nested instruction -- an
    ``f`` inside an argument -- can still make one.
    """
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
    """Execute one instruction, returning the value it produces (usually none).

    Pure in its state, like :func:`_eval`.  ``read`` and ``emit`` are the
    two ports; everything else is a function of the arguments and the
    variables.
    """
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
    # The twelve arms above are the other operations, so what is left is
    # ``x``.
    return None, state, (control[0], True)


class _Machine:
    """One Between run: the parsed program, variables, and counter."""

    def __init__(self, code: list[str], io: IO) -> None:
        self.io = io
        program: list[_Instr] = []
        for line in code:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            program.append(_parse_line(stripped))
        self.program = program
        self.state: dict[str, ValueT] = {}
        self.pc = 0
        self._exited = False

    @property
    def halted(self) -> bool:
        """Whether ``x`` fired or the counter ran off the program."""
        return self._exited or not 0 <= self.pc < len(self.program)

    # The VM's language-shaped view: Goto-based variables; ip the program counter,
    # memory the ints.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.pc

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [v for v in self.state.values() if type(v) is int]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.pc,
            tuple(sorted(self.state.items())),
            self.io.position(),
            self._exited,
        )

    def step(self) -> None:
        """Execute one instruction, advancing (or jumping) the counter.

        The two ports live here rather than in the transition: this is the
        shell.  They are handed over as callbacks because an instruction's
        arguments nest, so a read or a print happens part-way through
        evaluating a line rather than before or after it.
        """
        if self.halted:
            return
        _, state, control = _exec(
            self.program[self.pc],
            self.state,
            _FALL,
            self.io.input_str,
            self.io.print_value,
        )
        self.state = dict(state)
        jump, exited = control
        if exited:
            self._exited = True
            return
        self.pc = jump if jump is not None else self.pc + 1


def run(code: list[str], io: IO) -> None:
    """Run a Between program, executing instructions until it exits or falls off."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.readlines(), IO())
