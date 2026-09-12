r"""Interpreter for Modulous."""

import re
import sys
from collections.abc import Callable, Mapping
from typing import cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Randomness, draw

# : A command is a bracketed.
_TOKEN = re.compile(r'\[([^\[\]\"]*("[^"]*")?)]')


def _reject_stray_text(code: str) -> None:
    r"""Refuse anything outside a bracketed command."""
    end = 0
    stray: list[str] = []
    for match in _TOKEN.finditer(code):
        gap = code[end : match.start()].strip()
        if gap:
            stray.append(gap)
        end = match.end()
    if tail := code[end:].strip():
        stray.append(tail)
    if stray:
        raise ValueError(
            f"{stray[0]!r} is outside any [command]; Modulous reads only "
            f"bracketed commands, so this would have been dropped silently"
        )


# : One instant of a run:.
# : named variables, and the.
# :.
# : The tokens stay out:.
# : rewrites it, so a handler.
#: carrying the list.
type _Core = tuple[tuple[int, ...], dict[str, int], int]

# : Every value a Modulous step.
# : and cursor, plus whether.
# : once and never rewritten,.
type _State = tuple[_Core, bool]

# : One instant as the.
# : :data:`_State` except that.
# : a dict cannot be a member.
type _FrozenCore = tuple[tuple[int, ...], tuple[tuple[str, int], ...], int]
type _BranchState = tuple[_FrozenCore, bool]


# : The most outcomes one.
# : is a program operand rather.
# : for more states than any.
# : property of the transition.
# : that budget shrinks as the.
# : program decidable or not.
_RND_FANOUT = 256


def _freeze(state: _State) -> _BranchState:
    r"""Return ``state`` with its variable map made hashable."""
    (stk, var, ind), halted = state
    return ((stk, tuple(sorted(var.items())), ind), halted)


def _thaw(state: _BranchState) -> _State:
    r"""Invert :func:`_freeze` so a handler sees the map it expects."""
    (stk, var, ind), halted = state
    return ((stk, dict(var), ind), halted)


