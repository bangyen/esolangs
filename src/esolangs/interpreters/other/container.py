"""Interpreter for Container.

The first line declares rules: ``name = initial`` or a bare ``name``, and
following indented lines attach conditional deltas (``n cond``) to the most
recent container.  Each tick updates every container by its satisfied rules;
PRINT outputs OUT as a byte when it turns on, the empty-named container reads
a line of input into the IN container when it fires, and EXIT halts the
program.

A rule line before any container declaration is a malformed program and is
rejected with :class:`ValueError`; an empty program halts immediately.

Exhausted input raises :class:`EOFError` (the repo-wide convention).

The interpreter runs on a :class:`_Machine` (the containers, their current
values, and the exit code once EXIT fires), so it is step-capable:
``step()`` executes one full tick and ``halted`` is true once EXIT fires.
:func:`run` still raises :class:`SystemExit` on halt, matching the
original's direct ``sys.exit`` call.

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and the container rules to the next state,
and never mutates what it is given.  It takes no ``io`` argument at all, so
it is total and side-effect free by construction rather than by inspection.

A tick is where this language differs from the others in the series.  Every
container updates at once from the *old* values, and then three things --
PRINT's output, the empty container's read, and EXIT -- fire on comparisons
between the old and new values.  So the shell computes what the tick will
produce, does the two effects, and hands the read byte to the transition,
which is what actually builds the next state.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what Container *does* stays in
the pure layer.
"""

from __future__ import annotations

import sys

from esolangs.interpreters.io import IO

#: The container values, as an immutable name->value mapping in name order,
#: so one logical set of values has exactly one spelling.
type _Vars = tuple[tuple[str, int], ...]

#: One instant of a run: ``(vars, queue, exit_code, tick)`` -- the container
#: values, the pending input characters, the EXIT code once it fires, and
#: the tick counter.  A value, not a record: every transition below returns
#: a new one rather than editing one in place.
#:
#: ``exit_code`` is state because halting here is a value a tick produces,
#: not a position: EXIT changing is what stops the run, and the code it
#: changed to is what ``run`` exits with.
#:
#: ``tick`` is deliberately excluded from ``snapshot``: it counts steps, not
#: state, and including it would make every state unique by construction
#: and reduce the cycle detector to a step budget.
type _State = tuple[_Vars, tuple[str, ...], int | None, int]


def _get(variables: _Vars, name: str) -> int:
    """Return the value of container ``name``."""
    for key, value in variables:
        if key == name:
            return value
    # Unreachable from this module's call sites, and kept as the contract
    # rather than as a live path.  Every `_get` against the *old* variables
    # is guarded by a matching `_has`, and every `_get` against the *new*
    # ones is safe for a structural reason: `_tick` rebuilds its result from
    # `obj` -- one entry per declared container -- so a tick cannot drop a
    # name that was there before it.  Measured over a run of the input
    # example: zero key-set differences between a tick's input and output.
    raise KeyError(name)  # pragma: no cover - see above


def _has(variables: _Vars, name: str) -> bool:
    """Whether a container named ``name`` was declared."""
    return any(key == name for key, _ in variables)


def _tick(obj: list[Con], variables: _Vars) -> _Vars:
    """Return every container's value after one update, in name order.

    All of them update from the same old values, which is what makes a tick
    simultaneous rather than sequential.
    """
    old = dict(variables)
    return tuple(sorted((o.name, o.update(old)) for o in obj))


