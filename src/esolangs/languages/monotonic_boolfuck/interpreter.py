"""Monotonic Boolfuck: a Boolfuck whose bits can be set but never cleared.

Commands act on the bit under the pointer of a two-sided, initially zero bit
tape: ``1`` sets it, ``,`` reads a bit into it when it is 0 (and consumes a
bit with no effect when it is 1), ``;`` writes it, ``<`` and ``>`` move the
pointer, ``[`` skips past its ``]`` when the bit is 0, and ``]`` jumps back to
its ``[``, which tests again.  Other characters are ignored.

Input/output:
    Bits move least-significant first, eight to a byte.  Unicode input is
    reduced modulo 256, matching the package's byte interfaces.  EOF supplies
    zero bits, so a read never raises.  A partial output byte is padded with
    zero bits at halt.

Errors:
    ProgramError: unmatched brackets.

Decisions:
    * Bit order is least-significant first: the page's truth machine prints
      ``x`` then ``0 0 0 1 1 0 0``, which is ``'0'``/``'1'`` only in that order.
    * The tape is unbounded in both directions: the page's Hello world moves
      left of the start.
    * ``]`` is unconditional, as written; the ``[`` it returns to decides.
    * ``,`` on a 1 bit consumes a bit even at EOF (a zero), and a read of 0
      leaves the bit 0: the tape's set of ones only grows.
    * The page's Hello world does not print "Hello, world!" under these or any
      other reading tried (its lines carry nine outputs; the truth machine
      fixes the semantics) and has no unique repair; it runs as written and
      its output is pinned in the tests.
"""

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.bit_tape import _BitTapeMachine
from esolangs.runtime.io import IO


class _Machine(_BitTapeMachine):
    """Language-owned bit-tape machine."""

    set_command = "1"

    def _set_bit(self, ptr: int) -> None:
        self.ones.add(ptr)

    def _read_bit(self, ptr: int, bit: int, _before: int) -> None:
        if bit and not _before:
            self.ones.add(ptr)


def run(code: str, io: IO) -> None:
    """Execute Monotonic Boolfuck and flush its final partial byte."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
