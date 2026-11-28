"""Arithmetic and low pointer routes for the three packed spill axes."""

from __future__ import annotations

from collections.abc import Callable

from .isa import _char_for

type _Jump = Callable[[int, int], None]
type _Return = Callable[[int, int, _Jump], None]


class _SpillCode:
    """Emit forward walks and jumps through known return operands."""

    def __init__(self, pointer: int, return_to: _Return | None = None) -> None:
        self.pointer = pointer
        self.return_to = return_to
        self.ops: list[str] = []

    def apply(self, op: str, target: int) -> None:
        if self.return_to is not None:
            self.return_to(self.pointer, target, self.jump)
        self.walk(target)
        self.ops.append(op)
        self.pointer += 1

    def walk(self, target: int) -> None:
        assert target >= self.pointer
        self.ops.append("o" * (target - self.pointer))
        self.pointer = target

    def jump(self, operand: int, landing: int) -> None:
        self.walk(operand)
        self.ops.append("j")
        self.pointer = landing

    def mix(self, operand: int, target: int) -> None:
        self.apply("*", operand)
        self.apply("p", target)

    def short(self, operand: int) -> None:
        self.jump(operand, 45925)
        self.jump(45926, 45)

    def long(self, operand: int) -> None:
        self.jump(operand, 54673)
        self.jump(54674, 39)

    def reset(self) -> None:
        self.jump(39, 72)
        self.jump(72, 125)

    def return_to_all_twos(self) -> None:
        """Return through the low operands to D112, the all-twos operand."""
        self.jump(106, 45)
        self.jump(45, 112)

    def return_to_readout(self) -> None:
        """Return through the low operands to D157, the readout register."""
        self.jump(52, 127)
        self.jump(134, 157)

    def return_to_rotation_seed(self) -> None:
        """Return through the low operands to D126, the rotation seed."""
        self.jump(65, 47)
        self.jump(48, 126)

    def rotate_selector(self, count: int) -> None:
        for _ in range(count):
            self.jump(93, 113)
            self.jump(113, 88)
            self.apply("*", 88)

    def dispatch(self) -> None:
        self.apply("*", 167)
        self.mix(128, 167)
        self.apply("i", 167)

    def write(self, source: bytearray, start: int, end: int) -> None:
        body = "".join(self.ops)
        assert start + len(body) == end
        for address, op in enumerate(body, start):
            source[address] = _char_for(op, address)


def _lower_return(pointer: int, target: int, jump: _Jump) -> None:
    if pointer <= target:
        return
    if pointer >= 202:
        jump(208, 124)
    elif pointer >= 199:
        jump(200, 45)
        jump(48, 126)
    elif pointer == 168:
        jump(168, 48)
        jump(48, 126)
    elif pointer >= 148:
        jump(151, 43)
        jump(48, 126)
    else:
        assert pointer == 144
        jump(144, 69)
        jump(72, 125)


def _mid_return(pointer: int, target: int, jump: _Jump) -> None:
    if pointer == 49:
        jump(52, 127)
    elif pointer <= target:
        return
    elif pointer >= 199:
        if target == 48:
            jump(200, 45)
        else:
            jump(208, 124)
    elif pointer == 168:
        jump(168, 48)
        jump(52, 127)
    elif pointer >= 150:
        jump(151, 43)
        jump(52, 127)
    elif target == 48:
        jump(131, 106)
        jump(106, 45)
    else:
        assert target == 126
        jump(135, 36)
        jump(39, 72)
        jump(72, 125)


def _upper_return(pointer: int, target: int, jump: _Jump) -> None:
    if pointer <= target:
        return
    if pointer >= 199:
        jump(200, 45)
        jump(48, 126)
    elif pointer == 168:
        jump(168, 48)
        jump(48, 126)
    elif pointer >= 148:
        jump(151, 43)
        jump(48, 126)
    elif pointer >= 137:
        jump(142, 126)
    else:
        jump(131, 106)
        jump(106, 45)
        jump(48, 126)


def _lower_fold(source: bytearray) -> None:
    code = _SpillCode(41552)
    code.jump(41552, 36)
    code.reset()
    code.walk(201)
    code.return_to = _lower_return
    mask, word = 143, 149
    ones, twos, zero = 128, 129, 198
    code.mix(201, 147)
    code.mix(twos, mask)
    code.apply("*", mask)
    code.mix(zero, mask)
    code.mix(twos, mask)
    code.apply("p", word)
    code.mix(twos, word)
    code.mix(ones, mask)
    code.apply("p", word)
    code.mix(twos, word)
    code.dispatch()
    code.write(source, 11786, 12263)


def _middle_fold(source: bytearray) -> None:
    code = _SpillCode(45926)
    code.jump(45926, 45)
    code.jump(48, 126)
    code.walk(202)
    code.return_to = _mid_return
    mask, word, seed = 48, 149, 126
    ones, twos, zero = 128, 129, 198
    code.mix(202, 147)
    code.mix(zero, mask)
    code.mix(twos, mask)
    code.apply("p", word)
    code.mix(twos, word)
    code.mix(ones, mask)
    code.apply("p", word)
    code.mix(zero, seed)
    code.mix(twos, seed)
    code.mix(ones, seed)
    code.apply("p", word)
    code.dispatch()
    code.write(source, 24908, 25431)


