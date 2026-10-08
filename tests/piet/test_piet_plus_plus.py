"""Piet++ interpreter: the wiki's stated output and the settled conventions."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.piet_plus_plus import _COMMANDS, run
from esolangs.raster import Raster

_DELTA = {name: delta for delta, name in _COMMANDS.items()}
BLACK = (0, 0, 0)


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


def test_entry_point_shares_the_run() -> None:
    from esolangs.interpreters.stack_based import piet_plus_plus
    from esolangs.interpreters.stack_based.piet_plus_plus import __main__ as entry

    assert entry.run is piet_plus_plus.run
