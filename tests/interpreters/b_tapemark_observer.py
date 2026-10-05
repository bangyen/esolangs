"""Complete state checks with immutable fields frozen once per value."""

from contextlib import contextmanager

from esolangs.interpreters.grid_based.b_tapemark import _Grid, _Machine
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.b_tapemark_reference import Reference
from tests.interpreters.views import view as vm_view


class Cells(dict):
    def __init__(self, cells):
        super().__init__(cells)
        self.changed = False
        self.frozen = None

    def __setitem__(self, key, value):
        if key not in self or self[key] != value:
            self.changed = True
            self.frozen = None
        super().__setitem__(key, value)

    def __delitem__(self, key):
        super().__delitem__(key)
        self.changed = True
        self.frozen = None

    def pop(self, key, *defaults):
        if key in self:
            value = self[key]
            del self[key]
            return value
        if defaults:
            return defaults[0]
        raise KeyError(key)

    def popitem(self):
        key = next(reversed(self))
        return key, self.pop(key)

    def clear(self):
        for key in tuple(self):
            del self[key]

    def update(self, *values, **named):
        for key, value in dict(*values, **named).items():
            self[key] = value

    def setdefault(self, key, value=None):
        if key not in self:
            self[key] = value
        return self[key]

    def __ior__(self, values):
        self.update(values)
        return self

    def view(self):
        if self.frozen is None:
            self.frozen = frozenset(self.items())
        return self.frozen


def cells(grid):
    return grid._cells  # noqa: SLF001 -- Compare the complete sparse field.


@contextmanager
def observed_fields():
    original = _Grid.__init__

    def initialize(grid, marks):
        original(grid, marks)
        grid._cells = Cells(cells(grid))  # noqa: SLF001 -- Observe storage mutations.

    _Grid.__init__ = initialize
    try:
        yield
    finally:
        _Grid.__init__ = original


def coordinate(z):
    return int(z.real), -int(z.imag)


def freeze(field):
    return frozenset((coordinate(point), symbol) for point, symbol in field.items())


def check(code, stdin, answer, *, consume_all=True):
    ref = Reference(code, stdin)
    with observed_fields():
        io = ScriptedIO(stdin)
        machine = _Machine(code, io)
        cached = list(map(freeze, ref.fields))
        expected_maps = [dict(field) for field in cached]
        bank = []
        steps = 0
        while True:
            state = machine.state
            for grid, expected, marks in zip(
                state.grids, cached, expected_maps, strict=True
            ):
                if cells(grid).frozen is not expected:
                    assert cells(grid) == marks
                    cells(grid).frozen = expected
            assert (
                state.program,
                state.positions,
                state.direction,
                tuple(cells(g).view() for g in state.grids),
                state.halted,
                io.position(),
                io.past_end,
                io.getvalue(),
            ) == (
                ref.active,
                tuple(map(coordinate, ref.points)),
                (1, -1j, -1, 1j).index(ref.heading),
                tuple(cached),
                ref.halted,
                ref.offset,
                ref.past_end,
                ref.stdout,
            )
            assert vm_view(machine, "ip") == coordinate(ref.points[ref.active])
            assert vm_view(machine, "stack") == []
            assert io.reads == ref.offset
            assert vm_view(machine, "memory") == [
                state.grids,
                tuple(map(coordinate, ref.points)),
                ref.active,
            ]
            if steps % 113 == 0:
                bank.append((machine.snapshot(), tuple(cached)))
            if ref.halted:
                break
            assert steps < 100000, "execution bound reached; termination unverified"
            previous = state.grids
            ref.step()
            machine.step()
            assert all(not cells(grid).changed for grid in previous), (
                "transition changed a banked field"
            )
            for field, point, symbol in ref.writes:
                point = coordinate(point)
                old = expected_maps[field].get(point)
                new = None if symbol == " " else symbol
                if old == new:
                    continue
                if old is not None:
                    cached[field] = cached[field] - {(point, old)}
                    del expected_maps[field][point]
                if new is not None:
                    cached[field] = cached[field] | {(point, new)}
                    expected_maps[field][point] = new
            steps += 1
        assert cached == list(map(freeze, ref.fields))
        for snapshot, fields in bank:
            assert tuple(cells(g).view() for g in snapshot[0].grids) == fields
            assert all(not cells(g).changed for g in snapshot[0].grids)
            assert all(
                cells(g) == dict(expected)
                for g, expected in zip(snapshot[0].grids, fields, strict=True)
            )
            hash(snapshot)
        assert io.getvalue() == answer
        assert (io.position(), io.reads) == (ref.offset, ref.offset)
        if consume_all:
            assert ref.offset == len(stdin)
        previous = machine.snapshot()
        machine.step()
        assert machine.snapshot() == previous
        return steps
