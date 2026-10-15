"""Tests for the Object disoriented interpreter."""

import pytest

from esolangs.languages.object_disoriented.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.contract import CycleContract, EmptyProgramContract

CAT = """
dcatloop.
  oi
  fsz
  rz
zz
dmain.
  flcatloop.z
  rz
zz
"""

DELAYED_CAT = """
dmain.cia cnfazobrzpap cncatcbactbrb snfpzrzzzt fatcftzt
cnfazobrzpip cnfazobrzpip cnfazobrzpip cnfazobrzpip
cnfazobrzpip cnfazobrzpip cnfazobrzpip ftprzzz
"""

#: The wiki's Hello world, its comments dropped; ``p0``/``p1`` end without ``r``.
_ROWS = [
    "01101000", "01100101", "01101100", "01101100", "01101111", "00100000",
    "01110111", "01101111", "01101100", "01110010", "01100100",
]  # fmt: skip
_PUSH = "".join(f"flp{bit}.a " for row in _ROWS for bit in row)
HELLO = f"""
dp0. cn cas rz pz p zz
dp1. cn cas r n fpz rz zz pz p zz
dmakehelloworld. {_PUSH} ra zz
dmakeloop8. rn fap fap fap fap fap fap fap fap rz pz zz
dmakeloop11. rn fap fap fap fap fap fap fap fap fap fap fap rz pz zz
dprintstackbit. cfpza oa rz zz
dmain. c flmakehelloworld.z a c flmakeloop11. flmakeloop8. lprintstackbit. b fba rz zz
"""
HELLO_REPAIRED = HELLO.replace("pz p zz", "pz p rz zz")


def _run(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def _machine(code: str) -> _Machine:
    return _Machine(code, ScriptedIO(""))


def _bits(*objects: str) -> str:
    """A main that prints one bit per object."""
    return "dmain." + "".join("o" + x for x in objects) + "rzzz"


def test_cat_echoes_until_input_runs_out() -> None:
    io = ScriptedIO("Hi")
    with pytest.raises(EOFError):
        run(CAT, io)
    assert io.getvalue() == "Hi"


@pytest.mark.parametrize(
    ("stdin", "out"), [("Hi\xc8tail", "Hi\xc8"), ("Hello\xff", "Hello\xff")]
)
def test_delayed_cat_stops_after_the_first_byte_above_128(stdin: str, out: str) -> None:
    assert _run(DELAYED_CAT, stdin) == out


def test_hello_world_as_printed_lacks_returns() -> None:
    with pytest.raises(ValueError, match=r"'d' at .* is not an object"):
        _run(HELLO)


def test_hello_world_repaired_pops_its_stack_last_in_first() -> None:
    """Reversed: the bytes of "hello wolrd" back to front, each bit-reversed."""
    data = "hello wolrd"[::-1]
    assert _run(HELLO_REPAIRED) == "".join(
        chr(int(f"{ord(c):08b}"[::-1], 2)) for c in data
    )


def test_the_minifuck_interpreter_leaves_c_without_a_destination() -> None:
    """Its first ``c fnrfaz pz t``: the call takes ``t``, then ``c`` meets ``c``."""
    with pytest.raises(ValueError, match=r"'c' at .* cannot be written"):
        _run("dmain. c fnrfaz pz t c fnrfaz tz a rz zz")


def test_bits_pack_most_significant_first() -> None:
    assert _run(_bits("z", "i", *["z"] * 5, "i"), "\x80") == "\x40"


def test_any_object_but_z_prints_one() -> None:
    """``n rz zz`` has z's function and members, so it is z."""
    assert _run(_bits("z", "nrzzz", "nrsss", "z", "z", "z", "z", "nrpzz")) == "\x21"


def test_a_partial_byte_is_never_printed() -> None:
    assert _run(_bits("i", "i"), "\xff") == ""


def test_an_input_one_calls_its_parameter_and_a_zero_does_not() -> None:
    # X prints a 1 bit; sixteen input bits, eight of them 1, print one byte.
    code = "dmain." + "fi n onrpzz rz zz" * 16 + "rzzz"
    assert _run(code, "\xff\x00") == "\xff"
    assert _run(code, "\x0f\xf0") == "\xff"


def test_a_write_to_s_lands_when_the_function_returns() -> None:
    # X sets ``s`` to z, then prints ``s``: still X, a 1.  Then t is z.
    code = "dmain. cnczsosrzzzt ftz ot" + "oz" * 6 + " rzzz"
    assert _run(code) == "\x80"


@pytest.mark.parametrize(("param", "out"), [("a", "\x00"), ("t", "\x80")])
def test_an_lvalue_argument_is_passed_as_its_place(param: str, out: str) -> None:
    """``f a a`` aliases: X's write to ``p`` is X's own place, so ``s`` is z."""
    code = f"dmain. cnczposrzzza fa{param}" + "oz" * 7 + " rzzz"
    assert _run(code) == out


def test_p_writes_reach_the_callers_variable() -> None:
    code = "dmain. f ncnfpzrzzzprzzz t ot" + "oz" * 7 + " rzzz"
    assert _run(code) == "\x80"


def test_a_temporary_argument_is_not_written_back() -> None:
    code = "dmain. f ncnfpzrzzzprzzz z ot" + "oz" * 7 + " rzzz"
    assert _run(code) == "\x00"


def test_t_starts_as_z() -> None:
    assert _run("dmain.ot" + "oz" * 7 + "rzzz") == "\x00"


def test_class_members_are_evaluated_where_l_is_written() -> None:
    """``l`` is a macro: ``k``'s member reads the instantiating frame's ``t``."""
    code = "dk.ra tz dmain. cnfpzrzzzt oflk.z" + "oz" * 7 + " rzzz"
    assert _run(code) == "\x80"


def test_whitespace_and_comments_are_ignored() -> None:
    code = "e a comment .d m a i n . o z e two .r z z z"
    with pytest.raises(ValueError, match="no 'main'"):
        _run(code.replace("m a i n", "mian"))
    assert _run(code) == ""


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("dmain.rz", "ends inside a form"),
        ("dmain.rzzz dmain.rzzz", "defined twice"),
        ("dmain.rlx.zz", "'x' is not defined"),
        ("dk.rzlk.z dmain.rlk.zz", "instantiates itself"),
        ("dmain.czzrzzz", "'z' at .* cannot be written"),
        ("dmain.rQzz", "'Q' at .* is not an object"),
        ("dmain.rzzz e open", "comment has no closing"),
        ("dmain.rl", "class name has no closing"),
        ("d.rzzz", "class name is empty"),
        ("xdmain.rzzz", "expects a definition"),
    ],
)
def test_malformed_programs_are_refused(code: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _run(code)


class TestContract(EmptyProgramContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    run = _run
    machine = _machine
    empty_raises = "Object disoriented program defines no 'main' class"
    halting_program = "dmain.rzzz"
    # Recursion is the only loop, and every call pushes a frame.
    no_cycle_reason = "Object disoriented divergence grows the call frame stack."
