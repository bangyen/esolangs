"""Interpreter for Modulous.

Commands are written as ``[OP arg]`` tokens.  PSH pushes an integer, string,
or variable value; POP/SWP/DUP reshape the stack; PRT prints the top as an
integer or byte; INP reads a line; JMP/IF conditionally jump; RST resets the
pointer to the start of the program; and END halts.

The wiki declares four variables (VAR1-VAR4), and those are the four that
exist: every variable op -- the ``PSH`` store, the ``PRT`` read, and the
``VARn+k``/``VARn-k`` arithmetic -- halts on any other name.  The store
used to be the exception, creating whatever name it was given, which made
``[PSH VAR VAR1]`` (the keyword spelling; the syntax is ``[PSH VAR1]``)
store into a phantom ``VAR`` and silently leave ``VAR1`` alone.

Operations that act on an empty stack, an undefined variable, or a missing
operand are invalid: they halt the program with
:class:`~esolangs.exceptions.HaltError`, and a malformed token (a missing
required argument) is rejected with :class:`ValueError`.

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import re
import sys
from collections.abc import Callable, Mapping
from typing import cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Randomness, draw

#: A command is a bracketed group, which may hold one quoted string.
_TOKEN = re.compile(r'\[([^\[\]\"]*("[^"]*")?)]')


#: One instant of a run: ``(stk, var, ind)`` -- the data stack, the four
#: named variables, and the token cursor.
#:
#: The tokens stay out: Modulous parses its program once and never
#: rewrites it, so a handler is handed the token it is running rather than
#: carrying the list.
type _Core = tuple[tuple[int, ...], dict[str, int], int]

#: Every value a Modulous step can change: the handler's stack, variables,
#: and cursor, plus whether ``END`` has stopped the run.  Tokens are parsed
#: once and never rewritten, while ports and randomness stay in the shell.
type _State = tuple[_Core, bool]

#: One instant as the all-outcomes search sees it.  Identical to
#: :data:`_State` except that ``var`` is the sorted tuple of its items --
#: a dict cannot be a member of the search's visited set.
type _FrozenCore = tuple[tuple[int, ...], tuple[tuple[str, int], ...], int]
type _BranchState = tuple[_FrozenCore, bool]


#: The most outcomes one ``RND`` may open in a branching search.  Its range
#: is a program operand rather than a fixed coin, so a single token can ask
#: for more states than any search wants to hold.  This is deliberately a
#: property of the transition rather than the caller's remaining budget:
#: that budget shrinks as the search proceeds, which would make the same
#: program decidable or not depending on when the token was reached.
_RND_FANOUT = 256


def _freeze(state: _State) -> _BranchState:
    """Return ``state`` with its variable map made hashable."""
    (stk, var, ind), halted = state
    return ((stk, tuple(sorted(var.items())), ind), halted)


def _thaw(state: _BranchState) -> _State:
    """Invert :func:`_freeze` so a handler sees the map it expects."""
    (stk, var, ind), halted = state
    return ((stk, dict(var), ind), halted)


class _Machine:
    """Stack, variables, and instruction pointer for a Modulous run."""

    stk: tuple[int, ...]
    var: dict[str, int]
    ind: int
    io: IO
    tokens: tuple[str, ...]
    _halted: bool
    # Overrides ``RND``'s draw, which is what makes a stepped run
    # reproducible; ``None`` draws for real.
    rng: Randomness | None

    def __init__(self, code: str, io: IO, rng: Randomness | None = None) -> None:
        """Build a state for ``code`` with its variables and parsed tokens."""
        self.stk = ()
        self.var = {f"VAR{k}": 0 for k in range(1, 5)}
        self.ind = 0
        self.io = io
        self.tokens = tuple(k[0] for k in _TOKEN.findall(code))
        self._halted = False
        self.rng = rng

    @property
    def halted(self) -> bool:
        """Whether the instruction pointer has run off the program."""
        return self._halted or self.ind >= len(self.tokens)

    # The VM's language-shaped view: the store is the stack, and the named
    # variables are not addressable cells, so ``memory`` stays empty.

    @property
    def ip(self) -> int:
        """The token cursor."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """No addressable cells; the store is the stack."""
        return []

    @property
    def stack(self) -> list[object]:
        """The data stack, bottom first."""
        return list(self.stk)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            self.stk,
            tuple(sorted(self.var.items())),
            self.io.position(),
            self._halted,
        )

    # The all-random-outcomes search.  ``_Core`` holds ``var`` as a dict,
    # which a search cannot key on, so the branching state carries it as
    # the sorted tuple ``snapshot`` already uses and rebuilds the dict on
    # the way back in.  The input cursor is left out: ``INP`` declines
    # rather than forking, and output cannot affect a later token.

    def branching_snapshot(self) -> _BranchState:
        """Return the current state as the search's starting point."""
        return _freeze(self._state)

    def branching_halted(self, state: object) -> bool:
        """Report whether ``state`` has ended or run off the program.

        Unlike a machine-shaped halt this reads the value alone: ``END``
        sets the flag inside the state, and running off the token list is a
        property of the cursor, so both live in the tuple.
        """
        (_stk, _var, ind), halted = cast(_BranchState, state)
        return halted or ind >= len(self.tokens)

    def branching_successors(
        self, state: object, _limit: int
    ) -> tuple[_BranchState, ...] | None:
        """Return the state for every value ``RND`` could draw.

        Mirrors :meth:`step`, whose cursor advances *before* the handler
        runs, so a successor that dispatched on the un-advanced core would
        re-run the same token forever.

        ``RND n`` takes its range from the program text rather than from a
        fixed coin, so one token can ask for arbitrarily many outcomes;
        that is charged against ``limit`` instead of being materialized.
        ``n < 1`` draws nothing and is left to the single deterministic
        call, exactly as the step leaves it.
        """
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
        """The complete changing state, with the handler core inside it."""
        return ((self.stk, self.var, self.ind), self._halted)

    def _restore(self, state: _State) -> None:
        """Write a transition result back onto the machine shell."""
        (stk, var, self.ind), self._halted = state
        self.stk = stk
        self.var = var

    def step(self) -> None:
        """Execute one ``[OP arg]`` token, advancing the pointer.

        The three effectful commands are answered here rather than by their
        handlers: ``PRT`` prints the value the handler then consumes,
        ``INP`` takes a line, and ``RND`` draws.  Everything else is a pure
        map from one core to the next.
        """
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
        """Write what ``PRT`` names: a variable, or the top of the stack."""
        n = _named(self.var, _operand(arg, 1)) if "VAR" in mod else _top(self.stk)
        if "INT" in mod:
            self.io.print_num(n)
        else:
            self.io.print_char(chr(n))


