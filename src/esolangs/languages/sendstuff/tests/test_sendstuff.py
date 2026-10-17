"""Tests for the SendStuff interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.sendstuff.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.contract import CycleContract, EmptyProgramContract

#: The wiki's Hello world: its closing parentheses are left off, so each
#: ``Add`` is a child of the one before and the deltas accumulate.
HELLO = """
 >(Add      72 >(Output)
 >(Add      29 >(Output)
 >(Add      7  >(Output)
               >(Output)
 >(Add      3  >(Output)
 >(Subtract 67 >(Output)
 >(Subtract 12 >(Output)
 >(Add      55 >(Output)
 >(Add      24 >(Output)
 >(Add      3  >(Output)
 >(Subtract 6  >(Output)
 >(Subtract 8  >(Output)
 >(Subtract 67 >(Output)
"""
CAT = " >start(Input >(Output) >start)"
#: The talk page's version: ``Sub``, which Zzo38 said the spec does not allow.
TALK_HELLO = """
>(Add 72 >(Output)             #H
>(Add 29 >(Output)             #e
>(Add 7  >(Output)             #l
         >(Output)             #l
>(Add 3  >(Output)             #o
>(Sub 67 >(Output)             #,
>(Sub 12 >(Output)             #
>(Add 55 >(Output)             #W
>(Add 24 >(Output)             #o
>(Add 3  >(Output)             #r
>(Sub 6  >(Output)             #l
>(Sub 8  >(Output)             #d
>(Sub 67 >(Output))))))))))))) #!
"""
#: Zzo38's SNZ macro from the talk page: send on only a nonzero number.
SNZ = "@SNZ(>(Subtract 1 >(Add 1 %)))\n|o(OutputNumber)\n"


def _run(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def _machine(code: str) -> _Machine:
    return _Machine(code, ScriptedIO(""))


def _send(command: str, value: int) -> str:
    """Send ``value`` through one node; print each result and a separator."""
    sinks = "|o(OutputNumber)|s(Constant 44>(Output))"
    return _run(f"{sinks}>(Constant {value} >({command} >o >s))")


def test_hello_world_prints_as_stated() -> None:
    assert _run(HELLO) == "Hello, World!"


def test_cat_echoes_any_character_until_eof() -> None:
    assert _run(CAT, "héllo\nworld") == "héllo\nworld"


def test_the_talk_pages_sub_is_refused_and_subtract_works() -> None:
    with pytest.raises(ValueError, match="no command 'Sub'"):
        _run(TALK_HELLO)
    assert _run(TALK_HELLO.replace("Sub ", "Subtract ")) == "Hello, World!"


@pytest.mark.parametrize(
    ("command", "value", "expected"),
    [
        ("Constant 9", 4, "9,"),
        ("Constant", 4, "0,"),  # a missing parameter is 0
        ("Add 3", 4, "7,"),
        ("Subtract 3", 4, "1,"),
        ("Subtract 5", 4, ""),
        ("Multiply 3", 4, "12,"),
        ("Divide 9", 4, "2,"),
        ("Divide 9", 0, ""),
        ("DivideBy 3", 10, "3,"),
        ("DivideBy", 10, ""),
        ("Modulo 9", 4, "1,"),
        ("Modulo 9", 0, ""),
        ("ModuloBy 3", 10, "1,"),
        ("ModuloBy", 10, ""),
        ("CountUp", 2, "0,1,2,"),
        ("CountDown", 2, "2,1,0,"),
        ("Interleave 6", 13, "121,"),
        ("LeftHalf", 121, "6,"),
        ("RightHalf", 121, "13,"),
        ("Output", 65, "A"),
        ("OutputNumber", 65, "65"),
    ],
)
def test_each_command_sends_its_results(
    command: str, value: int, expected: str
) -> None:
    assert _send(command, value) == expected


def test_every_result_reaches_every_target_before_the_next_result() -> None:
    assert _run(
        ">(Constant 2 >(CountUp >(OutputNumber) >(Add 5 >(OutputNumber))))"
    ) == ("051627")


def test_a_nodes_less_than_targets_come_first() -> None:
    # b sends to a (its '<'), then to o; a sends 5 to o.
    assert _run("|o(OutputNumber) >a(Constant 5 <b(Add 1 >o) >o) >b") == "551"
    # '<b' inside a, written after b: b's first target is still a.
    assert _run("|o(OutputNumber) >b(Add 1 >o) |a(Constant 5 >o <b)") == "51"


def test_input_number_reads_decimals_and_sends_nothing_at_eof() -> None:
    code = ">r(InputNumber >(Multiply 2 >(OutputNumber)) >r)"
    assert _run(code, "21 4\n") == "428"
    with pytest.raises(HaltError, match="non-negative"):
        _run(code, "-3")


def test_output_past_the_last_code_point_halts() -> None:
    with pytest.raises(HaltError, match=r"outside 0\.\.1114111"):
        _run(">(Constant 1114112 >(Output))")


def test_output_accepts_the_last_code_point() -> None:
    assert _run(">(Constant 1114111 >(Output))") == chr(1114111)


def test_a_fixed_node_closes_before_the_macro_uses_dollar() -> None:
    code = "@m(|x(OutputNumber) >c$(Constant 2 >x)) >(Constant 1 !m 0)"
    assert _run(code) == "2"


def test_macros_fill_their_parameter_and_number_each_call() -> None:
    assert _run(SNZ + ">(Constant 3 !SNZ >o >(Constant 0 !SNZ :>(Add 7 >o);))") == "3"
    cell = "@cell(|c$(Constant %>(OutputNumber)) >c$)"
    assert _run(cell + ">(Constant 0 !cell 5 !cell 7)") == "57"
    # Hoisted: invoked before its definition.
    twice = ">(Constant 4 !twice :>(OutputNumber);)@twice(>(Multiply 2 %))"
    assert _run(twice) == "8"


@pytest.mark.parametrize(
    ("code", "message"),
    [
        (">(Nope)", "no command 'Nope'"),
        (">(Add72)", "no command 'Add72'"),
        (">a(Add) >a(Add)", "'a' is defined twice"),
        (">later >later(Add)", "'later' is not defined yet"),
        ("<(Add)", "sends to the root"),
        (">", "neither name nor"),
        ("x", "expects a node type"),
        (">(Add))", "closes no node"),
        ("@m(>(Add) !m x)>(Add !m x)", "'m' invokes itself"),
        ("@m(|x(Add %))", "nothing inside it may use"),
        ("@m(@n(>(Add)))", "contains a macro definition"),
        ("@m(>(Add))@m(>(Add))", "'m' is defined twice"),
        (">(Add !q 1)", "macro 'q' is not defined"),
        (">(Add !m :x)@m(>(Add))", "has no ';'"),
        ("@m(>(Add)", "no closing"),
        ("@m", "needs @name"),
        (">(Add $)", "'\\$' appears outside a macro"),
    ],
)
def test_malformed_programs_are_refused(code: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _run(code)


def test_a_cycle_through_single_sends_revisits_its_state() -> None:
    machine = _machine(">a(Add 0 >a)")
    machine.step()
    first = machine.snapshot()
    machine.step()
    assert machine.snapshot() == first


class TestContract(EmptyProgramContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    run = _run
    machine = _machine
    halting_program = ">(Constant 3 >(CountDown >(Add 1)))"
    looping_program = ">a(Add 0 >a)"
