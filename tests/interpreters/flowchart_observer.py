"""Observe full independent Flowchart state, views and I/O each round."""

from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.flowchart_reference import Reference, coordinate
from tests.interpreters.views import view as vm_view


def compare(machine, ref, io):
    assert machine.halted == ref.done
    assert machine.snapshot() == ref.snapshot()
    assert machine.width == ref.width
    live = [p for p in ref.pointers if not p.done]
    assert vm_view(machine, "ip") == (
        (*coordinate(live[0].point), *coordinate(live[0].heading)) if live else None
    )
    assert vm_view(machine, "memory") == [
        v for k in sorted(ref.tapes) for v in ref.tapes[k]
    ]
    assert vm_view(machine, "stack") == []
    assert (io.getvalue(), io.position(), io.reads, io.past_end) == (
        ref.output,
        ref.offset,
        ref.reads,
        ref.past_end,
    )


def step(machine, ref, io):
    expected = actual = None
    try:
        ref.step()
    except ValueError:
        expected = ValueError
    try:
        machine.step()
    except ValueError:
        actual = ValueError
    assert expected == actual
    compare(machine, ref, io)
    return expected


def check(lines, stdin, machine_type, answer=None, limit=10000):
    ref = Reference(lines, stdin)
    io = ScriptedIO(stdin)
    machine = machine_type(lines, io)
    seen = {}
    for generation in range(limit):
        compare(machine, ref, io)
        snapshot = ref.snapshot()
        if ref.done or snapshot in seen:
            if answer is not None:
                assert ref.done
                assert ref.output == answer
            return {
                "halted": ref.done,
                "generations": generation,
                "output": ref.output,
                "reads": ref.reads,
                "cycle_start": seen.get(snapshot),
            }
        seen[snapshot] = generation
        if step(machine, ref, io):
            return {"error": True, "generations": generation}
    raise RuntimeError("Flowchart bound reached")


class Factory:
    """Reuse an executed input-free prefix with fresh pointer/deque state."""

    def __init__(self, lines, machine_type):
        self.ref = Reference(lines)
        self.machine = machine_type(lines, ScriptedIO())
        self.prefix_generations = 0
        while not self.ref.done and not any(
            not p.done and self.ref.nodes.get(self.ref.owner.get(p.point)) == "/ /"
            for p in self.ref.pointers
        ):
            assert step(self.machine, self.ref, self.machine.io) is None
            self.prefix_generations += 1
            if self.prefix_generations == 100000:
                raise RuntimeError("Flowchart prefix bound reached")
        compare(self.machine, self.ref, self.machine.io)
        assert self.ref.reads == 0
        assert self.ref.output == ""

    def pair(self, stdin):
        import copy

        ref = copy.copy(self.ref)
        ref.pointers = copy.deepcopy(self.ref.pointers)
        ref.tapes = copy.deepcopy(self.ref.tapes)
        ref.stdin = stdin
        machine = copy.copy(self.machine)
        machine.state = copy.deepcopy(self.machine.state)
        machine.io = ScriptedIO(stdin)
        return machine, ref, machine.io

    def check(self, stdin, answer, limit=100000):
        machine, ref, io = self.pair(stdin)
        compare(machine, ref, io)
        for generation in range(limit):
            if ref.done:
                assert ref.output == answer
                return {
                    "halted": True,
                    "generations": generation + self.prefix_generations,
                    "reads": ref.reads,
                }
            assert step(machine, ref, io) is None
        raise RuntimeError("Flowchart suffix bound reached")
