"""Minsky Swap interpreter implementation.

Turing-complete language based on Minsky machines.
Uses two unbounded registers with a register pointer that can be swapped.

Jump targets are 1-based and fixed by the tilde's position in the code line:
the Nth ``~`` jumps to the Nth number on the jump line, so ``decnz(N)`` (and
its compact ``~``) restarts execution at line N.  The wiki describes targets
as 1-based ("line N"), which this interpreter follows.

A ``~`` with no corresponding jump number is a malformed program and is
rejected with :class:`ValueError`.

The wiki defines no I/O for this language, so the interpreter prints both
registers when the program ends -- space-separated on one line, with no
trailing newline.  This is the convention the other interpreter-only
languages here follow (Back's tape, Bitdeque's deque, A Painter Ant's grid
raster); the choice to print at all, and the separator, are the repo's, not
the spec's.  A language whose spec *does* pin an output format follows that
instead: LaserFuck's says its decimal mode prints "with line breaks", so it
separates with newlines rather than spaces.

The interpreter runs on a :class:`_Machine` (the parsed program, both
registers, and the instruction cursor), so it is step-capable: ``step()``
executes one command and ``halted`` is true once the cursor reaches the end
of the program.  The register dump is printed exactly once, on the step
that halts the machine, matching the original's print-after-the-loop
behavior.

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and the jump table to the next state, and
never mutates what it is given.  It takes no ``io`` argument at all, so it
is total and side-effect free by construction rather than by inspection.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what Minsky Swap *does* stays
in the pure layer.  The register dump is the language's only effect and is
done by ``step``.
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

    Pure: it reads ``state`` and returns a new one.  It takes no ``io``
    argument, so the dump is necessarily the caller's business -- this
    function only records, through ``dumped``, that it has happened.

    ``~`` is decrement-or-jump: it decrements the current register when it
    is nonzero, and otherwise jumps to its 1-based target, landing on
    ``target - 2`` so the shared increment carries it to ``target - 1``.

    The parse strips everything but ``+~*``, so the final branch is ``*``,
    which swaps which register the pointer addresses.
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
    """Per-run Minsky Swap state: the program, both registers, and the cursor.

    ``step()`` executes one command; ``halted`` is true once the cursor
    reaches the end of the program.  The state-cycle hang detector and the
    VM expose this object.
    """

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

        The dump is here rather than in the transition: this is the shell,
        so it is where an effect belongs.  The transition carries the flag
        that says it has happened, which keeps it to exactly one dump
        however many times a halted machine is stepped.
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
