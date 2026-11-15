"""The 16 row-major bit patterns of a Bifunge command."""

from enum import IntEnum


class Command(IntEnum):
    NOP = 0b0000
    AND = 0b0001
    OR = 0b0010
    DOWN = 0b0011
    XOR = 0b0100
    RIGHT = 0b0101
    HORIZONTAL = 0b0110
    INPUT = 0b0111
    NOT = 0b1000
    VERTICAL = 0b1001
    LEFT = 0b1010
    OUTPUT = 0b1011
    UP = 0b1100
    HALT = 0b1101
    ZERO = 0b1110
    ONE = 0b1111
