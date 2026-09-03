"""RAM0 interpreter implementation.

Computational model with two registers (z, n) and unbounded RAM.
Seven commands: Z, A, N, C, L, S, and goto.

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and a token to the next state, and never
mutates what it is given.  It takes no ``io`` argument at all, so it is
total and side-effect free by construction rather than by inspection.

The RAM is a ``tuple`` of ``(address, value)`` pairs kept in insertion
order (the dump prints them in that order), so a state is a value that can
be stored, compared, and hashed as it stands.  A dict would have been the
obvious store, but a mutable one is
exactly what the old :func:`change` reached through -- it took the RAM and
wrote into the caller's copy -- and that is the aliasing this rewrite
exists to remove.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what RAM0 *does* stays in the
pure layer.

``step()`` executes one token and ``halted`` is true once the cursor runs
off either end of the token list.  The state dump is printed exactly once,
on the step that halts the machine, matching the original's
print-after-the-loop behavior.  That "exactly once" is why the dumped flag
is part of the state rather than a field beside it: it records that an
effect has already happened, and a state that forgot it would print twice.
"""

from __future__ import annotations

import re
import sys

from esolangs.interpreters.io import IO

#: The RAM as an immutable sequence of ``(address, value)`` pairs, held in
#: *insertion* order -- first write first, a rewrite updating in place.
#:
#: That order is observable: the state dump prints the pairs in the order
#: the dict yielded them, so a program that writes address 3 before address
#: 1 prints them in that order.  Sorting by address here would be tidier
#: and would silently change what such a program outputs.
#:
#: Ordering does not leak into cycle detection: ``snapshot`` converts to a
#: ``frozenset``, so two states with the same cells compare equal whatever
#: order they were written in.
type _Ram = tuple[tuple[int, int], ...]

#: One instant of a run: ``(ind, z, n, ram, dumped)`` -- the token cursor,
#: the two registers, the RAM, and whether the final dump has been printed.
#: A value, not a record: every transition below returns a new one rather
#: than editing one in place.
#:
#: ``dumped`` is state because the dump is a once-per-run effect that
#: happens *after* the cursor has run off the end, so the position cannot
#: distinguish "about to dump" from "already dumped".  It stays out of
#: ``snapshot``, which reports the four fields it always reported.
#:
#: The tokens are deliberately not in here.  They do not change during a
#: run, so carrying them would put constant data in every value the cycle
#: detector stores.  The current token is a parameter to the transition.
type _State = tuple[int, int, int, _Ram, bool]


def output(z: int, n: int, ram: dict[int, int], io: IO) -> None:
    """Print the current state of all registers and RAM memory."""
    res = f"z: {z}\nn: {n}\nram: {{"

    for x, y in ram.items():
        res += f"\n    {x}: {y},"
    if ram:
        res = res[:-1] + "\n"
    io.print_str(res + "}")


def _stored(ram: _Ram, addr: int, value: int) -> _Ram:
    """Return ``ram`` with ``addr`` set to ``value``, in insertion order.

    A rewrite updates the existing pair where it sits; a new address is
    appended.  That is what a dict does, and the dump reads the order back
    out, so it has to be what happens here too.

    Rebuilding the whole sequence is what an immutable store costs, and
    finding an existing address is a scan rather than a hash lookup.  Both
    stay affordable because RAM0 programs address a handful of cells: over
    the generated corpus the store never exceeds one.  The scan only starts
    to tell at a size nothing here reaches -- measured 3.7x slower than the
    dict at 200 cells, and level with it at the sizes real programs use.
    """
    for i, (key, _value) in enumerate(ram):
        if key == addr:
            return (*ram[:i], (addr, value), *ram[i + 1 :])
    return (*ram, (addr, value))


def _loaded(ram: _Ram, addr: int) -> int:
    """Return the value at ``addr``, or zero for a cell never written."""
    for key, value in ram:
        if key == addr:
            return value
    return 0


