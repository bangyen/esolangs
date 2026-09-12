r"""Interpreter for Container."""

from __future__ import annotations

import sys

from esolangs.interpreters.io import IO

# : The container values, as an.
# : so one logical set of.
type _Vars = tuple[tuple[str, int], ...]

# : One instant of a run:.
# : values, the pending input.
# : the tick counter.
# : a new one rather than.
# :.
# : ``exit_code`` is state.
# : not a position: EXIT.
# : changed to is what ``run``.
# :.
# : ``tick`` is deliberately.
# : state, and including it.
# : and reduce the cycle.
type _State = tuple[_Vars, tuple[str, ...], int | None, int]


def _get(variables: _Vars, name: str) -> int:
    r"""Return the value of container ``name``."""
    for key, value in variables:
        if key == name:
            return value
    # Unreachable from this.
    # rather than as a live path.
    # is guarded by a matching.
    # ones is safe for a structural.
    # `obj` -- one entry per.
    # name that was there before it.
    # example: zero key-set.
    raise KeyError(name)  # pragma: no cover - see above


def _has(variables: _Vars, name: str) -> bool:
    r"""Whether a container named ``name`` was declared."""
    return any(key == name for key, _ in variables)


def _tick(obj: list[Con], variables: _Vars) -> _Vars:
    r"""Return every container's value after one update, in name order."""
    old = dict(variables)
    return tuple(sorted((o.name, o.update(old)) for o in obj))


class Con:
    r"""A named container whose rules add deltas to its value each tick."""

    def __init__(self, name: str) -> None:
        r"""Create a container with the given ``name`` and no rules."""
        self.name = name
        self.rules: list[tuple[int, str]] = []

    def add(self, cond: str) -> None:
        r"""Append a rule ``n cond`` that adds ``n`` when ``cond`` holds."""
        n, c = cond.split()
        self.rules.append((int(n), c))

    def update(self, var: dict[str, int]) -> int:
        r"""Return the value after applying every satisfied rule."""

        def val(s: str) -> int:
            if s in var:
                return var[s]
            return int(s)

        res = var[self.name]
        for n, c in self.rules:
            if "<" in c:
                x, y = c.split("<=")
                b = val(x) <= val(y)
            else:
                x, y = c.split(">=")
                b = val(x) >= val(y)

            if b:
                res += n

        return max(res, 0)


class _Machine:
    r"""Per-run Container state: the containers, their values, and EXIT."""

    def __init__(self, code: list[str], io: IO) -> None:
        r"""Parse ``code`` into containers and start every value at rest."""
        self.io = io
        self.obj: list[Con] = []
        start: dict[str, int] = {}

        for raw in code:
            line = raw.strip()
            if ":" in line:
                line = line[:-1]
                if "=" in line:
                    x, y = line.split("=")
                    start[x] = int(y)
                    self.obj.append(Con(x))
                else:
                    start[line] = 0
                    self.obj.append(Con(line))
            elif line:
                if not self.obj:
                    raise ValueError("rule line before any container declaration")
                self.obj[-1].add(line)

        self.state: _State = (tuple(sorted(start.items())), (), None, 0)

    # The language's own names.
    # than fields of their own, so.

    @property
    def var(self) -> dict[str, int]:
        r"""The container values, by name."""
        return dict(self.state[0])

    @property
    def queue(self) -> list[str]:
        r"""The input characters read but not yet consumed."""
        return list(self.state[1])

    @property
    def exit_code(self) -> int | None:
        r"""The code EXIT halted with, or None while the run continues."""
        return self.state[2]

    @property
    def tick(self) -> int:
        r"""How many ticks have run."""
        return self.state[3]

    @property
    def halted(self) -> bool:
        r"""Whether EXIT has fired, or there was nothing to evaluate."""
        return self.state[2] is not None or not self.obj

    # The VM's language-shaped.
    # the values.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.state[3]

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        # The values are kept in name.
        return [value for _name, value in self.state[0]]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        variables, queue, exit_code, _tick_count = self.state
        return (variables, queue, exit_code)
        # tick is excluded: it counts.

    def step(self) -> None:
        r"""Execute one full tick, updating every container's value."""
        if self.halted:
            return
        variables, queue, _exit, _count = self.state
        new = _tick(self.obj, variables)
        output, reads = _ports(variables, new)

        if output is not None:
            self.io.print_char(chr(output))

        byte = None
        if reads:
            # The read blocks until there.
            # an effect and so belongs here.
            while not queue:
                queue = tuple(self.io.input_str())
            byte = ord(queue[0])
            queue = queue[1:]

        self.state = _advance(self.state, new, queue, byte)


def _rises(variables: _Vars, new: _Vars, name: str) -> bool:
    r"""Whether ``name`` goes from zero to nonzero across a tick."""
    return (
        _has(variables, name) and _get(variables, name) == 0 and bool(_get(new, name))
    )


def _ports(variables: _Vars, new: _Vars) -> tuple[int | None, bool]:
    r"""Return what the tick wants done: a byte to print, and whether to."""
    output = None
    if _rises(variables, new, "PRINT") and _has(variables, "OUT"):
        output = _get(new, "OUT") % (1 << 7)
    return output, _rises(variables, new, "")


def _advance(
    state: _State,
    new: _Vars,
    queue: tuple[str, ...],
    byte: int | None,
) -> _State:
    r"""Return the state a tick lands on."""
    variables, _queue, exit_code, count = state
    if byte is not None:
        new = tuple(sorted({**dict(new), "IN": byte}.items()))
    if _has(variables, "EXIT") and _get(variables, "EXIT") != _get(new, "EXIT"):
        exit_code = _get(new, "EXIT")
    return (new, queue, exit_code, count + 1)


def run(code: list[str], io: IO) -> int | None:
    r"""Run a Container program by ticking its rules until EXIT fires."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    return machine.exit_code


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            code = run(data, IO())
        if code is not None:
            sys.exit(code)
