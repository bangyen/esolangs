r"""Interpreter for Interprogck8."""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from typing import cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Randomness, draw

_TRUE, _FALSE = 84, 81  # ASCII "T" and "Q", what.

# : Fixed ``developer`` output.
# : printing this module's own.
# : on disk, which no test.
_DEVELOPER = "Interprogck8\n"

# : The nullary commands,.
# : ``mathroundtofloor`` floors.
_ARITH: dict[str, int] = {"@nd": 1, "@nt": -1, "@id": 10, "@dd": -10}
_LOAD: dict[str, int] = {"NnNn": 0, "nNnN": 65, "Empty_": 32}
_NOPS = frozenset({"X", "x", "mathroundtofloor"})


def _pips(literal: str) -> int:
    r"""Return a dice literal's value, or raise on a non-literal."""
    if not literal or any(c not in ":." for c in literal):
        raise HaltError(f"not a dice literal: {literal!r}")
    return 2 * literal.count(":") + literal.count(".")


def _dice(value: int) -> str:
    r"""Return the canonical dice literal for ``value``."""
    return ":" * (value // 2) + "." * (value % 2)


@dataclass(frozen=True)
class _State:
    r"""One instant of a run."""

    lines: tuple[str, ...]
    ip: int = 0
    acc: int = 0
    slot: tuple[str, ...] | None = None
    frames: tuple[tuple[tuple[str, ...], int], ...] = ()

    @property
    def halted(self) -> bool:
        return not self.frames and self.ip >= len(self.lines)

    @property
    def current(self) -> str:
        r"""The line about to run: the innermost frame's, or the program's."""
        if self.frames:
            body, index = self.frames[-1]
            return body[index]
        return self.lines[self.ip]


def _advance_cursor(state: _State) -> _State:
    r"""Move past the line just executed, popping every finished frame."""
    if state.frames:
        body, index = state.frames[-1]
        frames = (*state.frames[:-1], (body, index + 1))
        while frames and frames[-1][1] >= len(frames[-1][0]):
            frames = frames[:-1]
        return replace(state, frames=frames)
    return replace(state, ip=state.ip + 1)


def _call(state: _State) -> _State:
    r"""Enter the current function, after advancing past the calling line."""
    if state.slot is None:
        raise HaltError("no current function to execute")
    state = _advance_cursor(state)
    if not state.slot:  # an empty body is a call that.
        return state
    return replace(state, frames=(*state.frames, (state.slot, 0)))


def _capture(state: _State) -> _State:
    r"""Fill the function slot from the ``<`` at the cursor and jump past."""
    if state.frames:
        raise HaltError("functions cannot be created inside other functions")
    end = state.ip + 1
    while end < len(state.lines) and state.lines[end] != ">":
        if state.lines[end] == "<":
            raise HaltError("nested function opener")
        end += 1
    if end >= len(state.lines):
        raise HaltError("unclosed function")
    body = state.lines[state.ip + 1 : end]
    return replace(state, slot=body, ip=end + 1)


def _restart(state: _State) -> _State:
    r"""Apply ``z``: drop it and the line before it, then start over."""
    if state.frames:
        raise HaltError("z has no unambiguous previous line inside a function")
    if state.ip == 0:
        raise HaltError("FirstLineError: z on the first line")
    lines = state.lines[: state.ip - 1] + state.lines[state.ip + 1 :]
    return _State(lines)


def _split_args(line: str) -> list[str]:
    r"""Return the three arguments of a ``{values/=a/=b/=c}`` line."""
    if not (line.startswith("{values/=") and line.endswith("}")):
        raise ValueError(line)
    args = line[len("{values") : -1].split("/=")
    if len(args) != 4 or args[0] != "":
        raise ValueError(line)
    return args[1:]


def _roll(spec: str, acc: int, rng: Randomness | None, byte: int | None) -> int:
    r"""Evaluate a ``[a b]`` bracket, which never writes the accumulator."""
    inner = spec[1:-1]
    parts = inner.split(" ")
    if len(parts) != 2:
        raise HaltError(f"malformed random range: {spec!r}")
    bounds = []
    for part in parts:
        if part == "":
            bounds.append(acc)
        elif part == "$py":
            if byte is None:
                raise HaltError("$py inside a range read nothing")
            bounds.append(byte)
        else:
            bounds.append(_pips(part))
    low, high = min(bounds), max(bounds)
    return low + draw(rng, high - low + 1)


def _value(arg: str, acc: int, rng: Randomness | None, byte: int | None) -> int:
    r"""Evaluate one ``{values...}`` argument without touching the."""
    if arg == "":
        return acc
    if arg in ("$py", "u"):
        if byte is None:
            raise HaltError(f"{arg} inside a comparison read nothing")
        return byte
    if arg.startswith("[") and arg.endswith("]"):
        return _roll(arg, acc, rng, byte)
    return _pips(arg)


def _read_kinds(line: str) -> tuple[str, ...]:
    r"""How ``line`` reads input: one ``"pips"``/``"ord"`` per read, in."""
    if line == "$py":
        return ("pips",)
    if line == "u":
        return ("ord",)
    if line.startswith("[") and line.endswith("]"):
        return tuple("pips" for p in line[1:-1].split(" ") if p == "$py")
    try:
        args = _split_args(line)
    except ValueError:
        return ()
    kinds: list[str] = []
    for arg in args:
        if arg == "$py":
            kinds.append("pips")
        elif arg == "u":
            kinds.append("ord")
        elif arg.startswith("[") and arg.endswith("]"):
            kinds += ["pips" for p in arg[1:-1].split(" ") if p == "$py"]
    return tuple(kinds)


def _advance(
    state: _State, rng: Randomness | None = None, reads: tuple[int, ...] = ()
) -> tuple[_State, str | None]:
    r"""Return the state after one line, and the text to print."""
    line = state.current
    acc, out = state.acc, None
    nxt: int | None = None

    if line in _ARITH:
        acc = (acc + _ARITH[line]) % 256
    elif line in _LOAD:
        acc = _LOAD[line]
    elif line in _NOPS:
        pass
    elif line == "~":
        out = "Interprogck8\n" if draw(rng, 10) == 0 else None
    elif line == "developer":
        out = _DEVELOPER
    elif line == "div":
        out = chr(acc)
    elif line == "$ay":
        out = _dice(acc)
    elif line == "Instruction26":
        out = chr(acc).join(str(i) for i in range(1, 27))
    elif line in ("$py", "u"):
        acc = reads[0]
    elif line == "DownAccLines":
        if state.frames:
            # The pointer inside a function.
            # program line, so "skip down N.
            raise HaltError("DownAccLines inside a function body")
        nxt = state.ip + 1 + acc
        if nxt > len(state.lines):
            raise HaltError("EOFError: not enough lines to skip down")
    elif line == "<":
        return _capture(state), None
    elif line == ">":
        pass  # a stray closer outside a.
    elif line == "EXE":
        return _call(replace(state, acc=acc)), None
    elif line == "IFT":
        if acc == _TRUE:
            return _call(state), None
    elif line == "IFQ":
        if acc == _FALSE:
            return _call(state), None
    elif line == "z":
        return _restart(state), None
    elif line.startswith("["):
        acc = _roll(line, acc, rng, reads[0] if reads else None)
    else:
        try:
            args = _split_args(line)
        except ValueError:
            raise HaltError(f"unknown instruction: {line!r}") from None
        taken = iter(reads)
        values = [
            _value(a, state.acc, rng, next(taken, None) if _read_kinds(a) else None)
            for a in args
        ]
        acc = _FALSE if values[0] == values[1] == values[2] else _TRUE

    state = replace(state, acc=acc)
    if nxt is not None:
        return replace(state, ip=nxt), out
    return _advance_cursor(state), out


# : A ``_State`` flattened for.
# : without the output the.
type _BranchState = tuple[
    tuple[str, ...],
    int,
    int,
    tuple[str, ...] | None,
    tuple[tuple[tuple[str, ...], int], ...],
]


class _Pinned:
    r"""A :class:`Randomness` answering every draw with one fixed value."""

    def __init__(self, value: int) -> None:
        self._value = value

    def randbelow(self, upper: int) -> int:
        return self._value % upper


def _branch_state(state: object) -> _State:
    r"""Rebuild a ``_State`` from a branching-search tuple."""
    return _State(*cast("_BranchState", state))


def _draw_range(line: str) -> int:
    r"""How many distinct outcomes ``line`` has: 1 unless it draws."""
    if line == "~":
        return 10
    return 256 if line.startswith("[") and line.endswith("]") else 1


def _outcomes(state: _State) -> tuple[_State, ...]:
    r"""Every state one line could reach, one per draw it could make."""
    seen: dict[_State, None] = {}
    for draw_value in range(_draw_range(state.current)):
        nxt, _out = _advance(state, _Pinned(draw_value))
        seen.setdefault(nxt, None)
    return tuple(seen)


class _Machine:
    r"""The run state: the program lines, accumulator, slot, and call stack."""

    def __init__(
        self,
        code: str | list[str],
        io: IO,
        rng: Randomness | None = None,
    ) -> None:
        lines = code.splitlines() if isinstance(code, str) else list(code)
        if not lines:
            raise ValueError("empty program")
        self.state = _State(tuple(lines))
        self.io = io
        self.rng = rng

    @property
    def halted(self) -> bool:
        return self.state.halted

    # : ``ip`` starts with a line.
    # : with each open frame's.
    ip_shape = "line"

    @property
    def ip(self) -> int | tuple[int, ...]:
        r"""The instruction position: the line, plus each open frame's index."""
        return (self.state.ip, *(index for _body, index in self.state.frames))

    @property
    def memory(self) -> list[int]:
        r"""The one addressable cell."""
        return [self.state.acc]

    @property
    def stack(self) -> list[object]:
        r"""The call stack, one entry per open ``EXE``."""
        return [index for _body, index in self.state.frames]

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete state, hashable, with the cursor and the slot."""
        s = self.state
        return (s.lines, s.ip, s.acc, s.slot, s.frames, self.io.position())

    # The branching-search protocol.
    # instructions, so a hang proof.
    # than the one a source.
    # declines instead of forking,.
    # cannot share one input cursor.

    def branching_snapshot(self) -> tuple[object, ...]:
        r"""Return the state a search starts from, output deliberately absent."""
        s = self.state
        return (s.lines, s.ip, s.acc, s.slot, s.frames)

    def branching_halted(self, state: object) -> bool:
        r"""Report whether a search state has run off the program."""
        return _branch_state(state).halted

    def branching_successors(
        self, state: object, _limit: int
    ) -> tuple[tuple[object, ...], ...] | None:
        r"""Every state this line could reach, over all draws it could make."""
        current = _branch_state(state)
        if _read_kinds(current.current):
            return None
        try:
            reached = _outcomes(current)
        except HaltError:
            # A line the run cannot execute.
            # ending the search: an.
            return ()
        return tuple(
            (nxt.lines, nxt.ip, nxt.acc, nxt.slot, nxt.frames) for nxt in reached
        )

    def step(self) -> None:
        r"""Execute one line; the two ports live here and nowhere else."""
        if self.halted:
            return  # a step past the end is a.
        line = self.state.current
        reads = []
        for kind in _read_kinds(line):
            # ``u``'s EmptyInputError is.
            # error here rather than the.
            # of input is the different.
            val = self.io.input_str()
            if not val:
                raise HaltError("EmptyInputError: empty input")
            reads.append(_pips(val) if kind == "pips" else ord(val[0]))
        state, out = _advance(self.state, self.rng, tuple(reads))
        self.state = state
        if out:
            self.io.print_str(out)


def run(code: str | list[str], io: IO, rng: Randomness | None = None) -> None:
    r"""Run ``code`` to its halt; ``rng`` pins ``[a b]`` and ``~``."""
    machine = _Machine(code, io, rng)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
