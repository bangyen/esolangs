"""Malbolge research assembler retaining provably known low-memory writes."""

from collections import deque

from esolangs.interpreters.other.malbolge import _crazy
from esolangs.tools.malbolge import _Planner as _BasePlanner
from esolangs.tools.malbolge import _valid_chars
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

    def goto(self, target: int) -> None:
        if self.d >= _ENTRY and self.d not in self.data:
            reverse: list[list[int]] = [[] for _ in range(_ENTRY)]
            for cell in range(_ENTRY):
                if cell + 1 < _ENTRY:
                    reverse[cell + 1].append(cell)
                value = self.mem.get(cell)
                if value is not None and 0 <= value + 1 < _ENTRY:
                    reverse[value + 1].append(cell)
            distance = {target: 0}
            queue = deque([target])
            while queue:
                cell = queue.popleft()
                for parent in reverse[cell]:
                    if parent not in distance:
                        distance[parent] = distance[cell] + 1
                        queue.append(parent)
            candidates = [char for char in _valid_chars(self.d) if char + 1 in distance]
            if not candidates:
                raise AssertionError(f"cannot return to {target}")
            # Shortest returns cut the joined decoder from 27,032 to 22,334 cells.
            self.data[self.d] = min(
                candidates, key=lambda char: (distance[char + 1], char)
            )
        super().goto(target)

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
