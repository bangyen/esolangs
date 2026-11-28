"""Arithmetic and low pointer routes for the three packed spill axes."""

from __future__ import annotations

from collections.abc import Callable

from .isa import _char_for
from .packed_layout import (
    _LONG_HUB,
    _ONE_HUB,
    _SHORT_HUB,
)

type _Jump = Callable[[int, int], None]
type _Return = Callable[[int, int, _Jump], None]


class _SpillCode:
    """Emit forward walks and jumps through known return operands."""

    def __init__(self, pointer: int, return_to: _Return | None = None) -> None:
        self.pointer = pointer
        self.return_to = return_to
        self.ops: list[str] = []

    def _emit(self, op: str, target: int) -> None:
        if self.return_to is not None:
            self.return_to(self.pointer, target, self.jump)
        self.walk(target)
        self.ops.append(op)
        self.pointer += 1

    def rotate(self, target: int) -> None:
        self._emit("*", target)

    def crazy(self, target: int) -> None:
        self._emit("p", target)

    def read(self, target: int) -> None:
        self._emit("/", target)

    def jump_code(self, target: int) -> None:
        self._emit("i", target)

    def walk(self, target: int) -> None:
        assert target >= self.pointer
        self.ops.append("o" * (target - self.pointer))
        self.pointer = target

    def jump(self, operand: int, landing: int) -> None:
        self.walk(operand)
        self.ops.append("j")
        self.pointer = landing

    def mix(self, operand: int, target: int) -> None:
        self.rotate(operand)
        self.crazy(target)

    def short(self, operand: int) -> None:
        self.jump(operand, _SHORT_HUB)
        self.jump(_SHORT_HUB + 1, 45)

    def long(self, operand: int) -> None:
        self.jump(operand, _LONG_HUB)
        self.jump(_LONG_HUB + 1, 39)

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

    def return_to_staged_word(self) -> None:
        """Return from the staging cells to D126."""
        self.jump(204, 73)
        self.jump(74, 48)
        self.jump(48, 126)

    def rotate_selector(self, count: int) -> None:
        for _ in range(count):
            self.jump(93, 113)
            self.jump(113, 88)
            self.rotate(88)

    def dispatch(self) -> None:
        self.rotate(167)
        self.mix(128, 167)
        self.jump_code(167)

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
    start, pointer, end = 11786, _ONE_HUB + 1, 12263
    code = _SpillCode(pointer)
    code.jump(_ONE_HUB + 1, 36)
    code.reset()
    code.walk(201)
    code.return_to = _lower_return
    mask, word = 143, 149
    ones, twos, zero = 128, 129, 198
    code.mix(201, 147)
    code.mix(twos, mask)
    code.rotate(mask)
    code.mix(zero, mask)
    code.mix(twos, mask)
    code.crazy(word)
    code.mix(twos, word)
    code.mix(ones, mask)
    code.crazy(word)
    code.mix(twos, word)
    code.dispatch()
    code.write(source, start, end)


def _middle_fold(source: bytearray) -> None:
    start, pointer, end = 24908, _SHORT_HUB + 1, 25431
    code = _SpillCode(pointer)
    code.jump(_SHORT_HUB + 1, 45)
    code.jump(48, 126)
    code.walk(202)
    code.return_to = _mid_return
    mask, word, seed = 48, 149, 126
    ones, twos, zero = 128, 129, 198
    code.mix(202, 147)
    code.mix(zero, mask)
    code.mix(twos, mask)
    code.crazy(word)
    code.mix(twos, word)
    code.mix(ones, mask)
    code.crazy(word)
    code.mix(zero, seed)
    code.mix(twos, seed)
    code.mix(ones, seed)
    code.crazy(word)
    code.dispatch()
    code.write(source, start, end)


def _upper_fold(source: bytearray) -> None:
    start, pointer, end = 31388, _LONG_HUB + 1, 32026
    code = _SpillCode(pointer)
    code.jump(_LONG_HUB + 1, 39)
    code.reset()
    code.return_to = _upper_return
    seed = 126
    ones, twos, zero = 128, 129, 198
    mask, word = 136, 149

    code.rotate(133)
    code.crazy(147)
    for operand in (twos, zero, twos, ones):
        code.mix(operand, mask)
    code.crazy(word)
    code.mix(zero, mask)
    code.crazy(word)
    code.mix(twos, word)
    for _ in range(2):
        code.mix(twos, mask)
    code.crazy(word)
    code.mix(zero, seed)
    code.rotate(seed)
    code.mix(twos, seed)
    code.mix(ones, seed)
    for _ in range(4):
        code.rotate(seed)
    code.crazy(word)
    code.mix(ones, seed)
    code.crazy(word)
    code.dispatch()
    code.write(source, start, end)


