"""
DSDLAI interpreter implementation.

Dig variant with probabilistic death risk when using dig commands.
"""

import secrets as s
import sys
from typing import Callable

from . import dig


def rand() -> Callable[[], bool]:
    """Create a probabilistic death function for DSDLAI."""
    num = s.randbelow(71) + 20

    def chance() -> bool:
        """Determine if the mole dies during a dig operation."""
        n = s.randbelow(100) + 1
        if n <= num:
            print("\nYou died.")
        return n <= num

    return chance


def run(code: list[str]) -> None:
    """Execute a DSDLAI program with probabilistic death risk."""
    dig.run(code, rand())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
