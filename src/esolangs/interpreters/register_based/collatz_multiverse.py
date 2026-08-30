"""Interpreter for Collatz Multiverse.

An OISC where every line is ``[var1] = [var2] x + [var3], [DO|NOT] PRINT.``
The Collatz rule applies to var1: if it is odd (or 0), it becomes
``var1 * var2 + var3``; if it is even, it is halved.  ``DO`` prints the
result as a byte, ``NOT`` does not.  Variables are named by letters, digits,
and underscores (not starting with a digit) and start at 0; ``arr[var]``
indexes an array (bare ``arr`` acts as ``arr[0]``); ``negativeOne`` starts
at -1; ``input`` reads an integer from stdin and cannot be a target; and
``lineNumber`` reads the current line (1-indexed), and assigning to it moves
the instruction pointer to that line without executing it immediately.

Documented decisions for gaps in the wiki spec:
- the program is its non-blank lines, numbered from 1; execution starts at
  line 1 and halts when the pointer leaves the program;
- var2/var3 and array indices must be variable names, not numeric literals
  (the wiki rejects ``var = 3 x + 1``);
- assigning to ``lineNumber`` applies the Collatz rule to the current line
  number and jumps to the result (the wiki does not exempt it);
- ``DO`` prints the low byte of the result;
- ``input`` raises :class:`EOFError` when input runs out (repo-wide
  convention);
- a malformed line, a numeric literal, or an attempt to redefine ``input``
  is malformed (:class:`ValueError`).

The interpreter runs on a :class:`_Machine` (the registers, the arrays, and
the line pointer), so it is step-capable: ``step()`` executes one line and
``halted`` is true once the pointer leaves the program.  A ``lineNumber``
jump that returns to an exact state is a cycle the state-cycle hang detector
proves; the ``run()`` backstop stays for the unbounded-growth class (a
register that keeps growing).
"""

import re
import sys

from esolangs.interpreters.io import IO

_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_LINE = re.compile(
    rf"^\s*({_NAME})(?:\[({_NAME})\])?\s*=\s*"
    rf"({_NAME})(?:\[({_NAME})\])?\s*x\s*\+\s*"
    rf"({_NAME})(?:\[({_NAME})\])?\s*,\s*(DO|NOT)\s+PRINT\.\s*$"
)


class _Machine:
    """Per-run Collatz Multiverse state: registers, arrays, and the pointer.

    ``step()`` executes one line; ``halted`` is true once the pointer leaves
    the program.  The VM and the state-cycle hang detector expose this
    object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` into lines and start at line 1."""
        self.io = io
        lines = [ln for ln in code.splitlines() if ln.strip()]
        self.n = len(lines)
        self.parsed = []
        for ln in lines:
            m = _LINE.fullmatch(ln)
            if not m:
                raise ValueError(f"malformed line: {ln!r}")
            self.parsed.append(m.groups())
        self.registers: dict[str, int] = {"negativeOne": -1}
        self.arrays: dict[str, dict[int, int]] = {}
        self.ip = 1

    @property
    def halted(self) -> bool:
        """Whether the pointer has left the program."""
        return not (1 <= self.ip <= self.n)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            frozenset(self.registers.items()),
            frozenset(
                (name, frozenset(cells.items())) for name, cells in self.arrays.items()
            ),
            self.ip,
            self.io.position(),
        )

    def _read(self, spec: tuple[str, str | None]) -> int:
        name, index = spec
        if name == "input":
            return self.io.input_num()
        if name == "lineNumber":
            return self.ip
        if index is not None:
            return self.arrays.setdefault(name, {}).get(self._read((index, None)), 0)
        return self.registers.get(name, 0)

    def step(self) -> None:
        """Execute one line, moving the pointer."""
        if self.halted:
            return
        var1, idx1, var2, idx2, var3, idx3, do_print = self.parsed[self.ip - 1]
        if var1 == "input":
            raise ValueError("input cannot be redefined")

        t = self._read((var1, idx1))
        a = self._read((var2, idx2))
        b = self._read((var3, idx3))
        t = t * a + b if t == 0 or t % 2 != 0 else t // 2

        next_ip = self.ip + 1
        if var1 == "lineNumber":
            next_ip = t
        elif idx1 is not None:
            # The array already exists: every line reads its target before
            # writing it, and an indexed read creates the array (``_read``
            # defaults it).  So this write needs no default of its own --
            # one here would be a branch nothing can reach.
            self.arrays[var1][self._read((idx1, None))] = t
        else:
            self.registers[var1] = t

        if do_print == "DO":
            self.io.print_char(chr(t & 0xFF))
        self.ip = next_ip


def run(code: str, io: IO) -> None:
    """Run a Collatz Multiverse program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