def _top(stk: tuple[int, ...]) -> int:
    """Return the top of the stack, halting on an empty stack."""
    if not stk:
        raise HaltError
    return stk[-1]


def _operand(arg: list[str], n: int) -> str:
    """Return the ``n``-th token of a command, rejecting a missing operand."""
    if n >= len(arg):
        raise ValueError(f"missing operand in {' '.join(arg)}")
    return arg[n]


def _named(var: Mapping[str, int], name: str) -> int:
    """Return the value of ``name``, halting when it is not a variable."""
    if name not in var:
        raise HaltError
    return var[name]


def _jmp(core: _Core, mod: str, arg: list[str], _value: str | int | None) -> _Core:
    """Jump relative, optionally only when the top matches an operand."""
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
    """Add an operand to the top of the stack."""
    stk, var, ind = core
    n = int(_operand(arg, 1))
    return ((*stk[:-1], _top(stk) + n), var, ind)


def _sub(core: _Core, _mod: str, arg: list[str], _value: str | int | None) -> _Core:
    """Subtract an operand from the top of the stack."""
    stk, var, ind = core
    n = int(_operand(arg, 1))
    return ((*stk[:-1], _top(stk) - n), var, ind)


def _rst(core: _Core, _mod: str, _arg: list[str], _value: str | int | None) -> _Core:
    """Send the cursor back to the first token."""
    stk, var, _ind = core
    return (stk, var, 0)


