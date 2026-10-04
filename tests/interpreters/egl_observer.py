"""Compare independent EGL full state and I/O after every command."""

from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.egl_reference import Reference


def compare(machine, ref, io):
    assert machine.halted == ref.done
    assert machine.snapshot() == ref.snapshot()
    assert machine.ip == (ref.point[1], ref.point[0])
    assert machine.memory == list(ref.values)
    assert machine.stack == []
    assert (io.position(), io.reads, io.past_end, io.getvalue()) == (
        ref.offset,
        ref.reads,
        ref.past_end,
        ref.output,
    )


def step(machine, ref, io):
    expected = actual = None
    try:
        ref.step()
    except (EOFError, ValueError) as error:
        expected = type(error)
    try:
        machine.step()
    except (EOFError, ValueError) as error:
        actual = type(error)
    assert (actual is None and expected is None) or (
        actual is not None and expected is not None and issubclass(actual, expected)
    ), (actual, expected)
    compare(machine, ref, io)
    return expected


def check(source, stdin, machine_type, answer=None, limit=100000):
    ref = Reference(source, stdin)
    io = ScriptedIO(stdin)
    machine = machine_type(source, io)
    seen = set()
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
            }
        seen.add(snapshot)
        if step(machine, ref, io):
            return {"error": True, "generations": generation, "reads": ref.reads}
    raise RuntimeError("EGL bound reached")


class Factory:
    """Reuse an executed input-free prefix; each row receives fresh I/O."""

    def __init__(self, source, machine_type):
        self.ref = Reference(source)
        self.machine = machine_type(source, ScriptedIO())
        self.prefix_generations = 0
        while not self.ref.done and self.ref.program[self.ref.pc] != "x":
            compare(self.machine, self.ref, self.machine.io)
            assert step(self.machine, self.ref, self.machine.io) is None
            self.prefix_generations += 1
        compare(self.machine, self.ref, self.machine.io)
        assert self.ref.reads == 0
        assert not self.ref.output

    def pair(self, stdin):
        import copy

        ref = copy.copy(self.ref)
        ref.cells = self.ref.cells.copy()
        ref.frames = self.ref.frames.copy()
        ref.stdin = stdin
        machine = copy.copy(self.machine)
        machine.io = ScriptedIO(stdin)
        return machine, ref, machine.io

    def check(self, stdin, answer, limit=100000):
        machine, ref, io = self.pair(stdin)
        for generation in range(limit):
            compare(machine, ref, io)
            if ref.done:
                assert ref.output == answer
                return {
                    "halted": True,
                    "generations": self.prefix_generations + generation,
                    "reads": ref.reads,
                }
            assert step(machine, ref, io) is None
        raise RuntimeError("EGL bound reached")
