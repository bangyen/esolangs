import copy
import itertools

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.stack_based.modulous import _Machine
from esolangs.tools.modulous import modulous
from tests.interpreters.modulous_cases import finite_cases
from tests.interpreters.modulous_observer import check
from tests.interpreters.modulous_reference import InvalidError, Reference


@pytest.mark.parametrize("shard", range(8))
def test_finite_state(shard):
    for source, text, limit, draw in finite_cases()[shard::8]:
        check(source, text, limit, draw)


def test_cursorless_input_progress():
    class Cursorless(IO):
        def __init__(self):
            self.reads = 0

        def input_token(self, _prompt="Input: "):
            if self.reads == 8:
                raise EOFError
            self.reads += 1
            return "7"

        def position(self):
            return 0

    io = Cursorless()
    vm = _Machine("[INP INT][POP][RST]", io)
    seen = set()
    for _ in range(100):
        state = vm.snapshot()
        assert state not in seen
        seen.add(state)
        try:
            vm.step()
        except EOFError:
            break
    else:
        raise AssertionError("missing EOF")
    assert io.reads == 8


def test_static_program_is_in_snapshot():
    a = _Machine("[PSH INT 1]", IO())
    b = _Machine("[PSH INT 2]", IO())
    assert a.snapshot() != b.snapshot()


def test_branch_state():
    commands = [
        "ADD 2",
        "SUB -3",
        "POP",
        "SWP",
        "DUP",
        "PRT",
        "PRT INT",
        "PRT VAR1 INT",
        'PSH STR "INT"',
        "PSH VAR1",
        "VAR1--2",
        "VAR1-+2",
        "END",
        "RST",
        "JMP B 3",
        "JMP F 2 IF 0",
        "JMP B 1 NIF 0",
        "RND 1",
        "RND 3",
        "RND 256",
        "RND 0",
        "INP INT",
        "INP STR",
        "TYPO",
        "",
    ]
    checks = outcomes = 0
    for stack, command, cursor in itertools.product(
        [(), (0,), (1,), (65, 66)], commands, [0, -7]
    ):
        source = f"[{command}][END]"
        ref = Reference(source)
        ref.stack = list(stack)
        ref.cursor = cursor
        vm = _Machine(source, ScriptedIO(""))
        vm.stk = tuple(stack)
        vm.ind = cursor
        frozen = vm.snapshot()
        state = vm.branching_snapshot()
        assert not vm.branching_halted(state)
        token = ref.program[cursor % len(ref.program)].split()
        if token and token[0] == "INP":
            assert vm.branching_successors(state, 1) is None
            checks += 1
            continue
        choices = (
            range(int(token[1]))
            if token and token[0] == "RND" and int(token[1]) > 0
            else (0,)
        )
        expected = []
        error = None
        for choice in choices:
            branch = copy.deepcopy(ref)
            try:
                branch.step(choice)
            except InvalidError:
                error = "halt"
                break
            except ValueError:
                error = "value"
                break
            expected.append(
                (
                    (
                        tuple(branch.stack),
                        tuple(sorted(branch.variables.items())),
                        branch.cursor,
                    ),
                    branch.done,
                )
            )
        try:
            actual = vm.branching_successors(state, 1)
            actual_error = None
        except HaltError:
            actual_error = "halt"
        except ValueError:
            actual_error = "value"
        assert actual_error == error, (command, stack, cursor, actual_error, error)
        if error is None:
            assert set(actual) == set(expected), (command, stack, cursor)
            outcomes += len(actual)
        assert vm.snapshot() == frozen
        checks += 1
    for n in (257, 1000000):
        vm = _Machine(f"[RND {n}]", ScriptedIO(""))
        try:
            vm.branching_successors(vm.branching_snapshot(), 1000000)
        except TimeoutError:
            pass
        else:
            raise AssertionError("fanout cap ignored")


@pytest.mark.parametrize(("n", "shard"), [(1, 0), (2, 0)] + [(3, s) for s in range(16)])
def test_small_generated_state(n, shard):
    for value in range(shard, 1 << (1 << n), 16 if n == 3 else 1):
        table = format(value, f"0{1 << n}b")
        for width in (None, 1, 4, 7, 13, 40, 80, 100):
            source = modulous(table, width=width)
            if width is not None:
                assert max(map(len, source.splitlines())) <= max(width, 4)
            for row, answer in enumerate(table):
                result = check(source, " ".join(format(row, f"0{n}b")), limit=10000)
                assert result["halted"]
                assert result["error"] is None
                assert result["output"] == answer
                assert result["reads"] == n


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ('[PSH STR "A" "B"]', "multiple quoted payloads"),
        ('[PSH STR "A"junk]', "text after quoted payload"),
        ('[PSH STR "A" INT]', "text after quoted payload"),
        ('[PSH STR "A]', "unclosed module"),
        ('[PSH STR "A"[POP]]', "text after quoted payload"),
    ],
)
def test_quoted_payload_must_end_the_module(source, message):
    from tests.interpreters.modulous_reference import modules

    with pytest.raises(ValueError, match=message):
        modules(source)
    with pytest.raises(ValueError, match=r"outside any \[command\]"):
        _Machine(source, ScriptedIO())


@pytest.mark.parametrize(
    ("source", "error"),
    [
        ("[RND]", "value"),
        ("[RND nope]", "value"),
        ("[RND 0]", "halt"),
        ("[RND -1]", "halt"),
    ],
)
def test_invalid_random_operands(source, error):
    assert check(source)["error"] == error
