"""Tests for the moar cheese :3 interpreter."""

import pytest

import esolangs
from esolangs.exceptions import ProgramError
from esolangs.languages.moar_cheese_3.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import run_until_halt_or_cycle


def _out(code: str) -> str:
    io = ScriptedIO()
    run(code, io)
    return io.getvalue()


def test_the_xkcd_random_number() -> None:
    assert _out("(4)") == "4"


def test_hello_world() -> None:
    code = "(H) (e) (l) (l) (o) (,) ( ) (w) (o) (r) (l) (d) (!)"
    assert _out(code) == "Hello, world!"


def test_the_infinite_loop_revisits_its_state() -> None:
    assert run_until_halt_or_cycle(_Machine("l(l) l", ScriptedIO())) is False


@pytest.mark.parametrize(
    ("data", "rules"),
    [("110", ["10", "0", ""])],
)
def test_the_cyclic_tag_encoding(data: str, rules: list[str]) -> None:
    # The page's encoding: the data bits, then l(1(rule) () ... l) l.
    encoded = " ".join(f"1({' '.join(f'({b})' for b in r)}) ()" for r in rules)
    code = " ".join(f"({b})" for b in data) + f" l({encoded} l) l"
    machine = _Machine(code, ScriptedIO())
    queue, seen = data, []
    for _ in range(10_000):
        if machine.halted:
            break
        frame = machine.frames[-1] if machine.frames else None
        if frame and machine.bodies[frame[0]][frame[1]][0] == "deq":
            seen.append("".join(machine.queue))
        machine.step()
    expected = []
    for step in range(len(seen)):
        expected.append(queue)
        if queue:
            queue = queue[1:] + (rules[step % len(rules)] if queue[0] == "1" else "")
    assert seen == expected
    assert machine.halted
    assert not queue


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        # A redefinition inside a body takes effect at the next call; the
        # running body finishes its old code.
        ("a((x) a((y))) a a", "xy"),
        # Undefined instructions, and defined ones with empty bodies, do nothing.
        ("q a() a (z)", "z"),
        # A dequeued byte runs as an instruction.
        ("(a) (b) a((c) ()) () (d)", "cd"),
        ("  (a)   (b)  \n", "ab"),
        # A newline separates like a space, inside a body too.
        ("(a)\n(b)\nc(\n(c)\n( )) c", "abc "),
    ],
)
def test_rulings(code: str, expected: str) -> None:
    assert _out(code) == expected


def test_a_tail_call_loop_keeps_one_frame() -> None:
    machine = _Machine("(1) (1) (1) 1((1) ()) ()", ScriptedIO())
    depths = set()
    for _ in range(200):
        machine.step()
        depths.add(len(machine.frames))
    assert max(depths) <= 2


def test_nested_definitions_do_not_use_python_recursion() -> None:
    depth = 1200
    code = "a(" * depth + "(x)" + ")" * depth + " a" * depth
    assert _out(code) == "x"


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("(0)(1)", "no space"),
        ("(()", "bad enqueue"),
        ("(é)", "printable"),
        # A newline is a separator, never an enqueued byte.
        ("(\n)", "bad enqueue"),
    ],
)
def test_errors(code: str, message: str) -> None:
    with pytest.raises(ProgramError, match=message):
        _out(code)


@pytest.mark.medium
def test_a_balanced_program_folds_between_instructions() -> None:
    """Every row still computes once ``balance`` breaks the one line."""
    table = "0110100110010111"
    artifact = esolangs.generate("moar cheese :3", table, balance=True)
    assert "\n" in str(artifact.source)
    rows = [
        esolangs.evaluate(
            "moar cheese :3", artifact, [r >> 3 & 1, r >> 2 & 1, r >> 1 & 1, r & 1]
        ).answer
        for r in range(16)
    ]
    assert "".join(rows) == table
