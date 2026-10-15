"""Tests for the Quassaunt interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.quassaunt.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.contract import CycleContract, EmptyProgramContract

HELLO = " @@Hello_world! %%Printtoconsole"
HELLO_SPACE = """ @@Hello       @@[Whitespace] %%Obtain      %%Head
 %%Concatenate @@world!       %%Concatenate %%Printtoconsole"""
TRUTH = """ @@[Input] %%Inputchar %%Empty %%Makecontain %%Store
 @@[0]     @@0         %%Empty %%Makecontain %%Store
 @@[1Out]
   @@@@1?%%Printtoconsole?@@?@@?@@[1Out]?%%Obtain?@@?
   @@%%Concatenateall?%%Evaluatepermanently
   %%Concatenate
   %%Empty
   %%Makecontain
 %%Store

 @@@@0?%%Printtoconsole
 @@dummy @@[Input] %%Obtain %%Empty %%Makecontain %%Makecontain
 @@@@?@@?@@[1Out]?%%Obtain?@@?%%Concatenateall?%%Evaluatepermanently
         @@[0]     %%Obtain %%Empty %%Makecontain

 %%Ifpropersubset"""
#: The wiki's string idioms: set to string, and duplicate a string.
TO_STRING = " @@ %%Swap @@ %%Swap @@ %%Concatenateall"
DUPLICATE = """ @@Dummy %%Swap %%Empty %%Makecontain %%Store
 @@Dummy %%Obtain @@ %%Swap @@ %%Swap @@ %%Concatenateall
 @@Dummy %%Obtain @@ %%Swap @@ %%Swap @@ %%Concatenateall
 @@Dummy %%Delete"""
#: Print the error set's one message.
SHOW_ERROR = f" @@##Errormessage %%Obtain{TO_STRING} %%Printtoconsole"
LOOP = (
    "@@[L] @@@@?@@?@@[L]?%%Obtain?@@?%%Concatenateall?%%Evaluatepermanently "
    "%%Empty %%Makecontain %%Store @@ @@ @@[L] %%Obtain @@ %%Concatenateall %%Evaluate"
)


def _run(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def _machine(code: str) -> _Machine:
    return _Machine(code, ScriptedIO(""))


def test_the_hello_worlds_print_as_stated() -> None:
    assert _run(HELLO) == "Hello_world!"
    assert _run(HELLO_SPACE) == "Hello world!"


def test_the_truth_machine_prints_0_once_or_1_forever() -> None:
    assert _run(TRUTH, "0") == "0"
    io = ScriptedIO("1")
    machine = _Machine(TRUTH, io)
    for _ in range(200):
        machine.step()
    assert set(io.getvalue()) == {"1"}
    assert len(io.getvalue()) > 10


def test_the_wikis_duplicate_idiom_copies_a_string() -> None:
    assert _run(f"@@ab {DUPLICATE} %%Concatenate %%Printtoconsole") == "abab"


def test_set_operations_and_their_error_messages() -> None:
    two = "@@a %%Empty %%Makecontain"
    assert _run(f"@@-- @@x {two} @@b %%Swap %%Makecontain @@x %%Concatenateall"
                " %%Printtoconsole") == "a--b"  # fmt: skip
    assert _run(f"@@a {two} %%Makecontain {SHOW_ERROR}") == (
        "No_duplicates_are_allowed_in_a_set."
    )
    assert _run(f"{two} @@b %%Makenotcontain {SHOW_ERROR}") == (
        "The_set_does_not_contain_the_value_entered."
    )
    # Prints "empty" while the error set is a proper subset of {x}.
    check = (
        " @@@@empty?%%Printtoconsole @@x %%Empty %%Makecontain"
        " @@@@set?%%Printtoconsole @@##Errormessage %%Obtain %%Ifpropersubset"
    )
    assert _run(check) == "empty"
    duplicate = f"@@a {two} %%Makecontain @@[E] %%Swap %%Store"
    assert _run(duplicate + check) == "set"
    assert _run(f"{duplicate} @@##Errormessage %%Delete{check}") == "empty"


@pytest.mark.parametrize(
    ("bottom", "top", "proper", "disjoint"),
    [("@@a @@b", "@@a", "T", "F"), ("@@a", "@@a", "F", "F"), ("@@a", "@@b", "F", "T")],
)
def test_the_two_branches(bottom: str, top: str, proper: str, disjoint: str) -> None:
    def sets(words: str) -> str:
        return "%%Empty" + "".join(f" {w} %%Swap %%Makecontain" for w in words.split())

    for command, expected in (("Ifpropersubset", proper), ("Ifdisjoint", disjoint)):
        code = (
            f"@@@@T?%%Printtoconsole {sets(bottom)} @@@@F?%%Printtoconsole "
            f"{sets(top)} %%{command}"
        )
        assert _run(code) == expected, command


def test_locals_belong_to_one_evaluation_and_globals_to_all() -> None:
    store = "@@{0}?%%Empty?%%Store"
    assert _run(f"@@{store.format('[g]')} %%Evaluate @@[g] %%Obtain") == ""
    with pytest.raises(HaltError, match="no variable 'v'"):
        _run(f"@@{store.format('v')} %%Evaluate @@v %%Obtain")


def test_evaluatereplace_drops_the_rest_of_its_caller() -> None:
    assert _run("@@@@x?%%Printtoconsole %%Evaluate @@y %%Printtoconsole") == "xy"
    assert _run("@@@@x?%%Printtoconsole %%Evaluatereplace @@y %%Printtoconsole") == "x"
    # The inner call's own rest (z) and its caller's (y) are both dropped.
    permanent = "@@%%Evaluatepermanently?@@z?%%Printtoconsole %%Evaluate"
    assert _run(f"@@@@x?%%Printtoconsole {permanent} @@y %%Printtoconsole") == "x"


def test_argv_is_unsupported_and_says_so() -> None:
    assert _run(f"@@##Argvsupport %%Obtain{TO_STRING} %%Printtoconsole") == "N"
    store = "@@##Argvsupport %%Empty %%Store"
    assert _run(store + SHOW_ERROR) == "@@##Argvsupport_does_not_support_%%Store."
    with pytest.raises(HaltError, match="reserved variable '##Argv'"):
        _run("@@##Argv %%Obtain")


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("%%Swap", "needs more values"),
        ("%%Empty %%Printtoconsole", "needs a string"),
        ("@@x @@y %%Store", "needs a set, got 'y'"),
        ("@@ %%Head", "%%Head of an empty string"),
        ("@@v %%Delete", "found no variable 'v'"),
        ("@@[Whitespace] %%Empty %%Store", "cannot store"),
        ("@@^^x %%Obtain", "reserved variable"),
        (
            "@@ @@ %%Empty %%Empty %%Swap %%Makecontain @@ %%Concatenateall",
            "set inside",
        ),
        ("@@%%Nope %%Evaluate", "no word '%%Nope'"),
    ],
)
def test_invalid_operations_halt(code: str, message: str) -> None:
    with pytest.raises(HaltError, match=message):
        _run(code)


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("@@a %%Printtoconsole Hello", "no word 'Hello'"),
        ("@@a @@b %%Multithread", "an extension, not implemented"),
        ("%%^^Whatever", "no word"),
    ],
)
def test_malformed_programs_are_refused(code: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _run(code)


class TestContract(EmptyProgramContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    run = _run
    machine = _machine
    halting_program = HELLO
    looping_program = LOOP
