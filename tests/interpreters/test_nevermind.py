"""Unit tests for the Nevermind interpreter."""

from typing import ClassVar

from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.nevermind import run
from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.interpreters.runner import run_program


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class TestNevermind:
    def test_print(self) -> None:
        assert run_and_capture(["print,hello"]) == "hello"

    def test_print_comma_escape(self) -> None:
        assert run_and_capture(["print,Hello*44 World!"]) == "Hello, World!"

    def test_print_unicode_digits(self) -> None:
        """Non-ASCII digits stay strings instead of being converted to int."""
        assert run_and_capture(["print,²"]) == "²"
        assert run_and_capture(["print,١٢٣"]) == "١٢٣"

    def test_make_and_print_variable(self) -> None:
        assert run_and_capture(["make,x,5", "print,$x"]) == "5"

    def test_arithmetic(self) -> None:
        code = ["make,x,5", "make,y,3", "make,z,$x,+,$y", "print,$z"]
        assert run_and_capture(code) == "8"

    def test_if_true(self) -> None:
        code = ["if,5,>,3", "print,big", "endif", "print,after"]
        assert run_and_capture(code) == "bigafter"

    def test_if_false_skips_body(self) -> None:
        code = ["if,5,<,3", "print,big", "endif", "print,after"]
        assert run_and_capture(code) == "after"

    def test_loop(self) -> None:
        assert run_and_capture(["loop,3", "print,x", "endloop"]) == "xxx"

    def test_loop_exit_resumes_after_body(self) -> None:
        """Code after a finished loop still runs (skip flag must reset)."""
        code = ["loop,1", "print,inside", "endloop", "print,after"]
        assert run_and_capture(code) == "insideafter"

    def test_zero_loop_skips_body(self) -> None:
        """A loop of zero iterations runs nothing but continues after it."""
        code = ["loop,0", "print,x", "endloop", "print,after"]
        assert run_and_capture(code) == "after"

    def test_make_string_concatenation(self) -> None:
        """The ++ operator concatenates strings."""
        code = ["make,x,hello", "make,y,world", "make,z,$x,++,$y", "print,$z"]
        assert run_and_capture(code) == "helloworld"

    def test_calculator_addition(self) -> None:
        """The calculator example from esolangs.org."""
        code = [
            "make,a,10",
            "make,b,5",
            "make,operation,+",
            "if,$operation,==,+",
            "make,final,$a,+,$b",
            "print,$final",
            "endif",
        ]
        assert run_and_capture(code) == "15"

    def test_input_command(self) -> None:
        """Input stores a value in the answer variable."""
        assert run_and_capture(["input,prompt", "print,$answer"], inputs=["hi"]) == "hi"

    def test_make_subtract(self) -> None:
        code = ["make,x,10", "make,y,4", "make,z,$x,-,$y", "print,$z"]
        assert run_and_capture(code) == "6"

    def test_make_multiply(self) -> None:
        code = ["make,x,3", "make,y,4", "make,z,$x,*,$y", "print,$z"]
        assert run_and_capture(code) == "12"

    def test_make_divide(self) -> None:
        code = ["make,x,8", "make,y,2", "make,z,$x,/,$y", "print,$z"]
        assert run_and_capture(code) == "4.0"

    def test_nested_if(self) -> None:
        code = ["if,5,>,3", "if,2,>,1", "print,deep", "endif", "endif", "print,done"]
        assert run_and_capture(code) == "deepdone"

    def test_false_if_skips_nested_block(self) -> None:
        """A false outer if scans past a nested if to the matching endif."""
        code = ["if,5,<,3", "if,2,>,1", "print,deep", "endif", "endif", "print,done"]
        assert run_and_capture(code) == "done"

    def test_unmatched_if_scans_off_end(self) -> None:
        """A false if with no matching endif is a malformed program."""
        import pytest

        with pytest.raises(ValueError, match="unmatched"):
            run_and_capture(["if,5,<,3", "print,x"])

    def test_loop_with_nested_if(self) -> None:
        code = ["loop,2", "if,1,>,0", "print,x", "endif", "endloop"]
        assert run_and_capture(code) == "xx"

    def test_unmatched_endloop_rejected(self) -> None:
        """An endloop with no matching loop is a malformed program."""
        import pytest

        with pytest.raises(ValueError, match="unmatched"):
            run_and_capture(["endloop"])

    def test_divide_by_zero_halts(self) -> None:
        """Division by zero is an invalid operation."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture(["make,x,1", "make,y,0", "make,z,$x,/,$y"])

    def test_undefined_variable_halts(self) -> None:
        """Referencing an undefined $name is an invalid operation."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture(["print,$nope"])

    def test_input_without_prompt_rejected(self) -> None:
        """input with no prompt is a malformed program."""
        import pytest

        with pytest.raises(ValueError, match="prompt"):
            run_and_capture(["input"])


