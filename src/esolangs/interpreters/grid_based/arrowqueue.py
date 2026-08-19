"""Interpreter for ArrowQueue.

ArrowQueue is a two-dimensional, queue-based tarpit inspired by Re:direction.
The Instruction Pointer (IP) walks a grid; ``*`` turns it clockwise, ``~``
pushes the current direction onto a queue, and ``+`` pops the queue and
points the IP in the popped direction.  All other characters are no-ops.
The program halts when ``+`` pops an empty queue or the IP moves off the
grid.

Decisions for gaps in the wiki spec (documented):
- the IP starts in the top-left corner moving right, matching Re:direction
  (the wiki is silent on both);
- clockwise order is right, down, left, up (screen coordinates), so turning
  is ``(dir + 1) % 4``;
- the grid is padded to a rectangle as wide as the longest line, which is
  how the wiki's examples lay out wide rows; an IP that leaves the
  rectangle has moved out of bounds and halts the program.
"""

import sys

from esolangs.interpreters.io import IO

DELTA = [(1, 0), (0, 1), (-1, 0), (0, -1)]


class _Machine:
    """Per-run ArrowQueue state: position, heading, and the direction queue.

    ``step()`` advances the IP by one grid cell and ``halted`` says whether
    it has run off the grid or popped an empty queue — the shape the VM
    wrapper and the state-cycle hang detector expect.  :meth:`snapshot`
    returns the position, heading, and queue, so a repeated snapshot proves
    a deterministic run loops forever (the queue stays bounded on the
    rings that sustain).
    """

    def __init__(self, code: list[str]) -> None:
        """Pad ``code`` to a rectangle and reset the machine to the corner."""
        self.code = code
        self._done = False
        self.x = self.y = self.d = 0
        self.queue: list[int] = []
        if code:
            self.width = max(len(line) for line in code)
            self.grid = [line.ljust(self.width) for line in code]
        else:
            self.width = 0
            self.grid = []
            self._done = True

    @property
    def halted(self) -> bool:
        """Whether the IP has left the grid or halted on an empty pop."""
        return self._done

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.x, self.y, self.d, tuple(self.queue))

    def step(self) -> None:
        """Execute one grid cell, advancing the IP."""
        if self.halted:
            return
        if not 0 <= self.x < self.width or not 0 <= self.y < len(self.grid):
            self._done = True
            return
        cell = self.grid[self.y][self.x]
        if cell == "*":
            self.d = (self.d + 1) % 4
        elif cell == "~":
            self.queue.append(self.d)
        elif cell == "+":
            if not self.queue:
                self._done = True
                return
            self.d = self.queue.pop(0)
        dx, dy = DELTA[self.d]
        self.x += dx
        self.y += dy
        if not 0 <= self.x < self.width or not 0 <= self.y < len(self.grid):
            self._done = True


def run(
    code: list[str],
    io: IO,  # noqa: ARG001 - ArrowQueue defines no I/O; the param follows the
    # repo convention so `esolangs.run` and the example harness pass it uniformly
) -> None:
    """Run an ArrowQueue program, halting on an empty-queue pop or off-grid."""
    machine = _Machine(code)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