class Con:
    """A named container whose rules add deltas to its value each tick."""

    def __init__(self, name: str) -> None:
        """Create a container with the given ``name`` and no rules."""
        self.name = name
        self.rules: list[tuple[int, str]] = []

    def add(self, cond: str) -> None:
        """Append a rule ``n cond`` that adds ``n`` when ``cond`` holds."""
        n, c = cond.split()
        self.rules.append((int(n), c))

    def update(self, var: dict[str, int]) -> int:
        """Return the value after applying every satisfied rule."""

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
    """Per-run Container state: the containers, their values, and EXIT."""

    def __init__(self, code: list[str], io: IO) -> None:
        """Parse ``code`` into containers and start every value at rest."""
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

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def var(self) -> dict[str, int]:
        """The container values, by name."""
        return dict(self.state[0])

    @property
    def queue(self) -> list[str]:
        """The input characters read but not yet consumed."""
        return list(self.state[1])

    @property
    def exit_code(self) -> int | None:
        """The code EXIT halted with, or None while the run continues."""
        return self.state[2]

    @property
    def tick(self) -> int:
        """How many ticks have run."""
        return self.state[3]

    @property
    def halted(self) -> bool:
        """Whether EXIT has fired, or there was nothing to evaluate."""
        return self.state[2] is not None or not self.obj

    # The VM's language-shaped view: Named containers + tick count; ip the tick, memory
    # the values.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.state[3]

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        # The values are kept in name order, so this is already sorted.
        return [value for _name, value in self.state[0]]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        variables, queue, exit_code, _tick_count = self.state
        return (variables, queue, exit_code)
        # tick is excluded: it counts steps, not state, and always differs

    def step(self) -> None:
        """Execute one full tick, updating every container's value.

        The tick is computed first, because all three of the things that
        can happen -- PRINT's output, the read, and EXIT -- compare the old
        values against the new ones.  :func:`_ports` decides the first two
        from that comparison and :func:`_advance` the third; this performs
        what they report and hands the read's byte on.
        """
        if self.halted:
            return
        variables, queue, _exit, _count = self.state
        new = _tick(self.obj, variables)
        output, reads = _ports(variables, new)

        if output is not None:
            self.io.print_char(chr(output))

        byte = None
        if reads:
            # The read blocks until there is a character to take, which is
            # an effect and so belongs here rather than in the transition.
            while not queue:
                queue = tuple(self.io.input_str())
            byte = ord(queue[0])
            queue = queue[1:]

        self.state = _advance(self.state, new, queue, byte)


def _rises(variables: _Vars, new: _Vars, name: str) -> bool:
    """Whether ``name`` goes from zero to nonzero across a tick.

    A container fires on the rising edge, which is why both its old and
    its new value matter.  EXIT is the exception and is decided in
    :func:`_advance`: it fires on any *change*, so that a program can exit
    with zero.
    """
    return (
        _has(variables, name) and _get(variables, name) == 0 and bool(_get(new, name))
    )


def _ports(variables: _Vars, new: _Vars) -> tuple[int | None, bool]:
    """Return what the tick wants done: a byte to print, and whether to read.

    Pure: it compares the two ticks and reports.  The shell performs both,
    which keeps the rules for *when* a container fires here with the rest
    of the language rather than beside the ``io`` calls that carry them
    out.  ``PRINT`` prints OUT modulo 128, and only when OUT exists.
    """
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
    """Return the state a tick lands on.

    Pure: it reads ``state`` and returns a new one.  ``new`` is the tick the
    shell already computed, ``queue`` what is left of the input after any
    read, and ``byte`` the character that read took -- so the two effects
    are already done and only their consequences arrive here.

    A read writes its byte into IN, overriding whatever the tick computed
    for that container.  EXIT halts when its value *changes*, and the value
    it changed to is the code, which is why a program can exit with zero.
    """
    variables, _queue, exit_code, count = state
    if byte is not None:
        new = tuple(sorted({**dict(new), "IN": byte}.items()))
    if _has(variables, "EXIT") and _get(variables, "EXIT") != _get(new, "EXIT"):
        exit_code = _get(new, "EXIT")
    return (new, queue, exit_code, count + 1)


def run(code: list[str], io: IO) -> None:
    """Run a Container program by ticking its rules until EXIT fires."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    if machine.exit_code is not None:
        sys.exit(machine.exit_code)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
