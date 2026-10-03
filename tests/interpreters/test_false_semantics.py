"""FALSE agrees with independently parsed recursive stack evaluation."""

import itertools

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.false import _Lambda, _Machine
from esolangs.tools.false import false
from tests.interpreters.false_reference import Function, Reference


def normalized(values):
    return [
        ("lambda", value.start, value.end)
        if isinstance(value, (Function, _Lambda))
        else value
        for value in values
    ]


def check(code, stdin=""):
    reference = Reference(code, stdin)
    reference.execute(limit=20000)
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    for _ in range(20000):
        if machine.halted:
            break
        machine.step()
    else:
        raise AssertionError(("native bound", code))
    assert (io.getvalue(), normalized(machine.stack), io.position(), io.past_end) == (
        reference.output,
        normalized(reference.stack),
        reference.offset,
        reference.past_end,
    ), (code, stdin)
    return reference


def test_independent_stack_semantics():
    numbers = (0, 1, 2, 7, 255, 256, 2147483647, 2147483648, 4294967295, 4294967296)
    for left, right, op in itertools.product(numbers, numbers, "+-*/&|>="):
        if op == "/" and right % 4294967296 == 0:
            continue
        check(f"{left} {right}{op}.")
    for left, right in itertools.product((1, 7, 2147483648, 4294967295), (1, 2, 7)):
        check(f"{left}_ {right}/.")
        check(f"{left} {right}_/.")
    for number, op in itertools.product(numbers, "_~"):
        check(f"{number}{op}.")
    for a, b, c in itertools.product(range(4), repeat=3):
        for suffix in ("@", "\\", "$", "%", "0ø", "1O", "2ø"):
            check(f"{a} {b} {c} {suffix}")
    for flag in (0, 1, 4294967295):
        for body in ("", "3", "[4]", '"hi"', "1a:a;", "[1+]b:3b;!"):
            check(f"{flag}[{body}]?")
            check(f"[{body}]!")
    for count in range(16):
        check(f"{count}[$][1-]#")
        check(f"{count}[$0=~][$.1-]#%")
    for stdin in ("", "\n", "ABC\n", "é²٣"):
        check("[^$1_=~][,]#", stdin)
        check("^.^.^.^.^.", stdin)
    for code in (
        "",
        "1.B",
        "1.ß",
        "1.Z",
        "1².",
        "1٣.",
        "[0][]#",
        "[0][]# ",
        "[0][]#7.",
        '"[}"{[}1.',
        "']",
        "9" * 5000 + ".",
    ):
        check(code)


@pytest.mark.medium
def test_independent_generated_truth_tables():
    for n in (1, 2, 3):
        for value in range(1 << (1 << n)):
            table = f"{value:0{1 << n}b}"
            for width in (None, 1, 2, 7, 13, 40):
                code = false(table, width)
                if width is not None:
                    assert max(map(len, code.splitlines())) <= width
                for row, answer in enumerate(table):
                    stdin = f"{row:0{n}b}"
                    ref = check(code, stdin)
                    assert ref.output == answer
                    assert ref.offset == n
                    assert ref.past_end == 0


@pytest.mark.parametrize("source", ["[1", "1]", '"open', "{open", "1'"])
def test_syntax_validation_precedes_effects(source):
    io = ScriptedIO("X")
    with pytest.raises(ValueError, match=r".+"):
        Reference('^."written"' + source)
    with pytest.raises(ValueError, match=r".+"):
        _Machine('^."written"' + source, io)
    assert io.getvalue() == ""
    assert io.position() == 0


def test_loops_have_a_stable_complete_state():
    machine = _Machine("[1][]#", ScriptedIO(""))
    seen = {}
    for step in range(30):
        state = machine.snapshot()
        if state in seen:
            break
        seen[state] = step
        before = machine.snapshot()
        assert not machine.halted
        assert machine.ip is not None
        assert isinstance(machine.stack, list)
        assert machine.snapshot() == before
        machine.step()
    else:
        raise AssertionError("finite loop control failed to revisit its full state")
    assert step > seen[state]


@pytest.mark.medium
def test_shared_lambdas_and_variable_capacity_execute():
    import random

    tables = [("01101001" * 8), format(random.Random(0).getrandbits(512), "0512b")]
    for table in tables:
        n = len(table).bit_length() - 1
        for width in (None, 1, 13):
            code = false(table, width)
            for row in range(len(table)):
                reference = check(code, f"{row:0{n}b}")
                assert reference.output == table[row]
                assert reference.offset == n
                assert reference.past_end == 0


def test_public_run_forwards_character_io():
    from esolangs.interpreters.stack_based.false import run

    code = "[^$1_=~][,]#"
    reference = Reference(code, "A\né")
    reference.execute()
    io = ScriptedIO(reference.stdin)
    run(code, io=io)
    assert io.getvalue() == reference.output
    assert io.position() == reference.offset
    assert io.past_end == reference.past_end


@pytest.mark.parametrize(
    "code",
    [
        ".",
        "[]_",
        "1[]+",
        "1 0/",
        "a;",
        "1 99:",
        "1!",
        "1 2?",
        "[1]2#",
        "1 2 9ø",
        "1 1_ø",
        "[[]][]#",
        "[][]#",
    ],
)
def test_independent_invalid_operations(code):
    from esolangs.exceptions import HaltError
    from tests.interpreters.false_reference import InvalidOperationError

    reference = Reference(code)
    with pytest.raises(InvalidOperationError, match=r".+"):
        reference.execute()
    io = ScriptedIO("")
    machine = _Machine(code, io)

    def drive():
        for _ in range(100):
            if machine.halted:
                return
            machine.step()
        raise AssertionError("invalid-operation control did not stop")

    with pytest.raises(HaltError, match=r".+"):
        drive()
    assert io.getvalue() == reference.output
    assert io.position() == reference.offset