def _lower_entry(source: bytearray) -> None:
    start, pointer, end = 11667, 50, 11776
    code = _SpillCode(pointer)
    code.short(50)
    code.jump(45, 112)
    code.jump(113, 88)
    code.rotate_selector(5)
    code.long(89)
    code.reset()
    code.rotate(142)
    code.rotate(184)
    code.jump_code(186)
    code.write(source, start, end)


def _middle_entry(source: bytearray) -> None:
    start, pointer, end = 24814, 66, 24907
    code = _SpillCode(pointer)
    code.crazy(66)
    code.short(70)
    code.jump(45, 112)
    code.jump(112, 0)
    code.jump(2, 63)
    code.crazy(66)
    code.short(70)
    code.crazy(46)
    code.short(50)
    code.crazy(46)
    code.crazy(48)
    code.short(50)
    code.crazy(48)
    code.short(57)
    code.return_to_readout()
    code.rotate(170)
    code.jump_code(180)
    code.write(source, start, end)


def _middle_exit(source: bytearray) -> None:
    start, pointer, end = 25437, 187, 25514
    code = _SpillCode(pointer)
    code.walk(189)
    code.jump(189, 86)
    code.crazy(88)
    code.rotate_selector(3)
    code.long(89)
    code.rotate(40)
    code.jump(41, 36)
    code.rotate(37)
    code.reset()
    code.jump(125, 104)
    code.jump(105, 29525)
    code.jump(29525, 93)
    code.jump(93, 113)
    code.jump(113, 88)
    code.crazy(88)
    code.long(89)
    code.reset()
    code.jump(129, 0)
    code.jump(1, 86)
    code.crazy(86)
    code.jump(89, _LONG_HUB)
    code.rotate(_LONG_HUB)
    code.jump(_LONG_HUB + 1, 39)
    code.jump(51, 187)
    code.jump_code(187)
    code.write(source, start, end)


def _lower_exit(source: bytearray) -> None:
    start, pointer, end = 12271, 165, 12389
    code = _SpillCode(pointer)
    code.jump(166, 125)
    code.jump(125, 104)
    code.crazy(105)
    code.long(109)
    code.reset()
    code.jump(125, 104)
    code.crazy(105)
    code.return_to_all_twos()
    code.crazy(115)
    code.short(117)
    code.jump(45, 112)
    code.crazy(115)
    code.crazy(118)
    for target in (118, 61):
        code.jump(119, 37)
        code.jump(38, 35)
        code.jump(35, 29525)
        if target == 118:
            code.jump(29526, 59)
            code.jump(59, 118)
        else:
            code.jump(29525, 60)
        code.crazy(target)
    code.jump(62, _LONG_HUB)
    code.jump(54675, 38)
    code.jump(38, 35)
    code.jump(35, 29525)
    code.jump(29525, 60)
    code.crazy(61)
    code.long(62)
    code.reset()
    code.crazy(126)
    code.jump(127, _ONE_HUB)
    code.jump(_ONE_HUB + 1, 36)
    code.reset()
    code.crazy(126)
    code.jump(134, 157)
    code.crazy(157)
    code.jump(159, 47)
    code.return_to_readout()
    code.crazy(157)
    code.rotate(158)
    code.jump(159, 47)
    code.jump(52, 127)
    code.rotate(128)
    code.jump(129, 0)
    code.jump(0, 34)
    code.rotate(34)
    code.jump(35, 29525)
    code.jump(29525, 60)
    code.jump_code(61)
    code.write(source, start, end)


def _write_spill_routes(source: bytearray) -> None:
    """Emit the three spill-axis folds and their hub routes."""
    _lower_entry(source)
    _lower_fold(source)
    _lower_exit(source)
    _middle_entry(source)
    _middle_fold(source)
    _middle_exit(source)
    _upper_fold(source)
