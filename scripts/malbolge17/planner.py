"""Malbolge research assembler retaining provably known low-memory writes."""

from esolangs.interpreters.other.malbolge import _crazy
from esolangs.tools.malbolge import _Planner as _BasePlanner
from esolangs.tools.malbolge.core import _ENTRY, _rot


class _Planner(_BasePlanner):
    """Track low operands for code above ``_ENTRY``; branch A defaults to unknown."""

    def __init__(
        self,
        start: int,
        d: int,
        mem: dict[int, int | None],
        data: dict[int, int],
        *,
        accumulator: int | None = None,
    ) -> None:
        super().__init__(start, d, mem, data)
        self.accumulator = accumulator

    def raw(self, op: str) -> None:
        word = self.mem.get(self.d) if self.d < _ENTRY else None
        if op == "/":
            self.accumulator = None
        elif op in ("*", "p"):
            value = None
            if word is not None:
                if op == "*":
                    value = _rot(word)
                elif self.accumulator is not None:
                    value = _crazy(self.accumulator, word)
            self.accumulator = value
            self.mem[self.d] = value
        super().raw(op)

    def op(self, op: str, target: int) -> None:
        self.goto(target)
        self.raw(op)