def _psh(core: _Core, mod: str, arg: list[str], _value: str | int | None) -> _Core:
    """Push a literal, the characters of a string, or store into a variable."""
    stk, var, ind = core
    if "INT" in mod:
        return ((*stk, int(_operand(arg, 2))), var, ind)
    if "STR" in mod:
        m = mod.split('"')[1]
        return ((*stk, *[ord(c) for c in m][::-1]), var, ind)
    if "VAR" in mod:
        # The store names its target the same way every other variable op
        # does, so it rejects an unknown name the same way too: ``PRT`` and
        # the ``VARn+k`` arithmetic both halt on one, and letting the store
        # through created the variable instead.  That made ``[PSH VAR VAR1]``
        # -- the keyword spelling, which the syntax is ``[PSH VAR1]`` -- store
        # into a phantom ``VAR`` and silently do nothing to ``VAR1``.
        name = _operand(arg, 1)
        _named(var, name)
        return (stk, {**var, name: _top(stk)}, ind)
    return core


def _pop(core: _Core, _mod: str, _arg: list[str], _value: str | int | None) -> _Core:
    """Discard the top of the stack."""
    stk, var, ind = core
    _top(stk)
    return (stk[:-1], var, ind)


def _swp(core: _Core, _mod: str, _arg: list[str], _value: str | int | None) -> _Core:
    """Move the second value to the top."""
    stk, var, ind = core
    if len(stk) < 2:
        raise HaltError
    return ((*stk[:-2], stk[-1], stk[-2]), var, ind)


def _prt(core: _Core, mod: str, arg: list[str], _value: str | int | None) -> _Core:
    """Consume what the shell printed: a popped top, or nothing for a variable."""
    stk, var, ind = core
    if "VAR" in mod:
        _named(var, _operand(arg, 1))
        return core
    _top(stk)
    return (stk[:-1], var, ind)


def _inp(core: _Core, mod: str, _arg: list[str], value: str | int | None) -> _Core:
    """Push what the shell read.

    ``INT`` pushes the line as one number and the bare form pushes its
    characters, rightmost on top -- so what arrives is a sequence either
    way, and an empty ``INT`` read pushes nothing at all.
    """
    stk, var, ind = core
    text = "" if value is None else str(value)
    if "INT" in mod and text:
        return ((*stk, int(text)), var, ind)
    if "INT" in mod:
        return core
    return ((*stk, *[ord(c) for c in text][::-1]), var, ind)


def _end(core: _Core, _mod: str, _arg: list[str], _value: str | int | None) -> _Core:
    """Halt: the shell reads the sentinel cursor and stops."""
    return core


def _dup(core: _Core, _mod: str, _arg: list[str], _value: str | int | None) -> _Core:
    """Push a copy of the top."""
    stk, var, ind = core
    return ((*stk, _top(stk)), var, ind)


def _rnd(core: _Core, _mod: str, arg: list[str], value: str | int | None) -> _Core:
    """Push the draw the shell made, rejecting a bound below one."""
    stk, var, ind = core
    n = int(_operand(arg, 1))
    if n < 1:
        raise HaltError
    return ((*stk, int(value) if value is not None else 0), var, ind)


def _var_arith(core: _Core, mod: str) -> _Core:
    """Add to or subtract from a named variable, in place in the token."""
    stk, var, ind = core
    if "+" in mod:
        lhs, rhs = mod.split("+")
        return (stk, {**var, lhs: _named(var, lhs) + int(rhs)}, ind)
    # The caller only routes a token here when it holds a ``+`` or a ``-``,
    # so the one that is not a ``+`` is a ``-``.
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
    """Run a Modulous program, drawing ``RND`` from ``rng``.

    ``rng`` is the source ``RND`` draws from; ``None`` draws for real,
    which is the spec's behaviour and what a plain run gets.  The machine
    has always taken one -- it is how the VM makes a stepped run
    reproducible -- but ``run`` did not forward it, so a caller holding
    only ``run`` could not pin the draw without patching ``secrets``
    globally.  This is the signature COD, WII2D and LaserFuck take.
    """
    state = _Machine(code, io, rng)

    while not state.halted:
        state.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