def _upper_fold(source: bytearray) -> None:
    code = _SpillCode(54674)
    code.jump(54674, 39)
    code.reset()
    code.return_to = _upper_return
    seed = 126
    ones, twos, zero = 128, 129, 198
    mask, word = 136, 149

    code.apply("*", 133)
    code.apply("p", 147)
    for operand in (twos, zero, twos, ones):
        code.mix(operand, mask)
    code.apply("p", word)
    code.mix(zero, mask)
    code.apply("p", word)
    code.mix(twos, word)
    for _ in range(2):
        code.mix(twos, mask)
    code.apply("p", word)
    code.mix(zero, seed)
    code.apply("*", seed)
    code.mix(twos, seed)
    code.mix(ones, seed)
    for _ in range(4):
        code.apply("*", seed)
    code.apply("p", word)
    code.mix(ones, seed)
    code.apply("p", word)
    code.dispatch()
    code.write(source, 31388, 32026)


def _lower_entry(source: bytearray) -> None:
    code = _SpillCode(50)
    code.short(50)
    code.jump(45, 112)
    code.jump(113, 88)
    code.rotate_selector(5)
    code.long(89)
    code.reset()
    code.apply("*", 142)
    code.apply("*", 184)
    code.apply("i", 186)
    code.write(source, 11667, 11776)


def _middle_entry(source: bytearray) -> None:
    code = _SpillCode(66)
    code.apply("p", 66)
    code.short(70)
    code.jump(45, 112)
    code.jump(112, 0)
    code.jump(2, 63)
    code.apply("p", 66)
    code.short(70)
    code.apply("p", 46)
    code.short(50)
    code.apply("p", 46)
    code.apply("p", 48)
    code.short(50)
    code.apply("p", 48)
    code.short(57)
    code.return_to_readout()
    code.apply("*", 170)
    code.apply("i", 180)
    code.write(source, 24814, 24907)


def _middle_exit(source: bytearray) -> None:
    code = _SpillCode(187)
    code.walk(189)
    code.jump(189, 86)
    code.apply("p", 88)
    code.rotate_selector(3)
    code.long(89)
    code.apply("*", 40)
    code.jump(41, 36)
    code.apply("*", 37)
    code.reset()
    code.jump(125, 104)
    code.jump(105, 29525)
    code.jump(29525, 93)
    code.jump(93, 113)
    code.jump(113, 88)
    code.apply("p", 88)
    code.long(89)
    code.reset()
    code.jump(129, 0)
    code.jump(1, 86)
    code.apply("p", 86)
    code.jump(89, 54673)
    code.apply("*", 54673)
    code.jump(54674, 39)
    code.jump(51, 187)
    code.apply("i", 187)
    code.write(source, 25437, 25514)


def _lower_exit(source: bytearray) -> None:
    code = _SpillCode(165)
    code.jump(166, 125)
    code.jump(125, 104)
    code.apply("p", 105)
    code.long(109)
    code.reset()
    code.jump(125, 104)
    code.apply("p", 105)
    code.return_to_all_twos()
    code.apply("p", 115)
    code.short(117)
    code.jump(45, 112)
    code.apply("p", 115)
    code.apply("p", 118)
    for target in (118, 61):
        code.jump(119, 37)
        code.jump(38, 35)
        code.jump(35, 29525)
        if target == 118:
            code.jump(29526, 59)
            code.jump(59, 118)
        else:
            code.jump(29525, 60)
        code.apply("p", target)
    code.jump(62, 54673)
    code.jump(54675, 38)
    code.jump(38, 35)
    code.jump(35, 29525)
    code.jump(29525, 60)
    code.apply("p", 61)
    code.long(62)
    code.reset()
    code.apply("p", 126)
    code.jump(127, 41551)
    code.jump(41552, 36)
    code.reset()
    code.apply("p", 126)
    code.jump(134, 157)
    code.apply("p", 157)
    code.jump(159, 47)
    code.return_to_readout()
    code.apply("p", 157)
    code.apply("*", 158)
    code.jump(159, 47)
    code.jump(52, 127)
    code.apply("*", 128)
    code.jump(129, 0)
    code.jump(0, 34)
    code.apply("*", 34)
    code.jump(35, 29525)
    code.jump(29525, 60)
    code.apply("i", 61)
    code.write(source, 12271, 12389)


def _write_spill_routes(source: bytearray) -> None:
    """Emit the three spill-axis folds and their hub routes."""
    _lower_entry(source)
    _lower_fold(source)
    _lower_exit(source)
    _middle_entry(source)
    _middle_fold(source)
    _middle_exit(source)
    _upper_fold(source)
