"""Execution tests for the Whitespace interpreter."""

import pytest

from esolangs.exceptions import HaltError, InputExhaustedError, ProgramError
from esolangs.languages.whitespace.interpreter import _advance, run
from esolangs.runtime.io import IO, ScriptedIO
from tests.interpreters.runner import run_program

S, T, L = " ", "\t", "\n"


def push(value: int) -> str:
    """Assemble a push of ``value``."""
    sign = T if value < 0 else S
    digits = "".join(T if bit == "1" else S for bit in f"{abs(value):b}")
    return S + S + sign + digits + L


def number(value: int) -> str:
    """Assemble a bare number argument (copy, slide)."""
    sign = T if value < 0 else S
    digits = "".join(T if bit == "1" else S for bit in f"{abs(value):b}")
    return sign + digits + L


SWAP, DISCARD = S + L + T, S + L + L
ADD, SUB, MUL, DIV, MOD = (
    T + S + S + S,
    T + S + S + T,
    T + S + S + L,
    T + S + T + S,
    T + S + T + T,
)
STORE, RETRIEVE = T + T + S, T + T + T
OUT_CHAR, OUT_NUM = T + L + S + S, T + L + S + T
END = L + L + L


def copy(depth: int) -> str:
    return S + T + S + number(depth)


def slide(depth: int) -> str:
    return S + T + L + number(depth)


def jump(label: str) -> str:
    return L + S + L + label + L


RETURN = L + T + L


def wrun(program: str, stdin: str = "") -> str:
    return run_program(run, program, stdin)


def test_malformed_programs_are_rejected() -> None:
    with pytest.raises(ProgramError, match="ends inside"):
        run("   ", IO())  # ends inside the push
    with pytest.raises(ProgramError, match="empty"):
        run("", IO())
    # An unknown arithmetic subcommand is malformed, not a crash: the bare
    # dict lookup let this escape as KeyError until the fuzzer hit it.
    with pytest.raises(ProgramError, match="no command"):
        run(T + S + L + T, IO())
    # A flow command whose third token is not ``line feed`` is malformed too.
    with pytest.raises(ProgramError, match="flow command"):
        run(L + L + S, IO())


def test_a_pop_from_an_empty_stack_halts() -> None:
    for program in (ADD, SWAP, DISCARD, STORE, RETRIEVE, OUT_NUM, OUT_CHAR):
        with pytest.raises(HaltError, match="empty"):
            run(program + END, IO())


def test_slide_on_an_empty_stack_halts() -> None:
    with pytest.raises(HaltError, match="slide"):
        run(slide(1) + END, IO())


def test_a_read_with_no_input_halts() -> None:
    # ``_advance`` is called with no value supplied; the shell's read raises
    # EOF before reaching this guard, so this is a direct-call contract.
    for kind in ("read_char", "read_num"):
        with pytest.raises(HaltError, match="input left"):
            _advance((0, (0,), (), (), False), [(kind, 0)], {})


def test_advancing_a_done_state_is_a_no_op() -> None:
    done = (0, (), (), (), True)
    assert _advance(done, [], {}) == (done, None)


@pytest.mark.parametrize(
    ("program", "message"),
    [
        (push(1) + push(0) + DIV + END, "zero"),
        (push(1) + push(0) + MOD + END, "zero"),
        (push(1) + copy(5) + END, "copy"),
        (RETURN + END, "return"),
        (jump(T) + END, "undefined label"),
    ],
)
def test_invalid_operations_halt(program: str, message: str) -> None:
    with pytest.raises(HaltError, match=message):
        run(program, IO())


def test_the_wiki_cat_program_echoes_until_eof() -> None:
    """The page's Cat program loops on a read, so EOF ends it, after the echo."""
    cat = (
        "\n   \n   \t\n\t\n\t    \t\n\t\t\t\t\n     \t\n\t\t\t\n\t \t\n"
        "\n \n \n\n  \t\n\n\n\n"
    )
    io = ScriptedIO("ab\n")
    with pytest.raises(InputExhaustedError):
        run(cat, io)
    assert io.getvalue() == "ab\n"


def test_signed_division_and_remainder_match_reference() -> None:
    for left, right in ((-7, 3), (7, -3), (-7, -3), (-(2**80) - 1, 7)):
        for command, value in zip((DIV, MOD), divmod(left, right), strict=True):
            assert wrun(push(left) + push(right) + command + OUT_NUM + END) == str(
                value
            )


def test_first_duplicate_label_wins() -> None:
    mark = L + S + S + T + L
    for transfer, stop, expected in (
        (jump(T), END, "1"),
        (L + S + T + T + L, RETURN, "19"),
    ):
        first = mark + push(1) + OUT_NUM + stop
        second = mark + push(2) + OUT_NUM + stop
        assert wrun(transfer + push(9) + OUT_NUM + END + first + second) == expected


def test_untaken_branches_skip_missing_label_lookup() -> None:
    for branch, value in ((L + T + S, 1), (L + T + T, 0)):
        assert wrun(push(value) + branch + T + L + push(7) + OUT_NUM + END) == "7"
        with pytest.raises(HaltError, match="undefined label"):
            wrun(push(-1 if value == 0 else 0) + branch + T + L + END)
        with pytest.raises(HaltError, match="empty"):
            wrun(branch + T + L + END)
