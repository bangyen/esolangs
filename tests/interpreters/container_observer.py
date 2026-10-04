"""Observe Container states against independent synchronous equations."""

from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.container_reference import Reference


def check(code, stdin, machine_type, answer=None, limit=10000):
    """Execute and compare every tick, returning the exact halt or recurrence."""
    ref = Reference(code, stdin)
    io = ScriptedIO(stdin)
    machine = machine_type(code, io)
    seen = {}
    for generation in range(limit):
        assert type(machine.halted) is bool
        assert machine.var == ref.values
        assert machine.queue == list(ref.queue)
        assert machine.exit_code == ref.exit_code
        assert machine.tick == ref.tick
        assert machine.ip == ref.tick
        assert machine.memory == [ref.values[name] for name in sorted(ref.values)]
        assert machine.stack == []
        assert machine.snapshot() == ref.snapshot()
        assert io.position() == ref.offset
        assert io.reads == ref.reads
        assert io.past_end == ref.past_end
        assert io.getvalue() == ref.output
        assert machine.halted == ref.halted
        snapshot = ref.snapshot()
        if ref.halted or snapshot in seen:
            if answer is not None:
                assert ref.halted
                assert ref.output == answer
            return {
                "halted": ref.halted,
                "generations": generation,
                "output": ref.output,
                "cycle_start": seen.get(snapshot),
                "reads": ref.reads,
            }
        seen[snapshot] = generation
        old = machine.snapshot()
        recorded = repr(old)
        values_view = machine.var
        memory_view = machine.memory
        expected_values = dict(ref.values)
        expected_memory = [ref.values[name] for name in sorted(ref.values)]
        machine.step()
        ref.step()
        assert repr(old) == recorded
        assert values_view == expected_values
        assert memory_view == expected_memory
    raise RuntimeError("Container execution bound reached")
