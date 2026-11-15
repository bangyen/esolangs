"""BracketOnly's built-in function IDs."""

from enum import IntEnum


class Function(IntEnum):
    ONE = 0
    ADD = 1
    MUL = 2
    SUB = 3
    DIV = 4
    MOD = 5
    INP = 6
    INPC = 7
    OUT = 8
    OUTC = 9
    RND = 10
    IF = 11
    WHILE = 12
    READ = 13
    WRITE = 14
    AND = 15
    OR = 16
    XOR = 17
    NOT = 18
    LT = 19
    GT = 20
    EQ = 21
    NE = 22
    LE = 23
    GE = 24
