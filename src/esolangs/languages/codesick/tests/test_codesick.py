"""Tests for the Codesick interpreter."""

import pytest

from esolangs.languages.codesick.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO

TRUTH = "codesick in a 0 1;\n0 codesick out 0 * halt;\n1 codesick out 1 * 1;"


def _run(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def _steps(code: str, stdin: str, count: int) -> tuple[_Machine, ScriptedIO]:
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    for _ in range(count):
        machine.step()
    return machine, io


def test_wiki_hello_world_and_xkcd() -> None:
    assert _run('codesick out "Hello, world!" * *;') == "Hello, world!"
    assert _run("codesick out 4 * *;") == "4"


def test_wiki_cat_prints_its_input_forever() -> None:
    machine, io = _steps("cat codesick out in * cat;", "ab", 3)
    assert io.getvalue() == "ababab"
    assert not machine.halted


def test_wiki_truth_machine() -> None:
    assert _run(TRUTH, "0") == "0"
    machine, io = _steps(TRUTH, "1", 5)
    assert io.getvalue() == "1111"
    assert not machine.halted


def test_jumps_and_out_take_the_argument_as_written() -> None:
    # The truth machine's first line sets *1 to "1a"; line 1 still prints
    # "1" and jumps to label "1".
    machine, io = _steps(TRUTH, "1", 1)
    assert machine.memory["1"] == "1a"
    machine.step()
    assert (io.getvalue(), machine.ip) == ("1", TRUTH.index("1 codesick"))


def test_a_hit_deletes_the_first_occurrence_and_jumps_to_d() -> None:
    code = 'codesick x "abb" b n;\nb codesick out yes * *;\nn codesick out no * *;'
    assert _run(code) == "yes"
    assert _steps(code, "", 1)[0].memory["x"] == "xab"
    assert _run(code.replace("b n;", "q n;", 1)) == "no"


def test_the_dereference_argument() -> None:
    # *j = "jm", *jm = "jmv"; then C = j sets *j to **j = "jmv".
    code = 'codesick j m "" z w;\nw codesick jm v "" z u;\nu codesick c "" j z t;'
    assert _steps(code, "", 3)[0].memory["j"] == "jmv"


def test_quoted_strings_are_not_keywords() -> None:
    assert _run('codesick out "in" * *;', "x") == "in"
    assert _run('codesick out "say \\"hi\\"" * *;') == 'say "hi"'


def test_every_in_is_the_whole_input() -> None:
    assert _run("codesick in in z w;\nw codesick out in * *;", "01") == "01"
    assert _steps("codesick in in z w;", "01", 1)[0].memory["01"] == "0101"


def test_a_missing_label_halts_and_empty_programs_halt() -> None:
    assert _run("codesick x y z nowhere;") == ""
    assert _run("") == ""


@pytest.mark.parametrize(
    "code",
    [
        "codesick a b c;",
        "codesick a b c d e f;",
        "x y codesick a b c d;",
        "codesick a out c d;",
        "out codesick a b c d;",
        "codesick codesick b c d;",
        "l codesick a b c d;\nl codesick a b c d;",
        'codesick "a b c d;',
        "codesick a b c d",
        "a b c d;",
    ],
)
def test_malformed_programs_raise(code: str) -> None:
    with pytest.raises(ValueError, match="Codesick"):
        run(code, ScriptedIO())
