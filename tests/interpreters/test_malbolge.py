"""Execution tests for the interpreter-only Malbolge classic."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.malbolge import (
    _EOF,
    _WORDS,
    _advance,
    _crazy,
    _load,
    _Machine,
    _op,
    run,
)
from tests.interpreters.runner import run_program

#: Kamila Szewczyk's "Hello, world." -- the reference output is lowercase.
HELLO = (
    "(=<`#9]~6ZY327Uv4-QsqpMn&+Ij\"'E%e{Ab~w=_:]Kw%o44Uqp0/"
    "Q?xNvL:`H%c#DD2^WV>gY;dts76qKJImZkj"
)

#: The wiki's cat, which copies input and then loops forever at EOF.
CAT = '(=BA#9"=<;:3y7x54-21q/p-,+*)"!h%B0/.\n~P<\n<:(8&\n66#"!~}|{zyxwvu\ngJ%'


def test_the_crazy_operation_at_zero() -> None:
    # Each of the five base-9 di-trits maps 0 to 4, over places 9**0..9**4.
    assert _crazy(0, 0) == 4 * sum(9**place for place in range(5))


def test_decipherment_and_halt() -> None:
    # 'Q' at cell 0 deciphers to 'v', the halt instruction.
    assert _op(ord("Q"), 0) == "v"
    assert _op(0, 0) is None  # not a graphic cell: execution stops


def test_memory_is_filled_and_sized() -> None:
    memory = _load("Q")
    assert len(memory) == _WORDS
    assert memory[0] == ord("Q")
    assert memory[1] == _crazy(memory[0], 0)
    assert memory[2] == _crazy(memory[1], memory[0])


def test_each_machine_receives_fresh_memory() -> None:
    first = _load("Q")
    first[0] = 0
    assert _load("Q")[0] == ord("Q")


def test_a_known_program_prints_its_greeting() -> None:
    """The reference Hello World is the end-to-end check."""
    assert run_program(run, HELLO) == "Hello, world."


def test_a_one_character_program_halts_immediately() -> None:
    assert run_program(run, "Q") == ""


def test_input_is_one_line_per_character() -> None:
    # One line per character is the package's stdin convention; bound the
    # run, since the wiki's own cat does not stop at EOF.
    io = ScriptedIO("H\ni\n!\n")
    machine = _Machine(CAT, io)
    for _ in range(200):
        if machine.halted:
            break
        machine.step()
    assert io.getvalue().startswith("Hi!")


def test_a_non_instruction_source_character_is_rejected() -> None:
    # 'x' at cell 0 deciphers to something outside the eight instructions.
    assert _op(ord("x"), 0) not in "ji*p</vo"
    with pytest.raises(ValueError, match="does not decipher"):
        _load("x")


def test_an_empty_program_halts_at_once() -> None:
    assert run_program(run, " ") == ""


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


def test_a_non_graphic_rewrite_skips_the_encipherment() -> None:
    # The apostrophe is the cell that deciphers to '*': rotating 39 gives 13,
    # below the graphic range, so the cell keeps the value and is not
    # re-enciphered.
    (a, _c, _d, halted), writes, _effect = _advance((0, 0, 0, False), [ord("'")] * 8)
    assert not halted
    assert a == 13
    assert writes == ((0, 13),)
