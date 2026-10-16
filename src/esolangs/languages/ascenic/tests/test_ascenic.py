"""Tests for the Ascenic interpreter."""

import random

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.ascenic.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from esolangs.runtime.randomness import Seeded

#: The wiki's Hello world as (SUB, ADD, PRINT, POP) arguments per character;
#: its 52 lines are 35KB of ``s``.
_HELLO = (
    (1, 73, 74, 75),
    (76, 177, 178, 179),
    (180, 288, 290, 291),
    (292, 400, 402, 403),
    (404, 515, 516, 517),
    (518, 562, 564, 565),
    (566, 598, 600, 601),
    (602, 689, 690, 691),
    (692, 803, 804, 805),
    (806, 920, 922, 923),
    (924, 1032, 1034, 1035),
    (1036, 1136, 1138, 1139),
    (1140, 1173, 1174, 1175),
)


def _program(*lines: tuple[int, int]) -> str:
    return "\n".join("A" * op + "s" * arg for op, arg in lines)


def _run(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def test_wiki_hello_world() -> None:
    lines = [line for args in _HELLO for line in zip((5, 4, 1, 10), args, strict=True)]
    assert _run(_program(*lines)) == "Hello, World!"


def test_wiki_a_plus_b() -> None:
    code = "AAs\nAAsss\nAAAAAAAAAAAAAAAAssss\nAsssss"
    assert _run(code, "40\n2\n") == "42"
    assert _run(code, "3 -5") == "-2"


def test_an_empty_stack_top_is_a_fresh_zero() -> None:
    # SUB 1 then PRINT: the wiki's Hello world relies on it.
    assert _run(_program((5, 1), (1, 3))) == "-1"
    assert _run(_program((10, 1), (9, 2), (1, 3))) == "0"  # POP, SWAP on empty


def test_jumps_land_arg_lines_from_the_jump() -> None:
    skip = _program((3, 1), (12, 2), (1, 3), (1, 5))  # JMPF 2 skips one PRINT
    assert _run(skip) == "1"
    assert _run(_program((3, 1), (12, 2), (1, 5))) == ""  # past the end halts
    assert _run(_program((12, 1), (1, 3))) == "0"  # not taken on 0
    assert _run(_program((11, 1), (1, 3))) == "0"


def test_a_taken_jmpb_raises() -> None:
    with pytest.raises(HaltError):
        _run(_program((3, 1), (11, 2)))


def test_comparisons_push_without_popping() -> None:
    # PUSH 5, LT 6 -> [5, 1]; ADDS -> 6; TL with 6 over 0 -> 0.
    code = _program((3, 5), (13, 6), (16, 7), (14, 8), (1, 9), (10, 10), (1, 11))
    assert _run(code) == "06"


def test_arithmetic_floors_and_orders_operands() -> None:
    # 3 - 10 by SUBS is b - a; floor division and modulo follow Python.
    assert _run(_program((3, 3), (3, 10), (17, 11), (1, 13))) == "-7"
    assert _run(_program((5, 7), (7, 9), (1, 11))) == "-1"  # -7 // 9
    assert _run(_program((5, 7), (8, 9), (1, 11))) == "2"  # -7 % 9
    assert _run(_program((3, 3), (19, 4), (1, 5))) == "0"  # 0 / 3 by DIVS
    assert _run(_program((3, 3), (3, 4), (10, 5), (9, 6), (19, 7), (1, 9))) == "0"


def test_io_follows_the_argument_parity() -> None:
    assert _run(_program((2, 2), (1, 3)), "A") == "65"
    assert _run(_program((3, 65), (1, 66))) == "A"
    with pytest.raises(HaltError):
        _run(_program((5, 1), (1, 2)))


def test_rnd_draws_zero_and_one() -> None:
    code = _program((15, 1), (1, 3))
    seen = set()
    for seed in range(20):
        io = ScriptedIO()
        run(code, io, Seeded(seed))
        seen.add(io.getvalue())
    assert seen == {"0", "1"}


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("As\nAs", "does not exceed"),
        ("A" * 20 + "s", "opcode 20"),
        ("AsB", "not A"),
        ("A", "not A"),
    ],
)
def test_malformed_programs_raise(code: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _run(code)


def test_every_run_halts_within_its_line_count() -> None:
    rng = random.Random(5)
    for _ in range(300):
        args = sorted(rng.sample(range(1, 40), 12))
        code = _program(*((rng.choice((0, 3, 4, 9, 10, 12, 13, 16)), a) for a in args))
        machine = _Machine(code, ScriptedIO())
        steps = 0
        while not machine.halted:
            machine.step()
            steps += 1
        assert steps <= 12


def test_a_number_past_the_host_digit_cap_is_a_limit() -> None:
    """Reported as ProgramError (a load error) though the program is valid."""
    import esolangs
    from esolangs.exceptions import InterpreterLimitError

    with pytest.raises(InterpreterLimitError, match="4300"):
        esolangs.run("Ascenic", "AAsss\nAsssss", stdin="9" * 5000 + "\n")
