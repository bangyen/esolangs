"""Observe full Painfuck reference states, views and ports each command."""

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.painfuck import _Machine
from tests.interpreters.painfuck_reference import InvalidOperationError, Reference
from tests.interpreters.views import view as vm_view


class Coins:
    def __init__(self, values):
        self.values = values
        self.count = 0

    def randbelow(self, upper):
        value = self.values[self.count]
        self.count += 1
        assert 0 <= value < upper
        return value


def compare(vm, ref, port, rng):
    state = (tuple(ref.tape), tuple(ref.loops), ref.pointer, ref.cursor, ref.repeat)
    assert vm.snapshot() == (*state, ref.offset, ref.program, ref.reads, ref.draws)
    assert vm.halted == ref.halted
    assert vm_view(vm, "ip") == ref.cursor
    assert vm_view(vm, "memory") == ref.tape
    assert vm_view(vm, "stack") == ref.loops
    assert (port.position(), port.reads, port.getvalue(), rng.count) == (
        ref.offset,
        ref.reads,
        ref.output,
        ref.draws,
    )


def check(source, text="", coins=(), limit=10000):
    ref = Reference(source, text, coins)
    port = ScriptedIO(text)
    rng = Coins(coins)
    vm = _Machine(source, port, rng)
    error = None
    for generation in range(limit + 1):
        compare(vm, ref, port, rng)
        if ref.halted or error or generation == limit:
            return {
                "halted": ref.halted,
                "generations": generation,
                "output": ref.output,
                "reads": ref.reads,
                "error": error,
                "bounded": generation == limit,
            }
        frozen = vm.snapshot()
        value = hash(frozen)
        try:
            ref.step()
            expected = None
        except InvalidOperationError:
            expected = "invalid"
        except EOFError:
            expected = "eof"
        try:
            vm.step()
            error = None
        except HaltError:
            error = "invalid"
        except EOFError:
            error = "eof"
        assert error == expected
        assert hash(frozen) == value
    raise AssertionError("unreachable execution bound")
