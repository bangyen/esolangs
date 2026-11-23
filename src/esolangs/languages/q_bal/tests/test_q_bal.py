"""Tests for the Q-BAL interpreter, against the specification's examples."""

import sys

import pytest

from esolangs import Language
from esolangs.exceptions import HaltError, ProgramError
from esolangs.languages.q_bal.interpreter import _Machine, run
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
    assert _out("Q x\nx = 'in\n'out = x", "A\r\r\n") == "A\r\n"
    assert _out(_SQUARE + "7 -> square\nsquare -> out") == "49\n"


def test_the_queue_of_queues_program_echoes_lines_then_a_blank() -> None:
    assert _out(_STRINGS, "hello\nworld\n\n") == "hello\nworld\n\n"


def test_end_statement_skips_lines_and_can_be_reset() -> None:
    source = ".P ;+2 -> ;\n1 -> out\n2 -> out\n.P ;+1 -> ;\n3 -> out\n4 -> out"
    assert _out(source) == "1\n3\n4\n"


def test_function_end_statement_is_local() -> None:
    source = "F f\n.P ;+2 -> ;\n1 -> :out\n2 -> :out\n3 -> :out\nF\n-> f\n4 -> out"
    assert _out(source) == "1\n3\n4\n"


def test_custom_end_statement_runs_after_a_function_returns() -> None:
    # The body resolves before the custom end statement inspects the result.
    source = "F f\n1 -> out\nF\n.P ;+f -> ;\n-> f\n.P ;+1 -> ;\n2 -> out"
    assert _out(source) == "2\n"


def test_end_statement_does_not_repeat_line_on_input_error() -> None:
    machine = _Machine(".P in -> ;\n1 -> out\n2 -> out", io := ScriptedIO())
    machine.step()
    assert io.getvalue() == "1\n"
    for _ in range(2):
        with pytest.raises(EOFError):
            machine.step()
        assert io.getvalue() == "1\n"


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


def test_function_assignment_copies_all_three_queues() -> None:
    source = (
        "F f\nin + 1 -> out\nF\nF g\n99 -> out\nF\n"
        "40 -> &f\n7 -> @f\n2 -> &g\n3 -> @g\ng = f\ng = g\n"
        "-> g\ng -> out\ng -> out\n-> f\nf -> out\nf -> out"
    )
    assert _out(source) == "7\n41\n7\n41\n"


def test_function_assignment_changes_later_calls() -> None:
    source = "F f\n2 -> :out\nF\nF g\n:g = :f\n1 -> :out\nF\n-> g\n-> g"
    assert _out(source) == "1\n2\n"


@pytest.mark.parametrize("assignment", ["f = q", "q = f", "f = {1}"])
def test_function_assignment_requires_matching_types(assignment: str) -> None:
    with pytest.raises(HaltError, match="assigned"):
        _out("F f\nF\nQ q\n" + assignment)


def test_instruction_queue_append_and_nested_statements() -> None:
    source = "F f\n5 -> :out\nF\n[[7 -> :out] -> code] -> ~f\n-> f\n"
    assert _out(source) == "5\n7\n"


def test_function_copy_keeps_independent_instruction_queues() -> None:
    source = (
        "F f\n1 -> :out\nF\nF g\n2 -> :out\nF\n"
        "[3 -> :out] -> ~f\ng = f\n"
        "~f = [4 -> :out]\n-> f\n-> g"
    )
    assert _out(source) == "4\n1\n3\n"


def test_main_code_and_instruction_queue_move() -> None:
    source = "F f\n2 -> out\nF\n~f -> code\n#~f -> out"
    assert _out(source) == "0\n2\n"


def test_instruction_queue_rejects_numeric_items_and_arithmetic() -> None:
    for source in ("1 -> code", "[1 -> out] + 1 -> out", "Q q\n[1 -> out] -> q"):
        with pytest.raises(HaltError):
            _out(source)


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


def test_integers_ignore_pythons_decimal_limit() -> None:
    language = Language("Q-BAL")
    number = "1" + "0" * 1000
    previous = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(640)
        assert language.run(f"{number} -> out").output == number + "\n"
        assert language.run(f"Q x = {{{number}}}\nx -> out").output == number + "\n"
        assert language.run("in -> out", stdin=f"-{number}\n").output == f"-{number}\n"
        assert language.run("10 ^ 1000 -> out").output == number + "\n"
        with pytest.raises(HaltError, match="divides by zero"):
            language.run(f"{number} / 0 -> out")
        with pytest.raises(ProgramError, match="literal queue holds numbers"):
            language.run("Q x = {²}")

        table = "0" * (2**14 - 1) + "1"
        artifact = language.generate(table)
        assert language.evaluate(artifact, [0] * 14).answer == "0"
        assert language.evaluate(artifact, [1] * 14).answer == "1"
    finally:
        sys.set_int_max_str_digits(previous)


def test_output_retry_uses_the_same_number() -> None:
    class InterruptedOutput(ScriptedIO):
        def print_str(self, text: str) -> None:
            if not self.getvalue():
                super().print_str(text[:1])
                raise HaltError("output interrupted")
            super().print_str(text)

    for source, stdin, setup_steps, reads in (
        ("in -> out", "123\n456\n", 0, 1),
        ("Q x = {123,456}\nx -> out", "", 1, 0),
    ):
        io = InterruptedOutput(stdin)
        machine = _Machine(source, io)
        for _ in range(setup_steps):
            machine.step()
        with pytest.raises(HaltError, match="output interrupted"):
            machine.step()
        assert (io.getvalue(), io.reads) == ("1", reads)
        machine.step()
        assert machine.halted
        assert (io.getvalue(), io.reads) == ("123\n", reads)


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
