import re
import secrets
import sys
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class State:
    stk: list[int] = field(default_factory=list)
    var: dict[str, int] = field(default_factory=dict)
    new: int = 1
    ind: int = 0


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


def _add(state: State, mod: str, arg: list[str]) -> str | None:
    state.stk[-1] += int(arg[1])
    return None


def _sub(state: State, mod: str, arg: list[str]) -> str | None:
    state.stk[-1] -= int(arg[1])
    return None


def _rst(state: State, mod: str, arg: list[str]) -> str | None:
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


def _pop(state: State, mod: str, arg: list[str]) -> str | None:
    state.stk.pop()
    return None


def _swp(state: State, mod: str, arg: list[str]) -> str | None:
    state.stk.append(state.stk.pop(-2))
    return None


def _prt(state: State, mod: str, arg: list[str]) -> str | None:
    n = state.var[arg[1]] if "VAR" in mod else state.stk.pop()

    if "INT" in mod:
        print(n, end="")
    else:
        print(chr(n), end="")
    state.new = 0
    return None


def _inp(state: State, mod: str, arg: list[str]) -> str | None:
    input_str: str = input("\nInput: "[state.new :])
    state.new = 1

    if "INT" in mod and input_str:
        state.stk.append(int(input_str))
    else:
        state.stk += [ord(c) for c in str(input_str)][::-1]
    return None


def _end(state: State, mod: str, arg: list[str]) -> str | None:
    return "halt"


def _dup(state: State, mod: str, arg: list[str]) -> str | None:
    state.stk.append(state.stk[-1])
    return None


def _rnd(state: State, mod: str, arg: list[str]) -> str | None:
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


def run(code: str) -> None:
    reg = re.compile(r'\[([^\[\]\"]*("[^"]*")?)]')
    tokens = [k[0] for k in reg.findall(code)]
    state = State(var={f"VAR{k}": 0 for k in range(1, 5)})

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
            run(data)