class TestStepMachine:
    def test_empty_program_is_halted(self) -> None:
        from esolangs.interpreters.register_based.nevermind import _Machine

        assert _Machine([], IO()).halted is True

    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.register_based.nevermind import _Machine

        machine = _Machine([], IO())
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.halted

    def test_arithmetic_on_a_string_halts(self) -> None:
        """``+ - * /`` are numeric; ``++`` is the operator that joins text."""
        import pytest

        from esolangs.exceptions import HaltError

        for op in ("+", "-", "*", "/"):
            with pytest.raises(HaltError):
                run_and_capture(
                    ["make,x,ab", "make,y,cd", f"make,z,$x,{op},$y", "print,$z"]
                )

    def test_mixed_operands_halt(self) -> None:
        """A number and a string have no defined sum (the wiki's calculator)."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture(["make,x,3", "make,y,cd", "make,z,$x,+,$y", "print,$z"])

    def test_ordered_comparison_on_a_string_halts(self) -> None:
        """``>``/``<`` order numbers; they do not compare text."""
        import pytest

        from esolangs.exceptions import HaltError

        for cmp_op in (">", "<"):
            with pytest.raises(HaltError):
                run_and_capture(
                    ["make,x,ab", "make,y,cd", f"if,$x,{cmp_op},$y", "print,Y", "endif"]
                )

    def test_equality_still_compares_strings(self) -> None:
        """``=`` is not ordering, so it keeps working on text."""
        code = ["make,x,ab", "make,y,ab", "if,$x,=,$y", "print,Y", "endif"]
        assert run_and_capture(code) == "Y"

    def test_loop_count_must_be_a_number(self) -> None:
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture(["make,x,ab", "loop,$x", "print,h", "endloop"])

    def test_decimal_arithmetic(self) -> None:
        """A decimal spelling is a number: it adds rather than concatenating."""
        assert (
            run_and_capture(["make,x,2.5", "make,y,4", "make,z,$x,+,$y", "print,$z"])
            == "6.5"
        )
        assert (
            run_and_capture(["make,x,2.5", "make,y,3", "make,z,$x,*,$y", "print,$z"])
            == "7.5"
        )
        assert (
            run_and_capture(
                ["make,x,2.5", "make,y,3", "if,$x,<,$y", "print,Y", "endif"]
            )
            == "Y"
        )

    def test_non_canonical_decimals_stay_strings(self) -> None:
        """``02.5`` is not a number spelling, so ``++`` keeps what was written."""
        code = ["make,x,0", "make,y,2.5", "make,z,$x,++,$y", "print,$z"]
        assert run_and_capture(code) == "02.5"
        assert run_and_capture(["print,02.5"]) == "02.5"

    def test_string_concatenation_still_works(self) -> None:
        """``++`` is unaffected by the numeric guards."""
        code = ["make,x,ab", "make,y,cd", "make,z,$x,++,$y", "print,$z"]
        assert run_and_capture(code) == "abcd"

    def test_missing_operands_are_rejected(self) -> None:
        """A command short of its operands is malformed program text."""
        import pytest

        for code, message in (
            (["make,x"], "make requires"),
            (["make,x,"], "make requires"),
            (["make"], "make requires"),
            (["make,x,1", "if,$x,>"], "if requires"),
            (["if"], "if requires"),
            (["loop"], "loop requires"),
        ):
            with pytest.raises(ValueError, match=message):
                run_and_capture(code)

    def test_blank_lines_are_skipped_by_the_partner_scan(self) -> None:
        """A blank line has no command, so ``find`` must step over it."""
        assert run_and_capture(["if,1,==,1", "  ", "print,X", "endif"]) == "X"
        assert (
            run_and_capture(["if,1,==,0", "  ", "print,X", "endif", "print,Y"]) == "Y"
        )
        loop = ["make,n,2", "loop,$n", "", "print,h", "endloop"]
        assert run_and_capture(loop) == "hh"


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.register_based.nevermind import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program: ClassVar[list[str]] = ["make,x,5"]
    halting_program: ClassVar[list[str]] = ["make,x,5"]
