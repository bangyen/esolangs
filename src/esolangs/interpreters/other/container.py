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
"""

import sys

from esolangs.interpreters.io import IO


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
        self.queue: list[str] = []
        self.obj: list[Con] = []
        self.var: dict[str, int] = {}
        self.exit_code: int | None = None
        self.tick = 0

        for raw in code:
            line = raw.strip()
            if ":" in line:
                line = line[:-1]
                if "=" in line:
                    x, y = line.split("=")
                    self.var[x] = int(y)
                    self.obj.append(Con(x))
                else:
                    self.var[line] = 0
                    self.obj.append(Con(line))
            elif line:
                if not self.obj:
                    raise ValueError("rule line before any container declaration")
                self.obj[-1].add(line)

    @property
    def halted(self) -> bool:
        """Whether EXIT has fired, or there was nothing to evaluate."""
        return self.exit_code is not None or not self.obj

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            tuple(sorted(self.var.items())),
            tuple(self.queue),
            self.exit_code,
        )  # tick is excluded: it counts steps, not state, and always differs

    def step(self) -> None:
        """Execute one full tick, updating every container's value."""
        if self.halted:
            return
        var = self.var
        new = {o.name: o.update(var) for o in self.obj}

        if "PRINT" in var and var["PRINT"] == 0 and bool(new["PRINT"]) and "OUT" in var:
            self.io.print_char(chr(new["OUT"] % (1 << 7)))
        if "" in var and var[""] == 0 and bool(new[""]):
            while not self.queue:
                s = self.io.input_str()
                self.queue += list(s)

            new["IN"] = ord(self.queue[0])
            self.queue = self.queue[1:]
        if "EXIT" in var and var["EXIT"] != new["EXIT"]:
            self.exit_code = new["EXIT"]

        self.var = new
        self.tick += 1


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
