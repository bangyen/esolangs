"""
DSDLAI interpreter implementation.

Dig variant with probabilistic death risk when using dig commands.
Random chance (20-90%) that mole dies during dig operations.
"""

import secrets as s
import sys
from collections.abc import Callable

from esolangs.interpreters.io import IO

from . import dig


def rand(io: IO | None = None) -> Callable[[], bool]:
    """Create a probabilistic death function for DSDLAI."""
    io = io or IO()
    num = s.randbelow(71) + 20

    def chance() -> bool:
        """Determine if the mole dies during a dig operation."""
        n = s.randbelow(100) + 1
        if n <= num:
            io.print_line("\nYou died.")
        return n <= num

    return chance


def run(code: list[str], io: IO) -> None:
    """Execute a DSDLAI program with probabilistic death risk."""
    dig.run(code, io=io, func=rand(io))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
