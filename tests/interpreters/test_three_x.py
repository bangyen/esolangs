"""Unit tests for the 3x interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.three_x import run


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class Test3x:
    def test_literal(self) -> None:
        assert run_program("[Hi]") == "Hi"
        assert run_program("[Hello, World!]") == "Hello, World!"

    def test_literal_skips_past_bracket(self) -> None:
        # the literal ends at the first ], so trailing commands still run
        assert run_program("[A]333x!") == "A0"

    def test_push_three(self) -> None:
        assert run_program("3!") == "3"

    def test_x_operation(self) -> None:
        # (3-3)/3 = 0, (3-0)/3 = 1
        assert run_program("333x!") == "0"
        assert run_program("3333x3x!") == "1"

    def test_fraction_output(self) -> None:
        # (1-3)/3 = -2/3, printed as a fraction
        assert run_program("3333333x3xx!") == "-2/3"

    def test_swap(self) -> None:
        assert run_program("333x3!") == "3"
        assert run_program("333x3#!") == "0"  # swapped

    def test_read(self) -> None:
        assert run_program("33?x!", "6\n") == "1"  # (6-3)/3
        assert run_program("?3^!", "6\n") == "3"  # unassigned variable -> 3

    def test_store_and_recall(self) -> None:
        assert run_program("3^!") == "3"  # default value for an unassigned key
        assert run_program("3333xv3^!") == "0"  # store 0 under 3, recall it

    def test_loop(self) -> None:
        # push 1, loop prints 0 then exits on the 0
        assert run_program("3333x3x(33x)!") == "0"
        # push 0, the loop skips
        assert run_program("333x(3)!") == "0"

    def test_loop_repeats(self) -> None:
        # push 3, loop: 33x -> 0, exit; but with a counter... use input: ? reads n
        # (3-?)/3 ... instead verify the loop body runs while top nonzero
        assert run_program("3(33x)!") == "0"

    def test_error_empty_stack(self) -> None:
        with pytest.raises(HaltError):
            run_program("x")
        with pytest.raises(HaltError):
            run_program("!")
        with pytest.raises(HaltError):
            run_program("#")
        with pytest.raises(HaltError):
            run_program("(")
        with pytest.raises(HaltError):
            run_program(")")

    def test_error_division_by_zero(self) -> None:
        with pytest.raises(HaltError):
            run_program("333x33x!")

    def test_error_bad_input(self) -> None:
        with pytest.raises(ValueError, match="integer or a fraction"):
            run_program("?", "abc")
        with pytest.raises(ValueError, match="integer or a fraction"):
            run_program("?", "1/0")

    def test_loop_jumps_back_on_nonzero_top(self) -> None:
        # pass 1 ends with a 3 on top (jump back), pass 2 with a 0 (exit)
        assert run_program("333(33x#)!") == "0"

    def test_unmatched_print_bracket_prints_nothing(self) -> None:
        assert run_program("[") == ""

    def test_error_unmatched_bracket(self) -> None:
        with pytest.raises(HaltError):
            run_program("333x(")
        with pytest.raises(HaltError):
            run_program("33)")

    def test_empty_program(self) -> None:
        assert run_program("") == ""