class _Machine:
    r"""Stack, variables, and instruction pointer for a Modulous run."""

    stk: tuple[int, ...]
    var: dict[str, int]
    ind: int
    io: IO
    tokens: tuple[str, ...]
    _halted: bool
    # Overrides ``RND``'s draw,.
    # reproducible; ``None`` draws.
    rng: Randomness | None

    def __init__(self, code: str, io: IO, rng: Randomness | None = None) -> None:
        r"""Build a state for ``code`` with its variables and parsed tokens."""
        self.stk = ()
        self.var = {f"VAR{k}": 0 for k in range(1, 5)}
        self.ind = 0
        self.io = io
        self.tokens = tuple(k.group(1) for k in _TOKEN.finditer(code))
        _reject_stray_text(code)
        self._halted = False
        self.rng = rng

    @property
    def halted(self) -> bool:
        r"""Whether the instruction pointer has run off the program."""
        return self._halted or self.ind >= len(self.tokens)

    # The VM's language-shaped.
    # variables are not addressable.

    @property
    def ip(self) -> int:
        r"""The token cursor."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        r"""No addressable cells; the store is the stack."""
        return []

    @property
    def stack(self) -> list[object]:
        r"""The data stack, bottom first."""
        return list(self.stk)

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            self.stk,
            tuple(sorted(self.var.items())),
            self.io.position(),
            self._halted,
        )

    # The all-random-outcomes.
    # which a search cannot key on,.
    # the sorted tuple ``snapshot``.
    # the way back in.
    # rather than forking, and.

    def branching_snapshot(self) -> _BranchState:
        r"""Return the current state as the search's starting point."""
        return _freeze(self._state)

    def branching_halted(self, state: object) -> bool:
        r"""Report whether ``state`` has ended or run off the program."""
        (_stk, _var, ind), halted = cast(_BranchState, state)
        return halted or ind >= len(self.tokens)

    def branching_successors(
        self, state: object, _limit: int
    ) -> tuple[_BranchState, ...] | None:
        r"""Return the state for every value ``RND`` could draw."""
        core, halted = _thaw(cast(_BranchState, state))
        stk, var, ind = core
        mod = self.tokens[ind]
        arg = mod.split()
        advanced: _Core = (stk, var, ind + 1)
        if not arg:
            return (_freeze((advanced, halted)),)

        handler = _DISPATCH.get(arg[0])
        if handler is None:
            if "+" in mod or "-" in mod:
                return (_freeze((_var_arith(advanced, mod), halted)),)
            return (_freeze((advanced, halted)),)

        if arg[0] == "INP":
            return None

        values: tuple[str | int | None, ...] = (None,)
        if arg[0] == "RND":
            n = int(_operand(arg, 1))
            if n >= 1:
                if n > _RND_FANOUT:
                    raise TimeoutError(
                        f"undecided: one 'RND {n}' exceeds the {_RND_FANOUT}-outcome "
                        "cap on a single transition"
                    )
                values = tuple(range(n))

        done = halted or arg[0] == "END"
        return tuple(
            _freeze((handler(advanced, mod, arg, value), done)) for value in values
        )

    @property
    def _state(self) -> _State:
        r"""The complete changing state, with the handler core inside it."""
        return ((self.stk, self.var, self.ind), self._halted)

    def _restore(self, state: _State) -> None:
        r"""Write a transition result back onto the machine shell."""
        (stk, var, self.ind), self._halted = state
        self.stk = stk
        self.var = var

    def step(self) -> None:
        r"""Execute one ``[OP arg]`` token, advancing the pointer."""
        if self.halted:
            return
        (stk, var, ind), halted = self._state
        mod = self.tokens[ind]
        arg = mod.split()
        self._restore(((stk, var, ind + 1), halted))
        if not arg:
            return

        handler = _DISPATCH.get(arg[0])
        if handler is None:
            if "+" in mod or "-" in mod:
                core, halted = self._state
                self._restore((_var_arith(core, mod), halted))
                return
            # Not a command and not.
            # ``return``, so ``[PRTINT]``.
            # INT]`` -- ran as nothing at.
            # printed nothing, which is the.
            raise ValueError(
                f"[{mod}] is not a Modulous command: {arg[0]!r} is not one of "
                f"{', '.join(sorted(_DISPATCH))}, and a bare VARn+k or VARn-k "
                f"is the only other thing a command can be"
            )

        value: str | int | None = None
        if arg[0] == "PRT":
            self._print(mod, arg)
        elif arg[0] == "INP":
            value = self.io.input_str()
        elif arg[0] == "RND":
            n = int(_operand(arg, 1))
            if n >= 1:
                value = draw(self.rng, n)
        core, halted = self._state
        self._restore((handler(core, mod, arg, value), halted or arg[0] == "END"))

    def _print(self, mod: str, arg: list[str]) -> None:
        r"""Write what ``PRT`` names: a variable, or the top of the stack."""
        n = _named(self.var, _operand(arg, 1)) if "VAR" in mod else _top(self.stk)
        if "INT" in mod:
            self.io.print_num(n)
        else:
            self.io.print_char(chr(n))


def _top(stk: tuple[int, ...]) -> int:
    r"""Return the top of the stack, halting on an empty stack."""
    if not stk:
        raise HaltError("the stack is empty, so there is no top value to read")
    return stk[-1]


def _operand(arg: list[str], n: int) -> str:
    r"""Return the ``n``-th token of a command, rejecting a missing operand."""
    if n >= len(arg):
        raise ValueError(f"missing operand in {' '.join(arg)}")
    return arg[n]


def _named(var: Mapping[str, int], name: str) -> int:
    r"""Return the value of ``name``, halting when it is not a variable."""
    if name not in var:
        known = ", ".join(sorted(var)) or "none are defined yet"
        raise HaltError(f"{name} is not a defined variable ({known})")
    return var[name]


def _jmp(core: _Core, mod: str, arg: list[str], _value: str | int | None) -> _Core:
    r"""Jump relative, optionally only when the top matches an operand."""
    stk, var, ind = core
    cond = True
    val = _top(stk) if stk else 0

    if "NIF" in mod:
        cond = val != int(_operand(arg, -1))
    elif "IF" in mod:
        cond = val == int(_operand(arg, -1))

    if cond:
        if _operand(arg, 1) == "F":
            ind += int(_operand(arg, 2)) - 1
        else:
            ind -= int(_operand(arg, 2)) + 1
    return (stk, var, ind)


def _add(core: _Core, _mod: str, arg: list[str], _value: str | int | None) -> _Core:
    r"""Add an operand to the top of the stack."""
    stk, var, ind = core
    n = int(_operand(arg, 1))
    return ((*stk[:-1], _top(stk) + n), var, ind)


