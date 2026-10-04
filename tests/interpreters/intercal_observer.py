from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.intercal import _Machine
from tests.interpreters.intercal_reference import InvalidError, Reference, statements


def check(source, text="", limit=1000):
    ref = Reference(source, text)
    io = ScriptedIO(text)
    vm = _Machine(source, io)
    fixed_program = tuple(vm.lines)
    assert statements("\n".join(fixed_program)) == ref.program
    generations = 0
    error = None
    for _ in range(limit):
        packed = tuple(sorted(ref.variables.items()))
        calls = tuple(ref.calls)
        expected = (
            ref.cursor,
            packed,
            calls,
            ref.position,
            ref.reads,
            fixed_program,
            tuple(sorted(ref.labels.items())),
        )
        assert vm.snapshot() == expected
        assert vm.state == (ref.cursor, packed, calls)
        assert vm.labels == ref.labels
        assert tuple(vm.lines) == fixed_program
        assert vm.memory == [v for k, v in packed]
        assert vm.stack == list(calls)
        assert vm.ip == ref.cursor
        assert io.position() == ref.position
        assert io.getvalue() == ref.output
        assert vm.halted == ref.halted
        if vm.halted or error:
            break
        frozen = vm.snapshot()
        try:
            ref.step()
            expected_error = None
        except InvalidError:
            expected_error = "invalid"
        except EOFError:
            expected_error = "eof"
        try:
            vm.step()
            error = None
        except HaltError:
            error = "invalid"
        except EOFError:
            error = "eof"
        assert error == expected_error
        assert frozen == expected
        generations += 1
    else:
        raise AssertionError(("bound", source))
    return {
        "halted": vm.halted,
        "generations": generations,
        "reads": ref.reads,
        "output": ref.output,
        "error": error,
    }
