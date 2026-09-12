r"""RAM0 interpreter implementation."""

from __future__ import annotations

import re
import sys

from esolangs.interpreters.io import IO

# : The RAM as an immutable.
# : *insertion* order -- first.
# :.
# : That order is observable:.
# : the dict yielded them, so a.
# : 1 prints them in that order.
# : and would silently change.
# :.
# : Ordering does not leak into.
# : ``frozenset``, so two.
#: order they were written in.
type _Ram = tuple[tuple[int, int], ...]

# : One instant of a run:.
# : the two registers, the RAM,.
# : A value, not a record:.
#: than editing one in place.
# :.
# : ``dumped`` is state because.
# : happens *after* the cursor.
# : distinguish "about to dump".
# : ``snapshot``, which reports.
# :.
# : The tokens are deliberately.
# : run, so carrying them would.
# : detector stores.
type _State = tuple[int, int, int, _Ram, bool]


def _stored(ram: _Ram, addr: int, value: int) -> _Ram:
    r"""Return ``ram`` with ``addr`` set to ``value``, in insertion order."""
    for i, (key, _value) in enumerate(ram):
        if key == addr:
            return (*ram[:i], (addr, value), *ram[i + 1 :])
    return (*ram, (addr, value))


def _loaded(ram: _Ram, addr: int) -> int:
    r"""Return the value at ``addr``, or zero for a cell never written."""
    for key, value in ram:
        if key == addr:
            return value
    return 0


def change(z: int, n: int, ram: _Ram, op: str) -> tuple[int, int, _Ram, bool]:
    r"""Execute a single RAM0 command and return the updated registers."""
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
    r"""Return the state after executing one token."""
    ind, z, n, ram, dumped = state
    z, n, ram, skip = change(z, n, ram, op)
    if op == "C" and skip:
        ind += 1
    elif op.isdigit():
        ind = int(op) - 2
    return (ind + 1, z, n, ram, dumped)


class _Machine:
    r"""A RAM0 run: one immutable ``_State``, rebound per step."""

    # : Whether the tape/registers.
    # : It belongs to the language,.
    # : ends its loop with one more.
    # : ``halted`` has driven the.
    #: its output.
    dumps_on_the_post_halt_step = True

    def __init__(self, code: str, io: IO) -> None:
        r"""Tokenize ``code`` and start both registers and RAM at zero."""
        self.io = io
        self.tokens = re.findall(r"([ZANCLS]|[1-9]\d*)", code)
        # ``halted`` is read twice per.
        # once by ``step``'s guard --.
        self.size = len(self.tokens)
        self.state: _State = (0, 0, 0, (), False)

    # The language's own names.
    # than fields of their own, so.

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
        r"""The RAM as a dict, which is how callers and the dump read it."""
        return dict(self.state[3])

    @property
    def dumped(self) -> bool:
        r"""Whether the once-per-run state dump has already been printed."""
        return self.state[4]

    @property
    def halted(self) -> bool:
        r"""Whether the cursor has run past the end of the token list."""
        return self.state[0] >= self.size

    # The VM's language-shaped.

    @property
    def ip(self) -> int:
        r"""The token cursor."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        r"""The registers ``z`` and ``n``, then the RAM in address order."""
        _ind, z, n, ram, _dumped = self.state
        # The store is in insertion.
        # documented as address-ordered.
        return [z, n, *(value for _addr, value in sorted(ram))]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # The four fields this returned.
        # The RAM goes in as a.
        # not depend on the order pairs.
        ind, z, n, ram, _dumped = self.state
        return (ind, z, n, frozenset(ram))

    def _dump(self, z: int, n: int, ram: _Ram) -> None:
        r"""Print the final registers and RAM in their insertion order."""
        rendered = f"z: {z}\nn: {n}\nram: {{"
        for addr, value in ram:
            rendered += f"\n    {addr}: {value},"
        if ram:
            rendered = rendered[:-1] + "\n"
        self.io.print_str(rendered + "}")

    def step(self) -> None:
        r"""Execute one token, dumping the state once the cursor runs off."""
        ind, z, n, ram, dumped = self.state
        if ind >= self.size:
            if not dumped:
                self._dump(z, n, ram)
                self.state = (ind, z, n, ram, True)
            return
        self.state = _advance(self.state, self.tokens[ind])


def run(code: str, io: IO) -> None:
    r"""Execute a RAM0 program by parsing commands and running them."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    machine.step()  # dump the final state.


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
