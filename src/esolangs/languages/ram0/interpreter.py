"""Interpreter for RAM0.

Two registers (z, n) and unbounded RAM; seven commands: Z, A, N, C, L,
S, and goto.  The run halts when the cursor runs off the token list, and
then dumps the RAM once, in the order its addresses were first written.
A goto past the last command halts, as running off the end does.

Errors:
    HaltError: Goto ``0`` (or ``00``) when it runs.

Decisions:
    * Gotos are 1-based ("counting the first command as 1"), so ``0`` names
      no command.  It is not a comment: the wiki keeps digits out of the
      comment alphabet ("characters other than ``ZANCLS`` and digits").
"""

from __future__ import annotations

import re
from typing import NamedTuple

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.persistent import (
    Chunked,
    append,
    flatten,
    get,
    length,
    put,
)

#: The RAM as ``(address, value)`` pairs in insertion order.  The order is
#: observable (the dump prints it), so sorting would change output;
#: ``snapshot`` converts to a ``frozenset`` so it does not affect cycles.
type _Ram = Chunked[tuple[int, int]]

#: Where each address sits in the store: the machine's memo of a fact about
#: its own run.  A pair, once appended, never moves -- a rewrite updates it
#: in place -- so the position recorded at the first ``S`` to an address
#: stays right for every later state of the same run.
type _Index = dict[int, int]


class _State(NamedTuple):
    """An immutable value, rebound per step.

    ``dumped`` is state because the dump happens after the cursor runs off
    the end; it stays out of ``snapshot``.  Tokens are a parameter, not a field.
    """

    ind: int
    z: int
    n: int
    ram: _Ram
    dumped: bool


def _stored(ram: _Ram, addr: int, value: int, index: _Index) -> _Ram:
    """Return ``ram`` with ``addr`` set to ``value``, in insertion order.

    A chunked tape (:mod:`esolangs.runtime.persistent`) with an
    address-to-position memo: Theta(T) writes of O(T) each (268 cells at
    eight inputs) made execution grow faster than the command count.
    """
    position = index.get(addr)
    if position is not None:
        return put(ram, position, (addr, value))
    return append(ram, (addr, value))


def _loaded(ram: _Ram, addr: int, index: _Index) -> int:
    """Return the value at ``addr``, or zero for a cell never written."""
    position = index.get(addr)
    return get(ram, position)[1] if position is not None else 0


def change(z: int, n: int, ram: _Ram, op: str, index: _Index) -> tuple[int, int, _Ram]:
    """Execute a single RAM0 command and return the updated ``(z, n, ram)``."""
    if op == "Z":
        z = 0
    elif op == "A":
        z += 1
    elif op == "N":
        n = z
    elif op == "L":
        z = _loaded(ram, z, index)
    elif op == "S":
        ram = _stored(ram, n, z, index)
    return z, n, ram


# :func:`_advance` is pure over an immutable ``_State`` whose RAM is a tuple of
# ``(address, value)`` pairs in insertion order.  ``halted`` once the cursor runs off
# the token list, and the dump prints exactly once on that step -- the ``dumped`` flag
# is in the state because it records an effect.
def _advance(state: _State, op: str, index: _Index) -> _State:
    """Return the state after executing one token.

    ``C`` skips the next token when ``z`` is zero; a digit is a 1-based goto.
    """
    ind = state.ind
    if op.isdigit():
        if not int(op):
            raise HaltError(
                f"goto {op} at command {ind + 1}: commands count from 1",
                hint="jump to a command number of 1 or more",
            )
        return state._replace(ind=int(op) - 1)
    z, n, ram = change(state.z, state.n, state.ram, op, index)
    if op == "C" and not z:
        ind += 1
    return state._replace(ind=ind + 1, z=z, n=n, ram=ram)


class _Machine:
    """A RAM0 run: one immutable ``_State``, rebound per step."""

    #: Whether the tape/registers are written on the step *after* the halt.
    #: It belongs to the language, not to whoever is stepping it: ``run``
    #: ends its loop with one more ``step()``, so a caller who stops at
    #: ``halted`` has driven the program correctly and still holds none of
    #: its output.
    dumps_on_the_post_halt_step = True

    def __init__(self, code: str, io: IO) -> None:
        """Tokenize ``code`` and start both registers and RAM at zero."""
        self.io = io
        self.tokens = re.findall(r"[ZANCLS]|\d+", code)
        # ``halted`` is read twice per token -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(self.tokens)
        self.state = _State(0, 0, 0, (), dumped=False)
        self._index: _Index = {}

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ind(self) -> int:
        return self.state.ind

    @property
    def z(self) -> int:
        return self.state.z

    @property
    def n(self) -> int:
        return self.state.n

    @property
    def ram(self) -> dict[int, int]:
        """The RAM as a dict, which is how callers and the dump read it."""
        return dict(flatten(self.state.ram))

    @property
    def dumped(self) -> bool:
        """Whether the once-per-run state dump has already been printed."""
        return self.state.dumped

    @property
    def halted(self) -> bool:
        """Whether the cursor has run past the end of the token list.

        A goto never lands negative: :func:`_advance` rejects goto ``0``.
        """
        return self.state.ind >= self.size

    # The VM's language-shaped view: two registers and a sparse RAM.

    @property
    def ip(self) -> int:
        """The token cursor."""
        return self.state.ind

    @property
    def memory(self) -> list[int]:
        """The registers ``z`` and ``n``, then the RAM in address order."""
        _ind, z, n, ram, _dumped = self.state
        # The store is in insertion order, so sort here -- this view is
        # documented as address-ordered and is read by the VM, not printed.
        return [z, n, *(value for _addr, value in sorted(flatten(ram)))]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The four fields this returned before ``dumped`` joined the state.
        # The RAM goes in as it stands, insertion order included: that order
        # is observable (the dump prints it), so two stores differing only
        # in it are different states, and the value is already hashable.
        # It used to be re-packed into a frozenset here, O(cells) per step.
        ind, z, n, ram, _dumped = self.state
        return (ind, z, n, ram)

    def _dump(self, z: int, n: int, ram: _Ram) -> None:
        """Print the final registers and RAM in their insertion order."""
        rendered = f"z: {z}\nn: {n}\nram: {{"
        for addr, value in flatten(ram):
            rendered += f"\n    {addr}: {value},"
        if ram:
            rendered = rendered[:-1] + "\n"
        self.io.print_str(rendered + "}")

    def step(self) -> None:
        """Execute one token, dumping the state once the cursor runs off.

        The transition's flag keeps it to one dump.
        """
        ind, z, n, ram, dumped = self.state
        if ind >= self.size:
            if not dumped:
                self._dump(z, n, ram)
                self.state = self.state._replace(dumped=True)
            return
        op = self.tokens[ind]
        self.state = _advance(self.state, op, self._index)
        if op == "S" and n not in self._index:
            # A first store to ``n`` was appended at the old length.
            self._index[n] = length(ram)


def run(code: str, io: IO) -> None:
    """Execute a RAM0 program by parsing commands and running them sequentially."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
