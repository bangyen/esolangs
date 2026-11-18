"""Tests for the Q-BAL interpreter, against the specification's examples."""

import pytest

from esolangs.exceptions import HaltError, ProgramError
from esolangs.languages.q_bal.interpreter import run
from esolangs.runtime.io import ScriptedIO

_STRINGS = (
    "QQ x\nQ y\ny = 'in\n*$y -> x\n; - 3\\(#y != 0) -> ;\n"
    "$x -> 'out\n; - 2\\(#x != 0) -> ;\n; ->"
)
_SQUARE = "F square\n Q x\n *in -> x\n x \\ in -> x\n x -> out\nF\n"


def _out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def test_the_specifications_examples() -> None:
    dump = "x -> out\n" * 3 + "y -> out\n" * 3
    assert _out("Q x = {1,2,3}\nQ y = {4,5,6}\nx -> y\ny -> x\n" + dump) == (
        "2\n3\n4\n5\n6\n1\n"
    )
    assert _out("Q x = {1,2,3}\nQ y = {4,6}\ny = x\ny -> out\n" + "x -> out\n" * 3) == (
        "1\n1\n2\n3\n"
    )
    assert _out("Q x\nin -> x\nx + 1 -> x\nx -> out", "41\n") == "42\n"
    # "will get input repeatedly until the number 0 is entered"
    assert _out("Q x\nin -> x\n; - 2 \\ (x != 0) -> ;\n9 -> out", "3\n5\n0\n") == "9\n"
    assert _out("Q x\nx = 'in\n'out = x", "hi there\n") == "hi there\n"
    assert _out(_SQUARE + "7 -> square\nsquare -> out") == "49\n"


def test_the_queue_of_queues_program_echoes_lines_then_a_blank() -> None:
    assert _out(_STRINGS, "hello\nworld\n\n") == "hello\nworld\n\n"


def test_a_label_saves_and_restores_the_program_counter() -> None:
    code = "Q LABEL\nQ n = {3}\nLABEL = ;\n*n -> out\nn - 1 -> n\nQ c\n*n -> c\n"
    loop = "; = LABEL\n"
    # Line 9 jumps back to line 4 while n is nonzero, else skips line 9.
    assert _out(code + "; + (c == 0) -> ;\n" + loop) == "3\n2\n1\n"


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("7 - 2 + 1 -> out", "4\n"),  # "^ \\ / | + -": + binds tighter than -
        ("8 / 2 \\ 2 -> out", "2\n"),  # \ binds tighter than /
        ("0 - 7 / 2 -> out", "-3\n"),  # truncates toward zero
    ],
)
def test_operator_precedence_follows_the_listed_order(code: str, expected: str) -> None:
    assert _out(code) == expected


def test_null_queues_and_override_prefixes() -> None:
    assert _out("Q x = {5}\nx ->\nx -> out") == ""  # an empty bare source moves nothing
    deferred = "F f\nin -> :out\nF\n"  # inside f, out is its output queue
    assert _out(deferred + "1 -> &f\n0 -> out\n-> f") == "0\n1\n"
    assert _out(deferred + "1 -> f\n0 -> out") == "1\n0\n"
    assert _out("Q x = {1,2}\n#x -> out\n*x -> out\nx =\n#x -> out") == "2\n1\n0\n"
    assert _out("Q x = {1,2}\nQ y = {3}\n$x -> y\n#x -> out\n" + "y -> out\n" * 3) == (
        "0\n3\n1\n2\n"
    )


def test_two_program_counters_interleave() -> None:
    code = "100 -> ;\n1 -> out\n2 -> out\n3 -> out\n4 -> out\n5 -> out"
    # ; = {100, 2}: the top is past the end, which halts.
    assert _out(code) == ""
    # ; = {4, 2}: lines 4, 2, 5, 3, then 6 drops one counter; 5 and 6 remain.
    code = "4 -> ;\n0 -> out\n0 -> out\n1 -> out\n2 -> out\n; ->"
    assert _out(code) == "1\n0\n2\n0\n2\n"


def test_a_function_returns_and_can_end_the_program() -> None:
    code = "F stop\n:; ->\n5 -> out\nF\n-> stop\n9 -> out"
    assert _out(code) == ""
    code = "F f\n; ->\n5 -> out\nF\n-> f\n9 -> out"
    assert _out(code) == "9\n"


@pytest.mark.parametrize(
    ("code", "error"),
    [
        (".M ONE 1", ProgramError),  # directives are never exercised
        ("F f\nQ x", ProgramError),  # an unterminated function block
        ("0 -> ;\n0 - 1 -> ;", HaltError),  # line 0 after the end-of-line step
    ],
)
def test_errors(code: str, error: type[Exception]) -> None:
    with pytest.raises(error):
        _out(code)
