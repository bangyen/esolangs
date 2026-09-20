"""Execution tests for the Whitespace classic."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.stack_based.whitespace import _advance, run
from tests.interpreters.runner import run_program

S, T, L = " ", "\t", "\n"


def push(value: int) -> str:
    """Assemble a push of ``value``."""
    sign = T if value < 0 else S
    digits = "".join(T if bit == "1" else S for bit in bin(abs(value))[2:])
    return S + S + sign + digits + L


def number(value: int) -> str:
    """Assemble a bare number argument (copy, slide)."""
    sign = T if value < 0 else S
    digits = "".join(T if bit == "1" else S for bit in bin(abs(value))[2:])
    return sign + digits + L


DUP, SWAP, DISCARD = S + L + S, S + L + T, S + L + L
ADD, SUB, MUL, DIV, MOD = (
    T + S + S + S,
    T + S + S + T,
    T + S + S + L,
    T + S + T + S,
    T + S + T + T,
)
STORE, RETRIEVE = T + T + S, T + T + T
OUT_CHAR, OUT_NUM = T + L + S + S, T + L + S + T
READ_CHAR, READ_NUM = T + L + T + S, T + L + T + T
END = L + L + L


def copy(depth: int) -> str:
    return S + T + S + number(depth)


def slide(depth: int) -> str:
    return S + T + L + number(depth)


def mark(label: str) -> str:
    return L + S + S + label + L


def call(label: str) -> str:
    return L + S + T + label + L


def jump(label: str) -> str:
    return L + S + L + label + L


def jump_if_zero(label: str) -> str:
    return L + T + S + label + L


def jump_if_negative(label: str) -> str:
    return L + T + T + label + L


RETURN = L + T + L


def wrun(program: str, stdin: str = "") -> str:
    return run_program(run, program, stdin)


def test_push_and_both_outputs() -> None:
    assert wrun(push(65) + OUT_CHAR + END) == "A"
    assert wrun(push(-3) + OUT_NUM + END) == "-3"


def test_arithmetic_takes_the_first_pushed_as_left() -> None:
    assert wrun(push(7) + push(2) + SUB + OUT_NUM + END) == "5"
    assert wrun(push(6) + push(7) + MUL + OUT_NUM + END) == "42"
    # -7 truncates toward zero: -3, with remainder -1.
    assert wrun(push(-7) + push(2) + DIV + OUT_NUM + END) == "-3"
    assert wrun(push(-7) + push(2) + MOD + OUT_NUM + END) == "-1"
    assert wrun(push(4) + push(5) + ADD + OUT_NUM + END) == "9"


def test_stack_manipulation() -> None:
    assert wrun(push(3) + DUP + ADD + push(4) + ADD + OUT_NUM + END) == "10"
    assert wrun(push(1) + push(2) + SWAP + OUT_NUM + push(0) + END) == "1"
    assert wrun(push(9) + DISCARD + push(4) + OUT_NUM + END) == "4"
    # copy the second item, then slide one, keeping the copied 7 on top.
    assert wrun(push(7) + push(8) + copy(1) + slide(1) + OUT_NUM + END) == "7"


def test_heap_store_and_retrieve() -> None:
    program = (
        push(0)
        + READ_CHAR
        + push(0)
        + RETRIEVE
        + OUT_CHAR
        + push(1)
        + push(42)
        + STORE
        + push(1)
        + RETRIEVE
        + OUT_NUM
        + END
    )
    assert wrun(program, "Z\n") == "Z42"


def test_flow_control_jumps_calls_and_returns() -> None:
    label = S

    def branch(value: int, op: str) -> str:
        return wrun(push(value) + op(label) + push(66) + OUT_CHAR + mark(label) + END)

    # an unconditional jump skips the output.
    assert wrun(jump(label) + push(65) + OUT_CHAR + mark(label) + END) == ""
    # jz branches on zero, jn on negative; the other value falls through.
    assert branch(0, jump_if_zero) == ""
    assert branch(1, jump_if_zero) == "B"
    assert branch(-1, jump_if_negative) == ""
    assert branch(1, jump_if_negative) == "B"
    # call reaches the mark and returns to the caller's next command.
    called = push(68) + call(label) + OUT_CHAR + END + mark(label) + RETURN
    assert wrun(called) == "D"


def test_read_number_stores_it() -> None:
    program = push(0) + READ_NUM + push(0) + RETRIEVE + OUT_NUM + END
    assert wrun(program, "12\n") == "12"


def test_malformed_programs_are_rejected() -> None:
    with pytest.raises(ValueError, match="ends inside"):
        run("   ", IO())  # ends inside the push
    with pytest.raises(ValueError, match="empty"):
        run("", IO())
    # An unknown arithmetic subcommand is malformed, not a crash: the bare
    # dict lookup let this escape as KeyError until the fuzzer hit it.
    with pytest.raises(ValueError, match="no command"):
        run(T + S + L + T, IO())
    # A flow command whose third token is not ``line feed`` is malformed too.
    with pytest.raises(ValueError, match="flow command"):
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
