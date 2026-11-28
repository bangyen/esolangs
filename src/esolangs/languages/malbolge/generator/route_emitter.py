"""Emit packed decoder instructions while tracking the data pointer."""

from __future__ import annotations

from collections.abc import Callable

from .isa import _char_for
from .packed_layout import _LONG_HUB, _SHORT_HUB

type _Jump = Callable[[int, int], None]
type _Return = Callable[[int, int, _Jump], None]


class _RouteEmitter:
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
