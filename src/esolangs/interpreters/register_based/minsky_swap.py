r"""Minsky Swap interpreter implementation."""

from __future__ import annotations

import re
import sys

from esolangs.interpreters.io import IO

# : One instant of a run:.
# : register pointer, both.
# : been printed.
# : new one rather than editing.
#: for the same reason.
# :.
# : ``dumped`` is state because.
# : happens *after* the cursor.
# : cannot tell "about to dump".
# : ``snapshot``, which reports.
# :.
# : The program and its jump.
# : changes during a run, so.
# : value the cycle detector.
type _State = tuple[int, int, tuple[int, int], bool]


def _advance(state: _State, prog: str, targets: dict[int, int]) -> _State:
    r"""Return the state after executing one command."""
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
    r"""Return the compact-notation program and its jump-line numbers."""
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
        # Also process any remaining.
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
    r"""Per-run Minsky Swap state: the program, both registers, and the."""

    # : Whether the tape/registers.
    # : It belongs to the language,.
    # : ends its loop with one more.
    # : ``halted`` has driven the.
    #: its output.
    dumps_on_the_post_halt_step = True

    def __init__(self, code: str, io: IO) -> None:
        r"""Parse ``code`` and start both registers at zero."""
        self.io = io
        self.prog, nums = _parse(code)

        # Each tilde's jump target is.
        # line: the Nth tilde jumps to.
        # targets are 1-based (so a.
        self.targets: dict[int, int] = {}
        for i, ch in enumerate(self.prog):
            if ch == "~":
                if len(self.targets) >= len(nums):
                    raise ValueError("unmatched '~' with no jump target")
                self.targets[i] = nums[len(self.targets)]

        # ``halted`` is read twice per.
        # once by ``step``'s guard --.
        self.size = len(self.prog)
        self.state: _State = (0, 0, (0, 0), False)

    # The language's own names.
    # than fields of their own, so.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def ptr(self) -> int:
        return self.state[1]

    @property
    def reg(self) -> tuple[int, int]:
        r"""Both registers, in pointer order."""
        return self.state[2]

    @property
    def dumped(self) -> bool:
        r"""Whether the end-of-run register dump has already been printed."""
        return self.state[3]

    @property
    def halted(self) -> bool:
        r"""Whether the cursor has reached the end of the program."""
        return self.state[0] >= self.size

    # The VM's language-shaped.
    # both registers.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return list(self.state[2])

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # The three fields this.
        # ``dumped`` stays out: the.
        # machine, and a stopped run is.
        ind, ptr, reg, _dumped = self.state
        return (ind, ptr, reg)

    def step(self) -> None:
        r"""Execute one command, dumping the registers once the cursor ends."""
        ind, ptr, reg, dumped = self.state
        if ind >= self.size:
            if not dumped:
                self.io.print_str(" ".join(map(str, reg)))
                self.state = (ind, ptr, reg, True)
            return
        self.state = _advance(self.state, self.prog, self.targets)


def run(code: str, io: IO) -> None:
    r"""Execute a Minsky Swap program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    machine.step()  # dump the final registers.


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
