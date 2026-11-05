"""Boolfuck with a two-sided bit tape and little-endian byte I/O.

Commands act on the bit under the pointer: ``+`` flips it, ``,`` reads a bit
into it, ``;`` writes it, ``<`` and ``>`` move the pointer, and ``[ ]`` loop
while it is 1.  Noncommands are ignored.

Input/output:
    Bits move least-significant first, eight to a byte.  Unicode input is
    reduced modulo 256, matching the package's byte interfaces.  EOF supplies
    zero bits, so a read never raises.  A partial output byte is padded with
    zero bits at halt.

Errors:
    ProgramError: unmatched brackets.
"""

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.bit_tape import _BitTapeMachine
from esolangs.runtime.io import IO


class _Machine(_BitTapeMachine):
    """Language-owned bit-tape machine."""


def run(code: str, io: IO) -> None:
    """Execute Boolfuck and flush its final partial byte."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
