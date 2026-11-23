"""Route the data pointer by fixed landing intervals."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from typing import NamedTuple

from esolangs.languages.malbolge.interpreter import _crazy

from .isa import _ACTIVE, _char_for, _rot

# Holding a source byte fixed, the legal addresses repeat every 94
# cells. The largest cyclic gap bounds the cost of walking to a legal
# encoding and taking its jump (at most gap - 1 walks and one jump).
_ENCODING_PERIOD = 94
_ENCODING_OFFSETS = sorted(_char_for(op, 0) - 33 for op in _ACTIVE)
_ENCODING_GAP = max(
    right - left
    for left, right in zip(
        _ENCODING_OFFSETS,
        [*_ENCODING_OFFSETS[1:], _ENCODING_OFFSETS[0] + _ENCODING_PERIOD],
        strict=True,
    )
)
_RESET_OFFSET = _ENCODING_OFFSETS[0]
# Halve the walk budget, rounding up, until it fits within the reset's
# alignment walk. At that scale, go straight to the exact-landing tier.
_NARROWINGS = ((_ENCODING_GAP - 1) // _RESET_OFFSET).bit_length()
_LANDING_WIDTHS = (
    *(1 + ((_ENCODING_GAP - 1) >> shift) for shift in range(_NARROWINGS + 1)),
    0,
)


class _Landings:
    """Index each upper landing bound by a bit per known source cell."""

    def __init__(self, mem: dict[int, int | None], ceiling: int) -> None:
        self.masks = [0] * ceiling
        for address, value in mem.items():
            self.update(address, None, value)

    def update(self, address: int, old: int | None, new: int | None) -> None:
        """Toggle the source bit wherever its eligibility changed."""
        ceiling = len(self.masks)
        if address >= ceiling or old == new:
            return
        before = ceiling if old is None else old + 1
        after = ceiling if new is None else new + 1
        bit = 1 << address
        for bound in range(min(before, after), min(max(before, after), ceiling)):
            self.masks[bound] ^= bit

    def first(
        self, start: int, floor: int, cap: int, exclude: int | None
    ) -> int | None:
        """Get the first source at or above start in the landing interval."""
        mask = self.masks[cap] ^ self.masks[floor - 1]
        if exclude is not None:
            mask &= ~(1 << exclude)
        remaining = mask >> start
        if not remaining:
            return None
        return start + (remaining & -remaining).bit_length() - 1


class _Page(NamedTuple):
    pointer: int
    start: int
    limit: int


class _Route(NamedTuple):
    ops: str
    data: dict[int, int]


def _valid_chars(address: int) -> list[int]:
    return [_char_for(op, address) for op in _ACTIVE]


class _Planner:
    """Emit known D transitions and track words written through D."""

    def __init__(
        self,
        start: int,
        d: int,
        mem: dict[int, int | None],
        data: dict[int, int],
        *,
        ceiling: int,
        a: int | None = None,
    ) -> None:
        self.code: dict[int, str] = {}
        self.c, self.d, self.a = start, d, a
        self.mem, self.data, self.ceiling = mem, data, ceiling
        self._landings = _Landings(mem, ceiling)
        self._pages: deque[_Page] = deque()
        self._limit: int | None = None

    def paginate(self, limit: int, pages: Iterable[_Page]) -> None:
        """Enable continuation pages in their fixed emission order."""
        self._limit = limit
        self._pages.extend(pages)

    def _emit(self, ops: str) -> None:
        end = self.c + len(ops)
        if self._limit is not None and end > self._limit:
            raise AssertionError(f"code crosses page boundary at {self._limit}")
        self.code.update(enumerate(ops, self.c))
        self.c = end

    def raw(self, op: str) -> None:
        """Emit an instruction and update the tracked data word and A."""
        cell = self.d
        self._emit(op)
        self.d += 1
        if op == "/":
            self.a = None
        elif op in "p*":
            old = self.mem.get(cell)
            if op == "*":
                self.a = None if old is None else _rot(old)
            elif self.a is not None and old is not None:
                self.a = _crazy(self.a, old)
            else:
                self.a = None
            self.mem[cell] = self.a
            self._landings.update(cell, old, self.a)

    def _route(
        self,
        start: int,
        target: int,
        pending: dict[int, int],
        *,
        exclude: int | None = None,
    ) -> _Route:
        """Construct one route by successively narrowing its landing interval."""
        pos = start
        ops: list[str] = []
        data: dict[int, int] = {}

        def data_jump(address: int, default: int) -> int:
            value = pending.get(address, self.data.get(address, default))
            data[address] = value
            ops.append("j")
            return value + 1

        if pos >= self.ceiling:
            pos = data_jump(pos, min(_valid_chars(pos)))

        def tier(width: int, cap: int) -> None:
            nonlocal pos
            floor = max(cap - width, pos + 2 if pos <= target else 34)
            if floor > cap:
                return
            source = self._landings.first(pos, floor, cap, exclude)
            if source is None:
                return
            value = self.mem[source]
            assert value is not None
            if pos > target or source < value:
                ops.append("o" * (source - pos) + "j")
                pos = value + 1

        if target >= 128:
            tier(_ENCODING_GAP, target)
        for width in _LANDING_WIDTHS:
            tier(width, min(127, target))

        if pos > target:
            # The walked region ends on an encoding-period boundary.
            # The first legal site for byte 33 jumps back to 34.
            reset = self.ceiling + _RESET_OFFSET
            ops.append("o" * (reset - pos))
            pos = data_jump(reset, 33)
            assert pos == 34
        ops.append("o" * (target - pos))
        return _Route("".join(ops), data)

    def _take(self, route: _Route, target: int) -> None:
        self._emit(route.ops)
        self.data.update(route.data)
        self.d = target

    def goto(self, target: int, *, after_hub: int | None = None) -> None:
        """Emit the fixed route, entering the next page when space runs low."""
        while True:
            route = self._route(self.d, target, {})
            if self._limit is None:
                self._take(route, target)
                return
            reserve = 0
            if self._pages:
                # Raw reads may advance D by up to two after the operation.
                after = target + 1 if after_hub is None else after_hub
                branch = self._pages[0].pointer
                reserve = 1 + max(
                    len(
                        self._route(
                            after + offset, branch, route.data, exclude=target
                        ).ops
                    )
                    for offset in range(3 if after_hub is None else 1)
                )
            if self.c + len(route.ops) + reserve + 4 <= self._limit:
                self._take(route, target)
                return
            if not self._pages:
                raise AssertionError(f"no continuation page for {target} at {self.c}")
            page = self._pages.popleft()
            self._take(self._route(self.d, page.pointer, {}), page.pointer)
            self.raw("i")
            self.c, self._limit = page.start, page.limit

    def op(self, op: str, target: int) -> None:
        """Route D to target and emit the operation."""
        self.goto(target)
        self.raw(op)

    def hub(self, pointer: int, value: int) -> None:
        """Jump through a pointer holding value to the hub at value + 1."""
        self.goto(pointer, after_hub=value + 2)
        self.raw("j")
        self.d = value + 1
