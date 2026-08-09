"""Interpreter for Modulous.

Commands are written as ``[OP arg]`` tokens.  PSH pushes an integer, string,
or variable value; POP/SWP/DUP reshape the stack; PRT prints the top as an
integer or byte; INP reads a line; JMP/IF conditionally jump; RST resets;
and END halts.
"""

import re
import secrets
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from esolangs.interpreters.io import IO


@dataclass
class State:
    """Stack, variables, and instruction pointer for a Modulous run."""

    stk: list[int] = field(default_factory=list)
    var: dict[str, int] = field(default_factory=dict)
    ind: int = 0
    io: IO = field(default_factory=IO)


def _jmp(state: State, mod: str, arg: list[str]) -> str | None:
    cond = True
    val = state.stk[-1] if state.stk else 0

    if "NIF" in mod:
        cond = val != int(arg[-1])
    elif "IF" in mod:
        cond = val == int(arg[-1])

    if cond:
        if arg[1] == "F":
            state.ind += int(arg[2]) - 1
        else:
            state.ind -= int(arg[2]) + 1
    return None


def _add(state: State, _mod: str, arg: list[str]) -> str | None:
    state.stk[-1] += int(arg[1])
    return None


def _sub(state: State, _mod: str, arg: list[str]) -> str | None:
    state.stk[-1] -= int(arg[1])
    return None


def _rst(state: State, _mod: str, _arg: list[str]) -> str | None:
    state.ind = -1
    return None


def _psh(state: State, mod: str, arg: list[str]) -> str | None:
    if "INT" in mod:
        state.stk.append(int(arg[2]))
    elif "STR" in mod:
        m = mod.split('"')[1]
        state.stk += [ord(c) for c in m][::-1]
    elif "VAR" in mod:
        state.var[arg[1]] = state.stk[-1]
    return None


def _pop(state: State, _mod: str, _arg: list[str]) -> str | None:
    state.stk.pop()
    return None


def _swp(state: State, _mod: str, _arg: list[str]) -> str | None:
    state.stk.append(state.stk.pop(-2))
    return None


def _prt(state: State, mod: str, arg: list[str]) -> str | None:
    n = state.var[arg[1]] if "VAR" in mod else state.stk.pop()

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
    state.stk.append(state.stk[-1])
    return None


def _rnd(state: State, _mod: str, arg: list[str]) -> str | None:
    state.stk.append(secrets.randbelow(int(arg[1])))
    return None


def _var_arith(state: State, mod: str) -> None:
    if "+" in mod:
        lhs, rhs = mod.split("+")
        state.var[lhs] += int(rhs)
    elif "-" in mod:
        lhs, rhs = mod.split("-")
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
    tokens = [k[0] for k in reg.findall(code)]
    state = State(var={f"VAR{k}": 0 for k in range(1, 5)}, io=io)

    while state.ind < len(tokens):
        mod = tokens[state.ind]
        arg = mod.split()
        state.ind += 1

        handler = _DISPATCH.get(arg[0])
        if handler is not None:
            if handler(state, mod, arg) == "halt":
                return
        elif "+" in mod or "-" in mod:
            _var_arith(state, mod)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
