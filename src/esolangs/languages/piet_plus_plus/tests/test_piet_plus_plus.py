"""Piet++ interpreter: the wiki's stated output and the settled conventions."""

import pytest

from esolangs.languages.piet_plus_plus.interpreter import (
    _COMMANDS,
    _advance,
    _Machine,
    _NeedInputError,
    run,
)
from esolangs.raster import Raster
from esolangs.runtime.io import ScriptedIO

_DELTA = {name: delta for delta, name in _COMMANDS.items()}
BLACK = (0, 0, 0)


class _EventIO(ScriptedIO):
    """A ``ScriptedIO`` that logs each read and write in order."""

    def __init__(self, stdin: str = "") -> None:
        super().__init__(stdin)
        self.events: list[str] = []

    def input_char(self, prompt: str = "Input: ") -> int:
        self.events.append("read")
        return super().input_char(prompt)

    def input_token(self, prompt: str = "Input: ") -> str:
        self.events.append("read")
        return super().input_token(prompt)

    def _write(self, value: object) -> None:
        self.events.append(f"write:{value}")
        super()._write(value)


def strip(*commands: tuple[str, int]) -> Raster:
    """An L-shaped start, a block per command, then a vertical end block.

    A command's size is that of the block it leaves: what Push Int pushes.
    """
    level = [1, 0, 1]

    def paint() -> tuple[int, int, int]:
        # Green stays at levels 1 and 2, so a colour is never black or white.
        return level[0] * 85, (level[1] + 1) * 85, level[2] * 85

    def advance(name: str) -> None:
        level[:] = [
            (v + d) % m for v, d, m in zip(level, _DELTA[name], (4, 2, 4), strict=True)
        ]

    start = paint()
    advance("pop")  # the start block's pop runs on an empty stack
    cells: list[tuple[int, int, int]] = []
    for name, size in commands:
        cells += [paint()] * size
        advance(name)
    end = paint()
    rows = [[BLACK] * (len(cells) + 3) for _ in range(3)]
    rows[0][0] = rows[1][0] = rows[1][1] = start
    rows[1][2:-1] = cells
    for row in rows:
        row[-1] = end
    return Raster(tuple(map(tuple, rows)))


