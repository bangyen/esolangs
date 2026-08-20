"""RAM0 interpreter implementation.

Computational model with two registers (z, n) and unbounded RAM.
Seven commands: Z, A, N, C, L, S, and goto.

The interpreter runs on a :class:`_Machine` (registers, RAM, and the token
cursor), so it is step-capable: ``step()`` executes one token and ``halted``
is true once the cursor runs off either end of the token list.  The state
dump is printed exactly once, on the step that halts the machine, matching
the original's print-after-the-loop behavior.
"""

import re
import sys

from esolangs.interpreters.io import IO


def output(z: int, n: int, ram: dict[int, int], io: IO) -> None:
    """Print the current state of all registers and RAM memory."""
    res = f"z: {z}\nn: {n}\nram: {{"

    for x, y in ram.items():
        res += f"\n    {x}: {y},"
    if ram:
        res = res[:-1] + "\n"
    io.print_line(res + "}")


def change(z: int, n: int, ram: dict[int, int], op: str) -> tuple[int, int, bool]:
    """Execute a single RAM0 command and return the updated registers."""
    if op == "Z":
        z = 0
    elif op == "A":
        z += 1
    elif op == "N":
        n = z
    elif op == "L":
        z = ram.get(z, 0)
    elif op == "S":
        ram[n] = z
    return z, n, not z


class _Machine:
    """Per-run RAM0 state: the registers, RAM, and the token cursor.

    ``step()`` executes one token; ``halted`` is true once the cursor runs
    off either end of the token list.  The state-cycle hang detector and the
    VM expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Tokenize ``code`` and start both registers and RAM at zero."""
        self.io = io
        self.tokens = re.findall(r"([ZANCLS]|[1-9]\d*)", code)
        self.z = self.n = 0
        self.ram: dict[int, int] = {}
        self.ind = 0
        self._dumped = False

    @property
    def halted(self) -> bool:
        """Whether the cursor has run past the end of the token list.

        Matches the original loop's sole condition (``ind < len(tokens)``):
        a goto always lands with ``ind >= 0`` because the regex only
        tokenizes digit strings starting ``1``-``9`` (so ``int(c) - 2 + 1``,
        the post-increment value, is never negative) -- there is no path to
        a negative index this needs to guard against separately.
        """
        return self.ind >= len(self.tokens)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.ind, self.z, self.n, frozenset(self.ram.items()))

    def step(self) -> None:
        """Execute one token, dumping the state once the cursor runs off."""
        if self.halted:
            if not self._dumped:
                output(self.z, self.n, self.ram, self.io)
                self._dumped = True
            return
        c = self.tokens[self.ind]
        self.z, self.n, skip = change(self.z, self.n, self.ram, c)
        if c == "C" and skip:
            self.ind += 1
        elif c.isdigit():
            self.ind = int(c) - 2
        self.ind += 1


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
