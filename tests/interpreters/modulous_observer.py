from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.modulous import _Machine
from tests.interpreters.modulous_reference import InvalidError, Reference
from tests.interpreters.views import view as vm_view


class Draw:
    def __init__(self, value):
        self.value = value
        self.count = 0

    def randbelow(self, upper):
        self.count += 1
        return self.value % upper


def check(source, text="", limit=100, draw=0):
    ref = Reference(source, text)
    io = ScriptedIO(text)
    rng = Draw(draw)
    vm = _Machine(source, io, rng)
    error = None
    assert vm.tokens == ref.program
    for generation in range(limit + 1):
        assert vm.ind == ref.cursor
        assert list(vm.stk) == ref.stack
        assert vm.var == ref.variables
        assert vm.halted == ref.halted
        assert vm_view(vm, "memory") == []
        assert vm_view(vm, "stack") == ref.stack
        assert vm_view(vm, "ip") == ref.cursor
        assert io.position() == ref.position
        assert io.getvalue() == ref.output
        assert rng.count == ref.draws
        assert vm.snapshot() == (
            ref.cursor,
            tuple(ref.stack),
            tuple(sorted(ref.variables.items())),
            ref.position,
            ref.done,
            ref.program,
            ref.reads,
            ref.draws,
        )
        if ref.halted or error or generation == limit:
            break
        frozen = vm.snapshot()
        before_hash = hash(frozen)
        token = ref.program[ref.cursor % len(ref.program)].split()
        choice = 0
        if token and token[0] == "RND":
            try:
                bound = int(token[1])
            except (IndexError, ValueError):
                bound = 0
            if bound > 0:
                choice = draw % bound
        try:
            ref.step(choice)
            expected = None
        except InvalidError:
            expected = "halt"
        except ValueError:
            expected = "value"
        except EOFError:
            expected = "eof"
        try:
            vm.step()
            error = None
        except HaltError:
            error = "halt"
        except ValueError:
            error = "value"
        except EOFError:
            error = "eof"
        assert error == expected, (source, error, expected)
        assert hash(frozen) == before_hash
    return {
        "generations": generation,
        "halted": ref.halted,
        "error": error,
        "output": ref.output,
        "reads": ref.reads,
        "draws": ref.draws,
    }
