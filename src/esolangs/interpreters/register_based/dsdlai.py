"""
DSDLAI (Dig straight down like an idiot) interpreter implementation.

DSDLAI is a variant of Dig where there is a 20% to 90% chance for the program
to return an error when using the dig command, analogous to falling into lava
when digging straight down in Minecraft.

Based on the specification at https://esolangs.org/wiki/Dig_straight_down_like_an_idiot
"""

import secrets as s
import sys
from typing import Callable

from . import dig


def rand() -> Callable[[], bool]:
    """
    Create a probabilistic death function for DSDLAI.

    This function simulates the risk of "falling into lava" when digging straight
    down in Minecraft. It returns a function that has a random chance (20-90%)
    of causing the program to terminate with a death message.

    Returns:
        A function that returns True if the mole "dies" (causing program termination),
        False if the mole survives the dig operation.
    """
    num = s.randbelow(71) + 20

    def chance() -> bool:
        """
        Determine if the mole dies during a dig operation.

        Uses a random percentage to simulate the risk of falling into lava.
        The death chance is randomly set between 20% and 90% when rand() is called.

        Returns:
            True if the mole dies (should terminate program), False if it survives.
        """
        n = s.randbelow(100) + 1
        if n <= num:
            print("\nYou died.")
        return n <= num

    return chance


def run(code: list[str]) -> None:
    """
    Execute a DSDLAI program with probabilistic death risk.

    This function runs a Dig program with the added risk that the mole may
    "fall into lava" and die when using the dig command ($). The death chance
    is randomly determined between 20% and 90% for each program execution.

    Args:
        code: List of strings representing the 2D program grid

    The program uses the same commands as Dig, but with added risk:
    - $ (dig) command may cause death with 20-90% probability
    - All other Dig commands work normally
    """
    dig.run(code, rand())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
