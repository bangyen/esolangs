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
"""

import re
import sys

from esolangs.interpreters.io import IO


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

        self.ind = self.ptr = 0
        self.reg = [0, 0]
        self._dumped = False

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the program."""
        return self.ind >= len(self.prog)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.ind, self.ptr, tuple(self.reg))

    def step(self) -> None:
        """Execute one command, dumping the registers once the cursor ends."""
        if self.halted:
            if not self._dumped:
                self.io.print_str(" ".join(map(str, self.reg)))
                self._dumped = True
            return
        if (op := self.prog[self.ind]) == "+":
            self.reg[self.ptr] += 1
        elif op == "~":
            if self.reg[self.ptr]:
                self.reg[self.ptr] -= 1
            elif target := self.targets[self.ind]:
                self.ind = target - 2
        elif op == "*":
            self.ptr ^= 1
        self.ind += 1


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
