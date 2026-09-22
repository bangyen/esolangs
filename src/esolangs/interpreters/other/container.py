"""Interpreter for Container.

The first line declares rules (``name = initial`` or a bare ``name``);
following indented lines attach conditional deltas (``n cond``) to the
most recent container.  Each tick updates every container from the *old*
values; PRINT outputs OUT as a byte when it turns on, the empty-named
container reads a line into IN when it fires, and EXIT halts.  A rule
before any declaration raises :class:`ValueError`; an empty program halts
at once; exhausted input raises :class:`EOFError`.  :func:`run` returns
the EXIT code (``None`` if EXIT never fired) rather than exiting.

:func:`_advance` is a pure transition over an immutable ``_State`` with
no ``io`` argument.  The shell computes the tick, does the two effects
that compare old against new values, and hands the read byte to the
transition; :class:`_Machine` rebinds one state per ``step()``.
"""

from __future__ import annotations

from esolangs.interpreters._entry import script_main
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
#: changed to is what ``run`` returns.
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
    """Return every container's value after one update, in name order."""
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

        :func:`_ports` decides the print and the read from the old/new
        comparison, :func:`_advance` decides EXIT.
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

    EXIT instead fires on any *change*, so a program can exit with zero.
    """
    return (
        _has(variables, name) and _get(variables, name) == 0 and bool(_get(new, name))
    )


def _ports(variables: _Vars, new: _Vars) -> tuple[int | None, bool]:
    """Return what the tick wants done: a byte to print, and whether to read.

    ``PRINT`` prints OUT modulo 128, and only when OUT exists.
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

    ``new`` is the computed tick, ``queue`` the remaining input, ``byte``
    what the read took and writes into IN.  EXIT halts on a *change*, and
    the new value is the code.
    """
    variables, _queue, exit_code, count = state
    if byte is not None:
        new = tuple(sorted({**dict(new), "IN": byte}.items()))
    if _has(variables, "EXIT") and _get(variables, "EXIT") != _get(new, "EXIT"):
        exit_code = _get(new, "EXIT")
    return (new, queue, exit_code, count + 1)


def run(code: list[str], io: IO) -> int | None:
    """Run a Container program by ticking its rules until EXIT fires.

    Returns the EXIT code, or ``None``; EXIT is the normal halt.  Only the
    ``__main__`` block turns the code into a process exit.
    """
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    return machine.exit_code


if __name__ == "__main__":
    script_main(run, shape="keep")
