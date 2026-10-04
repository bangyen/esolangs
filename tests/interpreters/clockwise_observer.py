"""Full Clockwise state and IO observations against the independent model."""

import copy

from esolangs.interpreters.grid_based.clockwise import _Machine
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.clockwise_reference import Reference


def compare(ref, native, io, code):
    state = ref.state()
    assert native.state == state
    assert native.halted is ref.halted
    assert native.ip == state[:3]
    assert native.memory == [ref.accumulator]
    assert native.stack == []
    assert (
        native.row,
        native.col,
        native.r,
        native.acc,
        native.out,
        native.inp,
    ) == state[:6]
    assert (io.getvalue(), io.position(), io.reads, io.past_end) == (
        ref.output,
        ref.offset,
        ref.reads,
        0,
    )
    assert native.code == code
    snapshot = native.snapshot()
    hash(snapshot)
    assert snapshot == (*state[:6], ref.offset)
    return snapshot


def check(lines, stdin="", answer=None, limit=100000):
    ref = Reference(lines, stdin)
    io = ScriptedIO(stdin)
    native = _Machine(lines, io)
    code = native.code
    assert {
        (complex(x, y), char)
        for y, row in enumerate(code)
        for x, char in enumerate(row)
    } == set(ref.cells.items())
    return observe(ref, native, io, code, answer, limit)


def observe(ref, native, io, code, answer, limit):
    seen = {}
    banked = []
    for step in range(limit):
        snapshot = compare(ref, native, io, code)
        if ref.halted:
            if answer is not None:
                assert ref.output == answer
            native.step()
            assert compare(ref, native, io, code) == snapshot
            assert all(old == expected for old, expected in banked)
            return {"generations": step, "halted": True, "output": ref.output}
        if snapshot in seen:
            assert all(old == expected for old, expected in banked)
            return {
                "generations": step,
                "halted": False,
                "cycle_start": seen[snapshot],
                "period": step - seen[snapshot],
                "output": ref.output,
            }
        seen[snapshot] = step
        banked.append((snapshot, (*ref.state()[:6], ref.offset)))
        error = None
        try:
            ref.step()
        except (ValueError, EOFError) as caught:
            error = caught
        if error is not None:
            try:
                native.step()
            except type(error):
                assert compare(ref, native, io, code) == snapshot
                return {
                    "generations": step,
                    "error": type(error).__name__,
                    "output": ref.output,
                }
            raise AssertionError("native failed to reject the same transition")
        native.step()
    raise TimeoutError("observation bound reached; termination inconclusive")


class Factory:
    def __init__(self, lines):
        self.lines = tuple(lines)
        self.template = Reference(lines)
        self.code = tuple(row.ljust(self.template.width) for row in lines)

    def reference(self, stdin):
        ref = copy.copy(self.template)
        ref.pending = []
        ref.load_input(stdin)
        return ref

    def check(self, stdin="", answer=None, limit=100000):
        ref = self.reference(stdin)
        io = ScriptedIO(stdin)
        native = _Machine(list(self.lines), io)
        assert native.code == self.code
        return observe(ref, native, io, native.code, answer, limit)
