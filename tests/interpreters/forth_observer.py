from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.forth import _Machine
from tests.interpreters.forth_reference import EmptyError, ExhaustedError
from tests.interpreters.forth_stepped_reference import Stepped


def check(source, text):
    generations = 0
    ref = Stepped(source, text)
    io = ScriptedIO(text)
    vm = _Machine(source, io)
    for _ in range(10000):
        assert vm.stack == tuple(ref.evaluator.stack)
        assert vm.table == ref.evaluator.functions
        assert [(f.code, f.pc, f.loop) for f in vm.frames] == [
            tuple(f) for f in ref.frames
        ]
        assert vm.error == ref.error
        assert vm.halted == (not ref.frames)
        assert io.position() == ref.position
        assert io.getvalue() == ref.evaluator.output
        expected_snapshot = (
            tuple(ref.evaluator.stack),
            frozenset(ref.evaluator.functions.items()),
            tuple(tuple(f) for f in ref.frames),
            ref.position,
            ref.evaluator.reads,
        )
        assert vm.snapshot() == expected_snapshot
        expected_ip = tuple(frame[1] for frame in ref.frames) or (len(source),)
        assert vm.ip == expected_ip
        assert vm.memory == []
        if vm.halted:
            break
        try:
            ref.step()
            expected = None
        except EmptyError:
            expected = "empty"
        except ExhaustedError:
            expected = "eof"
        previous_snapshot = vm.snapshot()
        try:
            vm.step()
            actual = None
        except HaltError:
            actual = "empty"
        except EOFError:
            actual = "eof"
        assert previous_snapshot == expected_snapshot
        assert actual == expected, (source, actual, expected)
        generations += 1
        if actual:
            assert vm.stack == tuple(ref.evaluator.stack)
            assert [(f.code, f.pc, f.loop) for f in vm.frames] == [
                tuple(f) for f in ref.frames
            ]
            break
    else:
        raise AssertionError(("bound", source))
    return {
        "generations": generations,
        "reads": ref.evaluator.reads,
        "output": ref.evaluator.output,
    }
