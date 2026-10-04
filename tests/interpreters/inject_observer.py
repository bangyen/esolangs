from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.inject import _Machine
from tests.interpreters.inject_reference import InvalidError, Reference


def check(source, text="", limit=10000):
    ref = Reference(source, text)
    io = ScriptedIO(text)
    vm = _Machine(source, io)
    generations = 0
    actual = None
    for _ in range(limit):
        spans = {name: ref.span(name) for name in ref.blocks}
        values = [node.text for node in ref.lines]
        assert vm.lines == values
        assert vm.spans == spans
        assert vm.ind == ref.cursor
        assert vm.done == ref.done
        assert vm.halted == ref.halted
        assert io.getvalue() == ref.output
        assert io.position() == ref.position
        assert vm.snapshot() == (
            ref.cursor,
            ref.done,
            tuple(values),
            ref.position,
            ref.reads,
            frozenset(spans.items()),
        )
        assert vm.memory == [
            spans[name][1] - spans[name][0] - 1 for name in sorted(spans)
        ]
        inside = [
            name for name in spans if spans[name][0] < ref.cursor < spans[name][1]
        ]
        expected_stack = list(
            reversed(sorted(inside, key=lambda name: spans[name][1] - spans[name][0]))  # noqa: C413 - reverse equal-width ties too
        )
        assert vm.stack == expected_stack
        assert vm.ip == ref.cursor
        if vm.halted or actual:
            break
        frozen = vm.snapshot()
        expected_frozen = (
            ref.cursor,
            ref.done,
            tuple(values),
            ref.position,
            ref.reads,
            frozenset(spans.items()),
        )
        try:
            ref.step()
            expected = None
        except InvalidError:
            expected = "invalid"
        except ValueError:
            expected = "syntax"
        except EOFError:
            expected = "eof"
        try:
            vm.step()
            actual = None
        except HaltError:
            actual = "invalid"
        except ValueError:
            actual = "syntax"
        except EOFError:
            actual = "eof"
        assert actual == expected, (source, actual, expected)
        assert frozen == expected_frozen
        generations += 1
    else:
        raise AssertionError(("bound", source))
    return {
        "halted": vm.halted,
        "generations": generations,
        "reads": ref.reads,
        "output": ref.output,
        "error": actual,
    }
