from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.unsquare import _Machine
from tests.interpreters.unsquare_reference import InvalidOperationError, Reference


def compare(machine, ref, port):
    assert machine.snapshot() == ref.snapshot()
    assert machine.halted == ref.halted
    assert machine.ip == ref.pc
    assert machine.memory == [ref.accumulator]
    assert machine.stack == tuple(ref.values)
    assert machine.jumps == tuple(start - 1 for start in ref.loops)
    assert (port.getvalue(), port.position(), port.reads, port.past_end) == (
        ref.output,
        ref.offset,
        ref.reads,
        ref.past_end,
    )


def step(machine, ref, port):
    expected = actual = None
    try:
        ref.step()
    except InvalidOperationError:
        expected = HaltError
    except EOFError:
        expected = EOFError
    try:
        machine.step()
    except HaltError:
        actual = HaltError
    except EOFError:
        actual = EOFError
    assert expected == actual
    compare(machine, ref, port)
    return expected


def check(source, text="", limit=100000):
    ref = Reference(source, text)
    port = ScriptedIO(text)
    machine = _Machine(source, port)
    seen = {}
    for generation in range(limit):
        compare(machine, ref, port)
        snapshot = ref.snapshot()
        if ref.halted or snapshot in seen:
            return {
                "halted": ref.halted,
                "generations": generation,
                "output": ref.output,
                "reads": ref.reads,
                "error": None,
                "cycle_start": seen.get(snapshot),
            }
        seen[snapshot] = generation
        error = step(machine, ref, port)
        if error:
            return {
                "halted": ref.halted,
                "generations": generation,
                "output": ref.output,
                "reads": ref.reads,
                "error": error.__name__,
            }
    raise RuntimeError("Unsquare execution bound")
