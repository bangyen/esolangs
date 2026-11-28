"""Packed startup arithmetic and input routing."""

from .spill_routes import _SpillCode


def _write_first_read(source: bytearray) -> None:
    code = _SpillCode(237)
    code.jump(237, 86)
    code.jump(88, 71)
    code.jump(71, 107)
    code.jump(107, 111)
    code.jump(111, 42)
    code.jump(42, 59)
    code.jump(59, 118)
    code.apply("p", 118)
    code.jump(120, 115)
    code.jump(116, 102)
    code.jump(102, 52)
    code.jump(52, 127)
    code.apply("p", 140)
    code.jump(142, 126)
    code.apply("p", 140)
    code.apply("p", 198)
    code.jump(200, 45)
    code.jump(45, 112)
    code.apply("p", 112)
    code.jump(113, 88)
    code.jump(90, 56)
    code.jump(57, 43)
    code.apply("*", 43)
    code.jump(44, 108)
    code.jump(108, 91)
    code.apply("/", 91)
    code.write(source, 237, 356)
