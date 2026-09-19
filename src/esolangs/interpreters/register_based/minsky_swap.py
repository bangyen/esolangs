"""Interpreter for Minsky Swap.

Two unbounded registers and a swappable register pointer.  The Nth ``~``
jumps to the Nth number on the jump line, 1-based ("line N", per the
wiki); a ``~`` with no jump number raises :class:`ValueError`.  The wiki
defines no I/O, so both registers are printed once at the end,
space-separated with no trailing newline -- the repo's convention for
interpreter-only languages (Back, Bitdeque, A Painter Ant), not the
spec's; LaserFuck's spec pins newlines instead.

:func:`_advance` is a pure transition over an immutable ``_State`` with no
``io`` argument; :class:`_Machine` is the mutable shell that rebinds one
state per ``step()`` and does the one dump on the halting step.
"""

from __future__ import annotations

import re
import sys

from esolangs.interpreters.io import IO

#: One instant of a run: ``(ind, ptr, reg, dumped)`` -- the cursor, the
#: register pointer, both registers, and whether the end-of-run dump has
#: been printed.  A value, not a record: every transition below returns a
#: new one rather than editing one in place, and the registers are a tuple
#: for the same reason.
#:
#: ``dumped`` is state because the dump is a once-per-run effect that
#: happens *after* the cursor has run off the end, so the position alone
#: cannot tell "about to dump" from "already dumped".  It stays out of
#: ``snapshot``, which reports the three fields it always reported.
#:
#: The program and its jump table are deliberately not in here.  Neither
#: changes during a run, so carrying them would put constant data in every
#: value the cycle detector stores.
type _State = tuple[int, int, tuple[int, int], bool]


def _advance(state: _State, prog: str, targets: dict[int, int]) -> _State:
    """Return the state after executing one command.

    ``~`` decrements a nonzero register, else jumps to ``target - 2`` so the
    shared increment lands on ``target - 1``; ``*`` swaps the pointer.  The
    dump is the caller's; ``dumped`` records that it happened.
    """
    ind, ptr, reg, dumped = state
    op = prog[ind]
    if op == "+":
        reg = (reg[0] + 1, reg[1]) if ptr == 0 else (reg[0], reg[1] + 1)
    elif op == "~":
        if reg[ptr]:
            reg = (reg[0] - 1, reg[1]) if ptr == 0 else (reg[0], reg[1] - 1)
        elif target := targets[ind]:
            ind = target - 2
    else:
        ptr ^= 1
    return (ind + 1, ptr, reg, dumped)


def _parse(code: str) -> tuple[str, list[int]]:
    """Return the compact-notation program and its jump-line numbers."""
    prog = ""
    nums: list[int] = []

    if re.search(r"(inc|swap|decnz)\(", code):
        pattern = r"(inc|swap|decnz)\((\d*)\);"
        cmp = re.compile(pattern)
        for m in cmp.findall(code):
            if (s := m[0][0]) == "i":
                prog += "+"
            elif s == "s":
                prog += "*"
            else:
                prog += "~"
                skip = int(m[1]) if m[1] else 1
                nums.append(skip)
        # Also process any remaining compact notation
        compact_part = re.sub(r"(inc|swap|decnz)\([^)]*\);", "", code)
        compact_part = re.sub("[^+~*]", "", compact_part)
        prog += compact_part
    else:
        prog = (s := code.split("\n"))[0]
        prog = re.sub("[^+~*]", "", prog)
        if len(s) > 1:
            nums = re.findall(r"\d+", s[1])
            nums = [int(k) for k in nums]

    return prog, nums


class _Machine:
    """Per-run Minsky Swap state: the program, both registers, and the cursor."""

    #: Whether the tape/registers are written on the step *after* the halt.
    #: It belongs to the language, not to whoever is stepping it: ``run``
    #: ends its loop with one more ``step()``, so a caller who stops at
    #: ``halted`` has driven the program correctly and still holds none of
    #: its output.
    dumps_on_the_post_halt_step = True

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` and start both registers at zero."""
        self.io = io
        self.prog, nums = _parse(code)

        # Each tilde's jump target is fixed by its position in the code
        # line: the Nth tilde jumps to the Nth number on the jump line, and
        # targets are 1-based (so a jump to N runs the (N-1)th command).
        self.targets: dict[int, int] = {}
        for i, ch in enumerate(self.prog):
            if ch == "~":
                if len(self.targets) >= len(nums):
                    raise ValueError("unmatched '~' with no jump target")
                self.targets[i] = nums[len(self.targets)]

        # ``halted`` is read twice per command -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(self.prog)
        self.state: _State = (0, 0, (0, 0), False)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def ptr(self) -> int:
        return self.state[1]

    @property
    def reg(self) -> tuple[int, int]:
        """Both registers, in pointer order."""
        return self.state[2]

    @property
    def dumped(self) -> bool:
        """Whether the end-of-run register dump has already been printed."""
        return self.state[3]

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the program."""
        return self.state[0] >= self.size

    # The VM's language-shaped view: Two registers + pointer; ip the cursor, memory
    # both registers.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.state[2])

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The three fields this returned before ``dumped`` joined the state.
        # ``dumped`` stays out: the detector compares states of a running
        # machine, and a stopped run is not something it is asked about.
        ind, ptr, reg, _dumped = self.state
        return (ind, ptr, reg)

    def step(self) -> None:
        """Execute one command, dumping the registers once the cursor ends.

        The transition's ``dumped`` flag keeps it to one dump however often a
        halted machine is stepped.
        """
        ind, ptr, reg, dumped = self.state
        if ind >= self.size:
            if not dumped:
                self.io.print_str(" ".join(map(str, reg)))
                self.state = (ind, ptr, reg, True)
            return
        self.state = _advance(self.state, self.prog, self.targets)


def run(code: str, io: IO) -> None:
    """Execute a Minsky Swap program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    machine.step()  # dump the final registers


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
