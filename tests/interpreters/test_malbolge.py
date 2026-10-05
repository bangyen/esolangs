"""Execution tests for the interpreter-only Malbolge classic."""

import pytest

from esolangs.interpreters.other.malbolge import _EOF, _advance, _load, _op, run
from tests.interpreters.runner import run_program

#: Kamila Szewczyk's "Hello, world." -- the reference output is lowercase.
HELLO = (
    "(=<`#9]~6ZY327Uv4-QsqpMn&+Ij\"'E%e{Ab~w=_:]Kw%o44Uqp0/"
    "Q?xNvL:`H%c#DD2^WV>gY;dts76qKJImZkj"
)


def test_a_known_program_prints_its_greeting() -> None:
    """The reference Hello World is the end-to-end check."""
    assert run_program(run, HELLO) == "Hello, world."


def test_a_non_instruction_source_character_is_rejected() -> None:
    # 'x' at cell 0 deciphers to something outside the eight instructions.
    assert _op(ord("x"), 0) not in "ji*p</vo"
    with pytest.raises(ValueError, match="does not decipher"):
        _load("x")


def test_a_halted_state_advances_to_itself() -> None:
    done = (0, 0, 0, True)
    assert _advance(done, _load("Q")) == (done, (), None)


def test_a_read_with_no_input_is_the_eof_value() -> None:
    # 'q' at cell 4 deciphers to '/', the input instruction; an absent input
    # leaves the EOF sentinel in ``a`` rather than raising.
    memory = [ord("q")] * 8
    (a, _c, _d, halted), _writes, _effect = _advance((0, 4, 0, False), memory)
    assert a == _EOF
    assert not halted