def _sub(core: _Core, _mod: str, arg: list[str], _value: str | int | None) -> _Core:
    r"""Subtract an operand from the top of the stack."""
    stk, var, ind = core
    n = int(_operand(arg, 1))
    return ((*stk[:-1], _top(stk) - n), var, ind)


def _rst(core: _Core, _mod: str, _arg: list[str], _value: str | int | None) -> _Core:
    r"""Send the cursor back to the first token."""
    stk, var, _ind = core
    return (stk, var, 0)


def _psh(core: _Core, mod: str, arg: list[str], _value: str | int | None) -> _Core:
    r"""Push a literal, the characters of a string, or store into a."""
    stk, var, ind = core
    if "INT" in mod:
        return ((*stk, int(_operand(arg, 2))), var, ind)
    if "STR" in mod:
        m = mod.split('"')[1]
        return ((*stk, *[ord(c) for c in m][::-1]), var, ind)
    if "VAR" in mod:
        # The store names its target.
        # does, so it rejects an.
        # the ``VARn+k`` arithmetic.
        # through created the variable.
        # -- the keyword spelling,.
        # into a phantom ``VAR`` and.
        name = _operand(arg, 1)
        _named(var, name)
        return (stk, {**var, name: _top(stk)}, ind)
    return core


def _pop(core: _Core, _mod: str, _arg: list[str], _value: str | int | None) -> _Core:
    r"""Discard the top of the stack."""
    stk, var, ind = core
    _top(stk)
    return (stk[:-1], var, ind)


def _swp(core: _Core, _mod: str, _arg: list[str], _value: str | int | None) -> _Core:
    r"""Move the second value to the top."""
    stk, var, ind = core
    if len(stk) < 2:
        were = "is 1" if len(stk) == 1 else f"are {len(stk)}"
        raise HaltError(f"SWP needs two values on the stack and there {were}")
    return ((*stk[:-2], stk[-1], stk[-2]), var, ind)


def _prt(core: _Core, mod: str, arg: list[str], _value: str | int | None) -> _Core:
    r"""Consume what the shell printed: a popped top, or nothing for a."""
    stk, var, ind = core
    if "VAR" in mod:
        _named(var, _operand(arg, 1))
        return core
    _top(stk)
    return (stk[:-1], var, ind)


def _inp(core: _Core, mod: str, _arg: list[str], value: str | int | None) -> _Core:
    r"""Push what the shell read."""
    stk, var, ind = core
    text = "" if value is None else str(value)
    if "INT" in mod and text:
        return ((*stk, int(text)), var, ind)
    if "INT" in mod:
        return core
    return ((*stk, *[ord(c) for c in text][::-1]), var, ind)


def _end(core: _Core, _mod: str, _arg: list[str], _value: str | int | None) -> _Core:
    r"""Halt: the shell reads the sentinel cursor and stops."""
    return core


def _dup(core: _Core, _mod: str, _arg: list[str], _value: str | int | None) -> _Core:
    r"""Push a copy of the top."""
    stk, var, ind = core
    return ((*stk, _top(stk)), var, ind)


def _rnd(core: _Core, _mod: str, arg: list[str], value: str | int | None) -> _Core:
    r"""Push the draw the shell made, rejecting a bound below one."""
    stk, var, ind = core
    n = int(_operand(arg, 1))
    if n < 1:
        raise HaltError(f"RND needs an upper bound of at least 1, got {n}")
    return ((*stk, int(value) if value is not None else 0), var, ind)


def _var_arith(core: _Core, mod: str) -> _Core:
    r"""Add to or subtract from a named variable, in place in the token."""
    stk, var, ind = core
    if "+" in mod:
        lhs, rhs = mod.split("+")
        return (stk, {**var, lhs: _named(var, lhs) + int(rhs)}, ind)
    # The caller only routes a.
    # so the one that is not a.
    lhs, rhs = mod.split("-")
    return (stk, {**var, lhs: _named(var, lhs) - int(rhs)}, ind)


_DISPATCH: dict[str, Callable[[_Core, str, list[str], str | int | None], _Core]] = {
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


def run(code: str, io: IO, rng: Randomness | None = None) -> None:
    r"""Run a Modulous program, drawing ``RND`` from ``rng``."""
    state = _Machine(code, io, rng)

    while not state.halted:
        state.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