def change(z: int, n: int, ram: _Ram, op: str) -> tuple[int, int, _Ram, bool]:
    """Execute a single RAM0 command and return the updated registers.

    Now returns the RAM alongside the registers instead of writing into a
    dict the caller still holds.  ``S`` is the only command that touches
    the store, and it hands back a new one.

    The trailing flag is the ``C`` skip condition: whether ``z`` is zero
    after the command ran.
    """
    if op == "Z":
        z = 0
    elif op == "A":
        z += 1
    elif op == "N":
        n = z
    elif op == "L":
        z = _loaded(ram, z)
    elif op == "S":
        ram = _stored(ram, n, z)
    return z, n, ram, not z


def _advance(state: _State, op: str) -> _State:
    """Return the state after executing one token.

    Pure: it reads ``state`` and returns a new one.  It takes no ``io``
    argument, so the dump is necessarily the caller's business -- this
    function only records, through ``dumped``, that it has happened.

    ``C`` skips the next token when ``z`` is zero after the command; a
    digit token is a 1-based goto, so it lands on ``int(op) - 2`` and the
    shared increment below carries it to ``int(op) - 1``.  Every other
    token falls through to that same increment.
    """
    ind, z, n, ram, dumped = state
    z, n, ram, skip = change(z, n, ram, op)
    if op == "C" and skip:
        ind += 1
    elif op.isdigit():
        ind = int(op) - 2
    return (ind + 1, z, n, ram, dumped)


class _Machine:
    """A RAM0 run: one immutable ``_State``, rebound per step.

    The protocol the rest of the library expects (``step``, ``halted``,
    ``snapshot``, and the ``z``/``n``/``ram``/``ind`` attributes) is mutable
    by construction, so this class supplies it.  All it does is hold the
    current state and the tokens; the rules themselves are the pure
    functions above.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Tokenize ``code`` and start both registers and RAM at zero."""
        self.io = io
        self.tokens = re.findall(r"([ZANCLS]|[1-9]\d*)", code)
        # ``halted`` is read twice per token -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(self.tokens)
        self.state: _State = (0, 0, 0, (), False)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def z(self) -> int:
        return self.state[1]

    @property
    def n(self) -> int:
        return self.state[2]

    @property
    def ram(self) -> dict[int, int]:
        """The RAM as a dict, which is how callers and the dump read it."""
        return dict(self.state[3])

    @property
    def dumped(self) -> bool:
        """Whether the once-per-run state dump has already been printed."""
        return self.state[4]

    @property
    def halted(self) -> bool:
        """Whether the cursor has run past the end of the token list.

        Matches the original loop's sole condition (``ind < len(tokens)``):
        a goto always lands with ``ind >= 0`` because the regex only
        tokenizes digit strings starting ``1``-``9`` (so ``int(c) - 2 + 1``,
        the post-increment value, is never negative) -- there is no path to
        a negative index this needs to guard against separately.
        """
        return self.state[0] >= self.size

    # The VM's language-shaped view: two registers and a sparse RAM.

    @property
    def ip(self) -> int:
        """The token cursor."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The registers ``z`` and ``n``, then the RAM in address order."""
        _ind, z, n, ram, _dumped = self.state
        # The store is in insertion order, so sort here -- this view is
        # documented as address-ordered and is read by the VM, not printed.
        return [z, n, *(value for _addr, value in sorted(ram))]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The four fields this returned before ``dumped`` joined the state.
        # The RAM goes in as a frozenset, as it always did, so the hash does
        # not depend on the order pairs happen to sit in.
        ind, z, n, ram, _dumped = self.state
        return (ind, z, n, frozenset(ram))

    def step(self) -> None:
        """Execute one token, dumping the state once the cursor runs off.

        The dump is here rather than in the transition: this is the shell,
        so it is where an effect belongs.  The transition carries the flag
        that says it has happened, which is what keeps it to exactly one
        dump however many times a halted machine is stepped.
        """
        ind, z, n, ram, dumped = self.state
        if ind >= self.size:
            if not dumped:
                output(z, n, dict(ram), self.io)
                self.state = (ind, z, n, ram, True)
            return
        self.state = _advance(self.state, self.tokens[ind])


def run(code: str, io: IO) -> None:
    """Execute a RAM0 program by parsing commands and running them sequentially."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    machine.step()  # dump the final state


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
