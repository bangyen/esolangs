"""Fish instruction semantics."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.fish import _Machine, run
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.randomness import FirstDraw


def _run(source: str, stdin: str = "", rng: object = None) -> str:
    io = ScriptedIO(stdin)
    run(source.splitlines(), io, rng=rng)
    return io.getvalue()


def test_literals_arithmetic_comparison_and_output() -> None:
    assert _run("23+n;") == "5"
    assert _run("53-n;") == "2"
    assert _run("23*n;") == "6"
    assert _run("53%n;") == "2"
    assert _run("94,n;") == "2.25"
    assert _run("23(n;") == "1"
    assert _run("23)n;") == "0"
    assert _run("22=n;") == "1"
    assert _run("'iH'oo;") == "Hi"
    assert _run('"iH"oo;') == "Hi"


def test_input_returns_minus_one_at_eof() -> None:
    assert _run("iin;", "A\n") == "-1"


def test_stack_stack_register_and_rotations() -> None:
    assert _run("1233[r]rnnn;") == "321"
    assert _run("12&~&n;") == "2"
    assert _run("123}nnn;") == "213"
    assert _run("123{nnn;") == "132"
    assert _run("1:nn;") == "11"
    assert _run("12$nn;") == "12"
    assert _run("123@nnn;") == "213"
    assert _run("12lnnn;") == "221"
    assert _run("0[]ln;") == "0"
    assert _run("12]ln;") == "0"
    assert _run("1232[]nnn;") == "321"


def test_get_put_and_negative_storage() -> None:
    assert _run("'A'01p01go;") == "A"
    machine = _Machine(["'A'01-01-p;"], ScriptedIO(""))
    while not machine.halted:
        machine.step()
    assert machine.cells[(-1, -1)] == ord("A")
    machine = _Machine(["'A'99p;"], ScriptedIO(""))
    while not machine.halted:
        machine.step()
    assert (machine.width, machine.height) == (10, 10)


def test_movement_mirrors_jump_and_trampolines() -> None:
    assert _run("1!9n;") == "1"
    assert _run("0?9n;") == "9"
    assert _run("1?91n;") == "1"
    assert _run("20.9n;") == "9"
    assert _run("x;", rng=FirstDraw(0)) == ""
    machine = _Machine(["/ ", " ;"], ScriptedIO(""))
    machine.step()
    assert machine.ip == (1, 0, 0, -1)

    headings = {
        ">": (1, 0),
        "<": (-1, 0),
        "^": (0, -1),
        "v": (0, 1),
    }
    for command, heading in headings.items():
        machine = _Machine([command], ScriptedIO(""))
        machine.step()
        assert (machine.dx, machine.dy) == heading

    for command, start, expected in (
        ("/", (1, 0), (0, -1)),
        ("\\", (1, 0), (0, 1)),
        ("|", (1, 0), (-1, 0)),
        ("_", (0, 1), (0, -1)),
        ("#", (1, 0), (-1, 0)),
    ):
        machine = _Machine([command], ScriptedIO(""))
        machine.dx, machine.dy = start
        machine.step()
        assert (machine.dx, machine.dy) == expected


def test_branching_protocol_covers_random_input_plain_and_halted_states() -> None:
    random = _Machine(["x"], ScriptedIO(""))
    start = random.branching_snapshot()
    assert len(random.branching_successors(start, 10) or ()) == 4
    reading = _Machine(["i"], ScriptedIO(""))
    assert reading.branching_successors(reading.branching_snapshot(), 10) is None
    plain = _Machine(["1"], ScriptedIO(""))
    assert len(plain.branching_successors(plain.branching_snapshot(), 10) or ()) == 1
    halted = _Machine([";"], ScriptedIO(""))
    halted.step()
    final = halted.branching_snapshot()
    assert halted.branching_halted(final)
    assert halted.branching_successors(final, 10) == (final,)
    halted.step()


def test_errors_are_fishy() -> None:
    for source in ("~;", "10,;", "10%;", "};", "{;", "2[;", "z;"):
        with pytest.raises(HaltError, match="fishy"):
            _run(source)
    fractional = _Machine(["p"], ScriptedIO(""))
    fractional.stacks[-1].extend((2.5, 0, 0))
    with pytest.raises(HaltError, match="fishy"):
        fractional.step()


def test_a_missing_codebox_cell_is_a_nop() -> None:
    machine = _Machine(["v", ""], ScriptedIO(""))
    machine.step()
    machine.step()
    assert machine.ip == (0, 0, 0, 1)


def test_empty_program_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        run([], ScriptedIO(""))
