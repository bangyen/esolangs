"""Interpreter for Modulous.

Commands are written as ``[OP arg]`` tokens.  PSH pushes an integer, string,
or variable value; POP/SWP/DUP reshape the stack; PRT prints the top as an
integer or byte; INP reads a line; JMP/IF conditionally jump; RST resets the
pointer to the start of the program; and END halts.

The wiki declares four variables (VAR1-VAR4); the interpreter initializes
those but accepts any ``VARn`` name rather than enforcing the limit.

Operations that act on an empty stack, an undefined variable, or a missing
operand are invalid: they halt the program with
:class:`~esolangs.exceptions.HaltError`, and a malformed token (a missing
required argument) is rejected with :class:`ValueError`.

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import re
import secrets
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


@dataclass
class State:
    """Stack, variables, and instruction pointer for a Modulous run."""

    stk: list[int] = field(default_factory=list)
    var: dict[str, int] = field(default_factory=dict)
    ind: int = 0
    io: IO = field(default_factory=IO)
    tokens: list[str] = field(default_factory=list, init=False)
    _halted: bool = field(default=False, init=False)

    @property
    def halted(self) -> bool:
        """Whether the instruction pointer has run off the program."""
        return self._halted or self.ind >= len(self.tokens)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            tuple(self.stk),
            tuple(sorted(self.var.items())),
            self.io.position(),
            self._halted,
        )

    def step(self) -> None:
        """Execute one ``[OP arg]`` token, advancing the pointer."""
        mod = self.tokens[self.ind]
        arg = mod.split()
        self.ind += 1
        if not arg:
            return
        handler = _DISPATCH.get(arg[0])
        if handler is not None:
            if handler(self, mod, arg) == "halt":
                self._halted = True
        elif "+" in mod or "-" in mod:
            _var_arith(self, mod)


def _top(state: State) -> int:
    """Return the top of the stack, halting on an empty stack."""
    if not state.stk:
        raise HaltError
    return state.stk[-1]


def _operand(arg: list[str], n: int) -> str:
    """Return the ``n``-th token of a command, rejecting a missing operand."""
    if n >= len(arg):
        raise ValueError(f"missing operand in {' '.join(arg)}")
    return arg[n]


def _jmp(state: State, mod: str, arg: list[str]) -> str | None:
    cond = True
    val = _top(state) if state.stk else 0

    if "NIF" in mod:
        cond = val != int(_operand(arg, -1))
    elif "IF" in mod:
        cond = val == int(_operand(arg, -1))

    if cond:
        if _operand(arg, 1) == "F":
            state.ind += int(_operand(arg, 2)) - 1
        else:
            state.ind -= int(_operand(arg, 2)) + 1
    return None


def _add(state: State, _mod: str, arg: list[str]) -> str | None:
    n = int(_operand(arg, 1))
    _top(state)
    state.stk[-1] += n
    return None


def _sub(state: State, _mod: str, arg: list[str]) -> str | None:
    n = int(_operand(arg, 1))
    _top(state)
    state.stk[-1] -= n
    return None


def _rst(state: State, _mod: str, _arg: list[str]) -> str | None:
    state.ind = 0
    return None


def _psh(state: State, mod: str, arg: list[str]) -> str | None:
    if "INT" in mod:
        state.stk.append(int(_operand(arg, 2)))
    elif "STR" in mod:
        m = mod.split('"')[1]
        state.stk += [ord(c) for c in m][::-1]
    elif "VAR" in mod:
        state.var[_operand(arg, 1)] = _top(state)
    return None


def _pop(state: State, _mod: str, _arg: list[str]) -> str | None:
    _top(state)
    state.stk.pop()
    return None


def _swp(state: State, _mod: str, _arg: list[str]) -> str | None:
    if len(state.stk) < 2:
        raise HaltError
    state.stk.append(state.stk.pop(-2))
    return None


def _prt(state: State, mod: str, arg: list[str]) -> str | None:
    if "VAR" in mod:
        name = _operand(arg, 1)
        if name not in state.var:
            raise HaltError
        n = state.var[name]
    else:
        _top(state)
        n = state.stk.pop()

    if "INT" in mod:
        state.io.print_num(n)
    else:
        state.io.print_char(chr(n))
    return None


def _inp(state: State, mod: str, _arg: list[str]) -> str | None:
    input_str: str = state.io.input_str()

    if "INT" in mod and input_str:
        state.stk.append(int(input_str))
    else:
        state.stk += [ord(c) for c in str(input_str)][::-1]
    return None


def _end(_state: State, _mod: str, _arg: list[str]) -> str | None:
    return "halt"


def _dup(state: State, _mod: str, _arg: list[str]) -> str | None:
    state.stk.append(_top(state))
    return None


def _rnd(state: State, _mod: str, arg: list[str]) -> str | None:
    n = int(_operand(arg, 1))
    if n < 1:
        raise HaltError
    state.stk.append(secrets.randbelow(n))
    return None


def _var_arith(state: State, mod: str) -> None:
    if "+" in mod:
        lhs, rhs = mod.split("+")
        if lhs not in state.var:
            raise HaltError
        state.var[lhs] += int(rhs)
    elif "-" in mod:
        lhs, rhs = mod.split("-")
        if lhs not in state.var:
            raise HaltError
        state.var[lhs] -= int(rhs)


_DISPATCH: dict[str, Callable[[State, str, list[str]], str | None]] = {
    "JMP": _jmp,
    "ADD": _add,
    "SUB": _sub,
    "RST": _rst,
    "PSH": _psh,
    "POP": _pop,
    "SWP": _swp,
    "PRT": _prt,
    "INP": _inp,
    "END": _end,
    "DUP": _dup,
    "RND": _rnd,
}


def run(code: str, io: IO) -> None:
    """Run a Modulous program."""
    reg = re.compile(r'\[([^\[\]\"]*("[^"]*")?)]')
    state = State(var={f"VAR{k}": 0 for k in range(1, 5)}, io=io)
    state.tokens = [k[0] for k in reg.findall(code)]

    while not state.halted:
        state.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
