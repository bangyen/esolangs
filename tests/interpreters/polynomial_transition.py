"""Polynomial C-integer operations and nested control-flow interpretation."""

from fractions import Fraction


def matching(program, index):
    opening = program[index][0] not in (2, 6)
    step = 1 if opening else -1
    depth = 0
    for other in range(index + step, len(program) if opening else -1, step):
        instruction = program[other]
        if len(instruction) != 1:
            continue
        same = (instruction[0] not in (2, 6)) == opening
        if same:
            depth += 1
        elif depth:
            depth -= 1
        else:
            return other
    raise ValueError("unmatched control-flow bracket")


def condition(code, register):
    if code in (1, 5):
        return register > 0
    if code in (3, 7):
        return register < 0
    if code in (4, 8):
        return register == 0
    raise ValueError("invalid condition")


def transition(state, program, byte=None):
    register, cursor = state
    instruction = program[cursor]
    output = None
    if len(instruction) == 2:
        operand, operation = instruction
        if operand == 0:
            if operation == 1:
                output = chr(register) if register >= 0 else None
            else:
                register = -1 if byte is None else byte
        elif operation == 1:
            register += operand
        elif operation == 2:
            register -= operand
        elif operation == 3:
            register *= operand
        elif operation == 4:
            register = int(Fraction(register, operand))
        elif operation == 5:
            register -= operand * int(Fraction(register, operand))
        elif operation == 6:
            register = int(Fraction(register) ** operand)
        else:
            raise ValueError("invalid operator")
    else:
        code = instruction[0]
        if code in (2, 6):
            begin = matching(program, cursor)
            if program[begin][0] in (5, 7, 8) and condition(
                program[begin][0], register
            ):
                cursor = begin
        elif not condition(code, register):
            cursor = matching(program, cursor)
    return (register, cursor + 1), output
