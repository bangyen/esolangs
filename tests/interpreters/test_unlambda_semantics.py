"""Unlambda transitions agree with independently scheduled callbacks."""

import itertools
import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.unlambda import (
    _App,
    _Apply,
    _Arg,
    _Cmd,
    _Cont,
    _Eval,
    _Machine,
    _Partial,
    _Print,
    _Promise,
    _Query,
    _Val,
)
from esolangs.tools.unlambda import unlambda
from tests.interpreters.unlambda_reference import Reference, normalize
from tests.tools.boolean_runners import five_input_sample


def native_value(value):
    if isinstance(value, _Cmd):
        return ("atom", value.name)
    if isinstance(value, _Print):
        return ("print", value.char)
    if isinstance(value, _Query):
        return ("query", value.char)
    if isinstance(value, _Partial):
        return (value.name, *(native_value(item) for item in value.args))
    if isinstance(value, _Promise):
        return ("promise", native_value(value.term))
    if isinstance(value, _Val):
        return ("value", native_value(value.value))
    if isinstance(value, _App):
        return ("app", native_value(value.f), native_value(value.a))
    if isinstance(value, _Cont):
        return (
            "continuation",
            tuple(
                ("waiting_function", native_value(frame.term))
                if isinstance(frame, _Arg)
                else ("waiting_argument", native_value(frame.value))
                for frame in value.kont
            ),
        )
    raise AssertionError(type(value))


def native_context(frames):
    return tuple(
        ("waiting_function", native_value(frame.term))
        if isinstance(frame, _Arg)
        else ("waiting_argument", native_value(frame.value))
        for frame in frames
    )


def native_view(machine):
    task, frames, char, done = machine.snapshot()[:4]
    if isinstance(task, _Eval):
        work = ("evaluate", native_value(task.term))
    elif isinstance(task, _Apply):
        work = ("apply", native_value(task.f), native_value(task.a))
    else:
        work = ("return", native_value(task.value))
    context = native_context(frames)
    return work, context, char, done


def reference_view(reference):
    task, context, char, done = reference.view()
    return (
        (task[0], *(normalize(item) for item in task[1:])),
        tuple((tag, normalize(item)) for tag, item in context),
        char,
        done,
    )


def check(code, stdin="", *, states=True):
    ref = Reference(code, stdin)
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    for step in range(30000):
        halted = ref.action is None
        assert machine.halted == halted
        assert machine.snapshot()[-1] == ref.offset
        if states or halted:
            expected = reference_view(ref)
            assert native_context(machine.stack) == expected[1]
            assert machine.ip == (
                len(expected[1]),
                ("evaluate", "apply", "return").index(expected[0][0]),
            )
            assert native_view(machine) == reference_view(ref), (
                code,
                stdin,
                step,
                "state",
            )
        assert (io.getvalue(), io.position(), io.past_end) == (
            ref.output,
            ref.offset,
            ref.past_end,
        ), (code, stdin, step, "io")
        if halted:
            break
        machine.step()
        ref.step()
    else:
        raise AssertionError(("transition bound", code))
    before = machine.snapshot()
    machine.step()
    ref.step()
    assert machine.snapshot() == before
    assert native_view(machine) == reference_view(ref)
    return ref


ATOMS = ["s", "k", "i", "v", "c", "d", "e", "@", "|", "r", ".A", ".\n", "?A", "?\n"]


@pytest.mark.parametrize("head", ATOMS)
def test_every_term_through_two_applications(head):
    terms = [head] + ["`" + head + b for b in ATOMS]
    terms += [
        shape
        for b, c in itertools.product(ATOMS, repeat=2)
        for shape in ("``" + head + b + c, "`" + head + "`" + b + c)
    ]
    for code, stdin in itertools.product(terms, ("", "A", "A\n")):
        check(code, stdin)


def test_continuations_delay_exit_and_character_controls():
    selector = "``?Q``s``si`k`d`.Xi`kvi"
    for prefix, stdin in itertools.product(
        ("", "``k`@i", "``k`@i``k`@i"), ("", "Q", "R", "Q\n")
    ):
        check(prefix + selector, stdin)
    for code in (
        "``d`.xi`.yi",
        "`cd",
        "```cdii",
        "``c``si`kv.A",
        "``k`.Ai`e.B",
        "```s`d`@|i`ci",
        "``cd``d`@|`cd",
    ):
        for stdin in ("", "Q", "ABC\n", "é🙂\n"):
            check(code, stdin)
    assert check("``d`.xi`.yi").output == "yx"
    assert check("``k`@i``k`@i" + selector, "Q").output == ""
    assert check("``k`@i" + selector, "Q").output == "X"
    assert check("``k`@i``k`@i``|ii", "Q").output == ""


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_independent_small_generated_truth_tables(n):
    for value in range(1 << (1 << n)):
        table = f"{value:0{1 << n}b}"
        check_generated(table)


def check_generated(table):
    n = len(table).bit_length() - 1
    code = unlambda(table)
    for row, answer in enumerate(table):
        reference = check(code, f"{row:0{n}b}", states=False)
        assert reference.output == answer
        assert reference.offset == n
        assert reference.past_end == 0


@pytest.mark.medium
@pytest.mark.parametrize(
    "table",
    five_input_sample()[::10]
    + [
        f"{value % 2 ** (2**n):0{2**n}b}"
        for n in (4, 6)
        for value in (0x6996, 0x1234ABCD5678EF01)
    ]
    + [f"{random.Random(seed).getrandbits(512):0512b}" for seed in (0, 1)],
)
def test_shared_generated_programs(table):
    check_generated(table)


@pytest.mark.parametrize(
    "source", ["", "`i", "ii", ".", "?", "z", "#comment", "``ii", "`k`"]
)
def test_syntax_is_checked_before_io(source):
    with pytest.raises(ValueError, match=r".+"):
        Reference(source)
    io = ScriptedIO("X")
    with pytest.raises(ValueError, match=r".+"):
        _Machine(source, io)
    assert io.position() == 0
    assert io.getvalue() == ""


def test_quoted_characters_whitespace_and_comments():
    for source in (
        "#skip\n`.Ai",
        "` .# i",
        "` .\n i",
        "` ?# i",
        "\t` i\n i #tail",
        "#head\n`d`.Ai#tail",
    ):
        check(source)


def test_a_loop_revisits_its_complete_state():
    reference = Reference("```sii``sii")
    machine = _Machine("```sii``sii", ScriptedIO(""))
    seen = {}
    for step in range(100):
        state = reference_view(reference)
        assert native_view(machine) == state
        if state in seen:
            break
        seen[state] = step
        reference.step()
        machine.step()
    else:
        raise AssertionError("silent SKI self-application did not revisit its state")
    assert not machine.halted
    assert reference.action is not None
    assert reference.output == ""
    assert step > seen[state]


def test_public_run_uses_character_io():
    from esolangs.interpreters.other.unlambda import run

    source = "```s`d`@|i`ci"
    reference = Reference(source, "A\né🙂")
    reference.run()
    io = ScriptedIO(reference.stdin)
    run(source, io=io)
    assert io.getvalue() == reference.output
    assert io.position() == reference.offset
    assert io.past_end == reference.past_end
