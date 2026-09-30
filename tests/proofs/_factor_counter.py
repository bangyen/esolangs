"""Factor witness using a traveling binary counter beside packed truth pairs."""

from esolangs.tools.helpers import _validate_truth_table


class _Code:
    def __init__(self, stride: int = 1, position: int = 0) -> None:
        self.parts: list[str] = []
        self.position = position
        self.stride = stride

    def at(self, cell: int, commands: str = "") -> None:
        delta = self.stride * (cell - self.position)
        self.parts.append((">" if delta >= 0 else "<") * abs(delta) + commands)
        self.position = cell

    def transfer(self, source: int, target: int, command: str = "+") -> None:
        self.at(source, "[-")
        self.at(target, command)
        self.at(source, "]")

    def render(self) -> str:
        return "".join(self.parts)


def _counter(width: int) -> str:
    if not width:
        return ""
    code = _Code(stride=2)
    guard, carry, next_carry, zero = range(width, width + 4)
    # Inputs arrive most significant first; the distance counts zero bits.
    for bit in reversed(range(width)):
        code.at(carry, "+")
        code.at(bit, "," + "-" * 48)
        code.transfer(bit, carry, "-")
        code.transfer(carry, bit)

    def guard_from_bits() -> None:
        code.at(guard, "[-]")
        for bit in range(width):
            code.at(bit, "[-")
            code.at(carry, "+")
            code.at(guard, "[-]+")
            code.at(bit, "]")
            code.transfer(carry, bit)
        code.at(guard)

    guard_from_bits()
    code.at(guard, "[-")
    code.at(carry, "+")
    for bit in range(width):
        code.at(carry, "[-")
        code.at(zero, "+")
        code.at(bit, "[-")
        code.at(zero, "-")
        code.at(bit, "]")
        code.at(zero, "[-")
        code.at(bit, "+")
        code.at(next_carry, "+")
        code.at(zero, "]")
        code.at(carry, "]")
        code.transfer(next_carry, carry)
    guard_from_bits()
    # Ascending transfers leave every destination empty before the next shift.
    for cell in range(width + 1):
        code.transfer(cell, cell - 1)
    code.at(guard - 1, "]")
    # The closing bracket is now at the shifted guard, relative to the new base.
    code.position = guard
    code.at(0)
    return code.render()


def _decoder(phase: int) -> str:
    code = _Code()
    code.at(0, "+" * (4 - phase))

    def divide(source: int, remainder: int, quotient: int, flag: int) -> None:
        for cell in (remainder, quotient, flag):
            code.at(cell, "[-]")
        code.at(source, "[-")
        code.at(flag, "+")
        code.at(remainder, "[-")
        code.at(quotient, "+")
        code.at(flag, "-")
        code.at(remainder, "]")
        code.at(flag, "[-")
        code.at(remainder, "+")
        code.at(flag, "]")
        code.at(source, "]")

    divide(0, 1, 2, 3)
    divide(2, 3, 4, 5)
    code.at(6, "[-]+")
    code.at(0, "," + "-" * 48 + "[-")
    code.at(6, "-")
    code.at(1, "+" * 48 + ".")
    code.at(0, "]")
    code.at(6, "[-")
    code.at(3, "+" * 48 + ".")
    code.at(6, "]")
    return code.render()


def counter_program(truth_table: str) -> str:
    """Use a global cyclic phase to pack pairs, then walk by a binary counter."""
    n = _validate_truth_table(truth_table)
    values = [int(truth_table[i : i + 2], 2) for i in range(0, len(truth_table), 2)]

    def signed(value: int, phase: int) -> int:
        rotated = (value + phase) % 4
        return -1 if rotated == 3 else rotated

    phase = min(range(4), key=lambda p: sum(abs(signed(v, p)) for v in values))
    data = (
        ">"
        + ">>".join(
            ("+" if signed(v, phase) >= 0 else "-") * abs(signed(v, phase))
            for v in values
        )
        + "<"
    )
    return data + _counter(n - 1) + ">" + _decoder(phase)
