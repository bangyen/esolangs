from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.grapheme import _Machine
from tests.interpreters.grapheme_reference import Function, InvalidError
from tests.interpreters.grapheme_stepped_reference import Stepped
from tests.interpreters.views import view as vm_view


def value(v):
    return ("func", v.source) if isinstance(v, Function) else v


def check(source, text):
    generations = 0
    ref = Stepped(source, text)
    io = ScriptedIO(text)
    vm = _Machine(source, io)
    for _ in range(10000):
        assert vm_view(vm, "stack") == list(map(value, ref.evaluator.stack)), source
        assert dict(vm.vars) == {
            value(k): value(v) for k, v in ref.evaluator.variables.items()
        }, source
        frames = tuple(
            (
                f.source,
                f.cursor,
                {"E": "string", "F": "int", "H": "func", "": ""}[f.mode],
                tuple(f.buffer),
                f.pending,
                f.repeat,
            )
            for f in ref.frames
        )
        assert vm.frames == frames, (source, vm.frames, frames)
        expected_ip = tuple(frame.cursor for frame in ref.frames) or (
            len(source.replace("\n", "")),
        )
        assert vm_view(vm, "ip") == expected_ip
        assert vm_view(vm, "memory") == []
        assert vm.snapshot() == (
            tuple(map(value, ref.evaluator.stack)),
            frozenset((value(k), value(v)) for k, v in ref.evaluator.variables.items()),
            frames,
            ref.evaluator.position,
            ref.evaluator.reads,
        )
        assert io.getvalue() == ref.evaluator.output
        assert vm.halted == (not ref.frames)
        if vm.halted:
            break
        try:
            ref.step()
            expected = None
        except InvalidError:
            expected = "invalid"
        except EOFError:
            expected = "eof"
        except ValueError:
            expected = "malformed"
        try:
            vm.step()
            actual = None
        except HaltError:
            actual = "invalid"
        except EOFError:
            actual = "eof"
        except ValueError:
            actual = "malformed"
        assert actual == expected, (source, actual, expected)
        generations += 1
        if actual:
            break
    else:
        raise AssertionError(("bound", source))
    return {
        "generations": generations,
        "reads": ref.evaluator.reads,
        "output": ref.evaluator.output,
        "halted": vm.halted,
    }