def execute(program: Raster, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(program, io)
    return io.getvalue()


def test_advance_is_pure_and_repeatable() -> None:
    """The transition is a function of its core and leaves it unchanged."""
    program = strip(
        ("push_int", 3), ("push_int", 4), ("multiply", 1), ("out_integer", 1)
    )
    machine = _Machine(program, ScriptedIO(""))
    core = machine.state
    writes_before = dict(core[7])
    first, first_effect = _advance(core)
    second, second_effect = _advance(core)
    assert first == second
    assert first_effect == second_effect
    assert core[3] == machine.state[3]
    assert dict(core[7]) == writes_before


def test_advance_returns_output_instead_of_writing() -> None:
    """``out`` reports an effect; the transition owns no port."""
    program = strip(
        ("push_int", 3), ("push_int", 4), ("multiply", 1), ("out_integer", 1)
    )
    io = ScriptedIO("")
    machine = _Machine(program, io)
    effect = None
    for _ in range(30):
        core, effect = _advance(machine.state)
        machine.state = core
        if effect:
            break
    assert effect == ("out", (12,), True)
    assert io.getvalue() == ""


def test_advance_requests_input_rather_than_reading() -> None:
    """An ``in`` command raises instead of touching the port."""
    program = strip(("in_character", 1), ("out_character", 1))
    io = ScriptedIO("A")
    machine = _Machine(program, io)

    def step_to_input() -> None:
        for _ in range(30):
            core, _effect = _advance(machine.state)
            machine.state = core

    with pytest.raises(_NeedInputError) as caught:
        step_to_input()
    assert caught.value.effects is None  # one command per step: no prefix
    assert io.getvalue() == ""
    assert io.position() == 0


def test_a_fault_is_rethrown_after_flushing_its_prefix() -> None:
    """The shell writes the carried prefix, then re-raises the cause."""
    from types import MappingProxyType

    from esolangs.languages.piet_plus_plus.interpreter import _FaultError

    program = strip(("push_int", 1), ("out_integer", 1))
    machine = _Machine(program, ScriptedIO(""))
    # An empty image is malformed; the traversal raises, and the shell must
    # surface that cause after writing the (empty) prefix exactly once.
    machine.state = ((0, 0), 0, -1, (), (), False, (), MappingProxyType({}))
    with pytest.raises(IndexError):
        machine.step()
    with pytest.raises(_FaultError) as caught:
        _advance(machine.state)
    assert isinstance(caught.value.cause, IndexError)
    assert caught.value.effects is None


def test_an_input_step_reads_before_the_write_it_feeds() -> None:
    """The retry kernel never defers or duplicates the output."""
    program = strip(("in_character", 1), ("out_character", 1))
    io = _EventIO("A")
    run(program, io)
    assert io.events == ["read", "write:A"]
    assert io.getvalue() == "A"


def test_an_input_step_at_eof_writes_nothing_and_keeps_going() -> None:
    """EOF is ignored, and no pending output is dropped or repeated."""
    program = strip(("in_character", 1), ("out_character", 1), ("out_character", 1))
    io = _EventIO("")
    run(program, io)
    assert io.getvalue() == ""
    assert io.events == ["read"]


def test_xkcd_random_number_prints_four() -> None:
    on, off = (0, 85, 85), (0, 170, 85)
    dim, mid, hot = (170, 255, 85), (255, 85, 85), (255, 85, 255)
    rows = (
        (on, dim, dim, mid, hot, BLACK, off),
        (BLACK, dim, dim, BLACK, hot, hot, off),
        (BLACK, BLACK, BLACK, BLACK, BLACK, BLACK, off),
    )
    assert execute(Raster(rows)) == "4"


def test_deltas_cover_all_thirty_two_commands() -> None:
    assert len(_COMMANDS) == len(set(_COMMANDS.values())) == 32


def test_arithmetic_and_output() -> None:
    program = strip(
        ("push_int", 3), ("push_int", 4), ("multiply", 1), ("out_integer", 1)
    )
    assert execute(program) == "12"


def test_invalid_commands_are_ignored_without_popping() -> None:
    # Add on one operand, Divide by zero, Negate on a stack: all no-ops.
    program = strip(
        ("push_int", 5),
        ("add", 1),
        ("push_int", 1),
        ("push_int", 1),
        ("subtract", 1),
        ("divide", 1),
        ("push_stack", 1),
        ("negate", 1),
        ("pop", 1),
        ("pop", 1),
        ("out_integer", 1),
    )
    assert execute(program) == "5"


def test_add_keeps_stack_order() -> None:
    program = strip(
        ("push_stack", 1),
        ("down", 1),
        ("push_int", 1),
        ("push_int", 2),
        ("up", 1),
        ("push_int", 7),
        ("add", 1),
        ("out_integer", 1),
    )
    # 7 joins the top of [1, 2]; Out prints a stack's elements top first.
    assert execute(program) == "721"


ZEROS = (("push_int", 1), ("push_int", 1), ("subtract", 1), ("dup", 1))


def test_read_pops_x_and_offsets_from_the_codel_entered() -> None:
    program = strip(*ZEROS, ("read", 1), ("out_integer", 1))
    red, green, blue = program.rows[1][7]
    assert execute(program) == str(red << 16 | green << 8 | blue)


def test_write_black_lands_at_once_and_halts() -> None:
    program = strip(
        *ZEROS, ("dup", 1), ("write", 1), ("push_int", 1), ("out_integer", 1)
    )
    assert execute(program) == ""


@pytest.mark.parametrize("op", ["roll", "roll_context", "pointer", "toggle"])
def test_empty_stack_commands_do_nothing(op: str) -> None:
    assert execute(strip((op, 1), ("push_int", 2), ("out_integer", 1))) == "2"


PUSH = "push_int"
OUT = ("out_integer", 1)
MINUS_ONE = (*ZEROS[:3], (PUSH, 1), ("subtract", 1))
UNDER = (("push_stack", 1), ("down", 1), (PUSH, 5), ("up", 1))
INNER = ((PUSH, 1), ("push_stack", 1), ("down", 1), (PUSH, 2), ("up", 1))


@pytest.mark.parametrize(
    ("commands", "stdin", "expected"),
    [
        ([(PUSH, 3), ("dup", 1), ("add", 1), OUT], "", "6"),
        ([*UNDER, ("size", 1), OUT], "", "1"),
        ([(PUSH, 3), ("size", 1), OUT], "", "-1"),
        (
            [(PUSH, 1), (PUSH, 2), (PUSH, 3), (PUSH, 3), (PUSH, 1), ("roll", 1)]
            + [OUT] * 3,
            "",
            "213",
        ),
        ([*INNER, (PUSH, 2), (PUSH, 1), ("roll_context", 1), OUT, OUT], "", "12"),
        (
            [(PUSH, 1), (PUSH, 5), (PUSH, 1), ("roll_context", 1), OUT, OUT, OUT],
            "",
            "151",
        ),
        (
            [
                ("push_stack", 1),
                ("down", 1),
                (PUSH, 4),
                ("push_up", 1),
                ("up", 1),
                ("down", 1),
                OUT,
            ],
            "",
            "4",
        ),
        (
            [("push_stack", 1), (PUSH, 4), ("push_down", 1), ("pull_up", 1), OUT],
            "",
            "4",
        ),
        ([("push_stack", 1), ("down", 1), ("depth", 1), OUT], "", "1"),
        ([(PUSH, 7), (PUSH, 2), ("divide", 1), OUT], "", "3"),
        ([(PUSH, 7), (PUSH, 2), ("mod", 1), OUT], "", "1"),
        ([(PUSH, 7), (PUSH, 2), ("greater", 1), OUT], "", "1"),
        ([(PUSH, 7), (PUSH, 2), ("lesser", 1), OUT], "", "0"),
        ([(PUSH, 7), (PUSH, 7), ("equal", 1), OUT], "", "1"),
        ([(PUSH, 7), ("negate", 1), OUT], "", "-7"),
        ([(PUSH, 7), ("not", 1), OUT], "", "0"),
        (
            [
                (PUSH, 4),
                ("pointer", 1),
                (PUSH, 3),
                ("toggle", 1),
                (PUSH, 2),
                ("toggle", 1),
                (PUSH, 6),
                OUT,
            ],
            "",
            "6",
        ),
        ([("in_integer", 1), OUT], "42\n", "42"),
        ([("in_integer", 1), OUT, ("in_integer", 1), OUT], "x 7", "7"),
        ([("in_character", 1), ("out_character", 1)], "A", "A"),
        ([*MINUS_ONE, ("out_character", 1), ("in_character", 1), OUT], "", ""),
        ([(PUSH, 9), ("dup", 1), ("read", 1), OUT], "", "9"),
        ([(PUSH, 9), ("dup", 1), ("dup", 1), ("write", 1), OUT, OUT, OUT], "", "999"),
        (
            [*MINUS_ONE, ("dup", 1), ("dup", 1), ("write", 1), OUT, OUT, OUT],
            "",
            "-1-1-1",
        ),
    ],
)
def test_commands(commands: list[tuple[str, int]], stdin: str, expected: str) -> None:
    assert execute(strip(*commands), stdin) == expected


def test_white_codels_slide_without_running_a_command() -> None:
    a, b, c, end = (85, 85, 85), (170, 85, 85), (0, 85, 0), (85, 170, 170)
    white = (255, 255, 255)
    # A pushes 3 on leaving for B; the slide into C runs nothing; C prints.
    rows = (
        (a, BLACK, BLACK, BLACK, BLACK, end),
        (a, a, b, white, c, end),
        (BLACK, BLACK, BLACK, BLACK, BLACK, end),
    )
    assert execute(Raster(rows)) == "3"


def test_a_black_start_halts_at_once() -> None:
    assert execute(Raster(((BLACK, BLACK),))) == ""


def test_entry_point_executes_a_generated_program(tmp_path) -> None:
    import subprocess
    import sys

    import esolangs

    program = esolangs.generate("Piet++", "01", scale=1)
    path = tmp_path / "identity.png"
    path.write_bytes(program.to_png())
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "esolangs.languages.piet_plus_plus.interpreter",
            str(path),
        ],
        input=b"1\n",
        capture_output=True,
        timeout=10,
        check=True,
    )
    assert result.stdout == b"Input: 1"


@pytest.mark.parametrize("scale", [1, 2, 3])
@pytest.mark.parametrize("bit", [0, 1])
def test_enlarged_generated_programs_detect_their_scale(scale: int, bit: int) -> None:
    import esolangs
    from esolangs.languages.piet_plus_plus.generator import LANGUAGE

    source = esolangs.generate(LANGUAGE.name, "01", scale=scale)
    assert esolangs.run(LANGUAGE.name, source, stdin=f"{bit}\n") == str(bit)
