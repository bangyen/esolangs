import copy

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO

# ruff: noqa: SLF001 -- Share checked immutable grid representations.
from tests.interpreters.dig_reference import (
    MissingOperandError,
    NegativeDistanceError,
    Reference,
    ZeroDivisorError,
)


def compare(machine, ref, io):
    assert type(machine.halted) is bool
    assert machine.halted == ref.done
    expected_code = ref.code
    if machine.code is not expected_code:
        assert machine.code == expected_code
        assert type(machine.code) is tuple
        for actual_row, expected_row in zip(machine.code, expected_code, strict=True):
            if actual_row is not expected_row:
                assert type(actual_row) is tuple
                assert all(type(cell) in (str, int) for cell in actual_row)
        # Equal immutable grids can share their representation between writes.
        ref._code = machine.code
    assert machine.snapshot() == ref.snapshot()
    assert machine.size == ref.width
    assert machine.ip == ref.snapshot()[:3]
    assert machine.memory == [ref.value]
    assert machine.stack == []
    assert io.position() == ref.offset
    assert io.reads == ref.reads
    assert io.past_end == ref.past_end
    assert io.getvalue() == ref.output


def step(machine, ref, io):
    expected = actual = None
    try:
        ref.step()
    except (MissingOperandError, ZeroDivisorError, NegativeDistanceError):
        expected = HaltError
    except (EOFError, ValueError) as error:
        expected = type(error)
    try:
        machine.step()
    except (HaltError, EOFError, ValueError) as error:
        actual = error
    if expected is None:
        assert actual is None, actual
    else:
        assert isinstance(actual, expected), (expected, actual)
    compare(machine, ref, io)
    return expected is not None


def _check(machine, ref, io, answer=None, limit=10000):
    seen = {}
    grids = {}
    previous_code = None
    grid_id = 0
    for generation in range(limit):
        compare(machine, ref, io)
        full = ref.snapshot()
        if ref.code is not previous_code:
            grid_id = grids.setdefault(ref.code, len(grids))
            previous_code = ref.code
        snapshot = (*full[:5], grid_id, *full[6:])
        if ref.done or snapshot in seen:
            if answer is not None:
                assert ref.done
                assert ref.output == answer
            return {
                "halted": ref.done,
                "generations": generation,
                "output": ref.output,
                "cycle_start": None if ref.done else seen.get(snapshot),
                "reads": ref.reads,
            }
        seen[snapshot] = generation
        if step(machine, ref, io):
            return {
                "halted": False,
                "error": True,
                "generations": generation,
                "output": ref.output,
                "reads": ref.reads,
            }
    raise RuntimeError("Dig execution bound reached")


def check(code, stdin, machine_type, answer=None, limit=10000):
    ref = Reference(code, stdin)
    io = ScriptedIO(stdin)
    return _check(machine_type(code, io), ref, io, answer, limit)


class Factory:
    def __init__(self, code, machine_type):
        self.code = code
        self.machine_type = machine_type
        self.reference_template = Reference(code)
        self.native_template = machine_type(code, ScriptedIO())
        compare(self.native_template, self.reference_template, self.native_template.io)

    def pair(self, stdin):
        ref = copy.copy(self.reference_template)
        ref.stdin = stdin
        machine = copy.copy(self.native_template)
        machine.io = ScriptedIO(stdin)
        return machine, ref, machine.io

    def check(self, stdin, answer=None, limit=10000):
        return _check(*self.pair(stdin), answer, limit)
