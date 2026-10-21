"""The code emitter of the Malbolge build.

The emitter writes into a ``code`` dict at a code pointer ``c`` while a data
pointer ``d`` tracks where execution will point: every instruction advances
both by one.  :class:`_Planner` knows the walked cells' values, so it steers
``d`` along a shortest path of steps and value jumps, and it tracks the
accumulator and the walked cells' contents across the writes it emits.
"""

from __future__ import annotations

from esolangs.languages.malbolge.interpreter import _crazy

from .isa import _ACTIVE, _char_for, _rot


def _valid_chars(address: int) -> list[int]:
    return [_char_for(op, address) for op in _ACTIVE]


class _Emitter:
    """A code dict under construction, at code pointer ``c``, data pointer ``d``."""

    def __init__(self, start: int, d: int, code: dict[int, str] | None = None) -> None:
        self.code: dict[int, str] = {} if code is None else code
        self.c = start
        self.d = d

    def raw(self, op: str) -> None:
        """Emit ``op`` at the code pointer; both pointers advance by one."""
        self.code[self.c] = op
        self.c += 1
        self.d += 1


class _Planner(_Emitter):
    """Emitter steering ``d`` by shortest path over ``o`` steps and ``j`` jumps.

    ``mem`` maps walked addresses to their known values (``None`` once
    written to an unknown value); ``a`` is the accumulator ``A`` when the ops
    so far have determined it, else ``None``; ``data`` maps store addresses
    above the code to source characters, which a ``j`` from there reads to
    come back below the walked region.  Knowing ``mem``/``a`` is only an
    optimisation: a cell whose value is still known stays usable as a ``j``
    target, so the shortest-path search sees the shortcuts the run-time
    pointers provide.  No path may step to ``ceiling`` or beyond.
    """

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
        super().__init__(start, d)
        self.mem = mem
        self.data = data
        self.ceiling = ceiling
        self.a = a

    def raw(self, op: str) -> None:
        cell = self.d
        super().raw(op)
        if op in "p*":
            self.mem[cell] = self._written(op, cell)
        elif op == "/":
            self.a = None

    def _written(self, op: str, cell: int) -> int | None:
        """Return the new value of ``cell`` after ``op``, or ``None`` if unknown."""
        old = self.mem.get(cell)
        if op == "*":
            if isinstance(old, int):
                self.a = _rot(old)
            else:
                self.a = None
        elif isinstance(old, int) and isinstance(self.a, int):
            self.a = _crazy(self.a, old)
        else:
            self.a = None
        return self.a

    def goto(self, target: int) -> None:
        """Steer ``d`` to ``target`` along a shortest path of ``o``/``j`` moves."""
        if self.d >= self.ceiling:
            char = self.data.setdefault(self.d, min(_valid_chars(self.d)))
            self.raw("j")
            self.d = char + 1
        previous: dict[int, tuple[int, str] | None] = {self.d: None}
        frontier = [self.d]
        while target not in previous:
            following = []
            for d in frontier:
                moves = [(d + 1, "o")]
                value = self.mem.get(d)
                if value is not None:
                    moves.append((value + 1, "j"))
                for step, op in moves:
                    if step < self.ceiling and step not in previous:
                        previous[step] = (d, op)
                        following.append(step)
            if not following:  # pragma: no cover - the walked cells cover all
                raise AssertionError(f"cannot reach {target}")
            frontier = following
        path = []
        node = target
        while (link := previous[node]) is not None:
            node, op = link
            path.append(op)
        for op in reversed(path):
            self.code[self.c] = op
            self.c += 1
        self.d = target

    def op(self, op: str, target: int) -> None:
        """Steer ``d`` to ``target`` and emit ``op`` there."""
        self.goto(target)
        self.raw(op)

    def hub(self, pointer: int, value: int, offset: int = 1) -> None:
        """``j`` through ``pointer`` (holding ``value``) to ``value + offset``."""
        self.goto(pointer)
        self.raw("j")
        self.d = value + 1
        while self.d < value + offset:
            self.raw("o")
