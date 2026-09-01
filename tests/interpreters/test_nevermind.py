"""Unit tests for the Nevermind interpreter."""

from typing import ClassVar

from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.register_based.nevermind import run
from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.interpreters.runner import run_program


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class _PromptRecordingIO(ScriptedIO):
    """A :class:`ScriptedIO` that remembers the prompts it was asked with.

    ``_read`` ignores its prompt, so what ``input`` passes down is
    invisible in a program's output.
    """

    def __init__(self, stdin: str = "") -> None:
        super().__init__(stdin)
        self.prompts: list[str] = []

    def _read(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return super()._read(prompt)


class TestNevermind:
    def test_print(self) -> None:
        assert run_and_capture(["print,hello"]) == "hello"

    def test_print_comma_escape(self) -> None:
        assert run_and_capture(["print,Hello*44 World!"]) == "Hello, World!"

    def test_print_joins_its_arguments_with_nothing(self) -> None:
        """Several arguments run together; ``print`` adds no separator.

        Every ``print`` in the suite takes a single argument, where any
        separator at all would sit between nothing.
        """
        assert run_and_capture(["print,a,b,c"]) == "abc"

    def test_a_line_keeps_its_spaces_but_loses_its_newline(self) -> None:
        """Only the leading indent and the line terminator are trimmed.

        Programs are written here as bare strings with neither, so the
        three trims the parser applies were never told apart -- and a
        space *inside* an argument is text the program wrote.
        """
        assert run_and_capture(["print,a "]) == "a "
        assert run_and_capture(["print,a\n"]) == "a"
        assert run_and_capture(["  print,a"]) == "a"

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

    def test_a_dot_alone_does_not_spell_a_decimal(self) -> None:
        """Both sides of the dot must be digits, and there must be a dot.

        The rejected spellings the suite carries are all rejected by the
        round-trip check further down, which is only reached once the
        three conditions above already agree -- so the conditions
        themselves were never separated.  Each of these fails exactly one
        of them, and would reach ``float`` on a text that has no value.
        """
        assert run_and_capture(["print,a.5"]) == "a.5"
        assert run_and_capture(["print,."]) == "."
        assert run_and_capture(["print,5."]) == "5."

    def test_an_ordering_is_strict(self) -> None:
        """``>`` and ``<`` are false on equal operands.

        Every comparison in the suite is between operands that differ, so
        an ordering that also admitted equality would answer the same on
        all of them.
        """
        for cmp_op in (">", "<"):
            code = [f"if,5,{cmp_op},5", "print,Y", "endif", "print,after"]
            assert run_and_capture(code) == "after"

    def test_an_if_reads_only_its_first_three_operands(self) -> None:
        """A comparison is three tokens wide, whatever follows them.

        Nothing in the suite writes a fourth, so the width the ``if``
        takes was pinned only from below, by the check that rejects too
        few.
        """
        assert run_and_capture(["if,5,>,3,x", "print,Y", "endif"]) == "Y"

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

    def test_the_numeric_halt_names_the_operator_and_the_value(self) -> None:
        """Each arithmetic site says which operator refused, and on what.

        The suite only asks that these halt, so the label every call site
        hands the check -- and the value it quotes back -- goes unread.
        The two operands are separate calls, so each side needs asking.
        """
        import pytest

        from esolangs.exceptions import HaltError

        for code, message in (
            (["make,x,ab", "make,z,$x,+,1"], "+ needs a number, got 'ab'"),
            (["make,x,ab", "make,z,1,+,$x"], "+ needs a number, got 'ab'"),
            (["make,x,ab", "if,$x,>,3", "endif"], "> needs a number, got 'ab'"),
            (["make,x,ab", "if,3,>,$x", "endif"], "> needs a number, got 'ab'"),
            (["make,x,ab", "if,$x,<,3", "endif"], "< needs a number, got 'ab'"),
            (["make,x,ab", "if,3,<,$x", "endif"], "< needs a number, got 'ab'"),
            (["make,x,ab", "loop,$x", "endloop"], "loop needs a number, got 'ab'"),
        ):
            with pytest.raises(HaltError) as caught:
                run_and_capture(code)
            assert str(caught.value) == message

    def test_the_malformed_messages_read_in_full(self) -> None:
        """Each message entire, not the fragment the tests match on.

        ``match=`` is a substring search, so the assertions above pass on
        a message padded or reworded around the phrase they look for.
        """
        import re

        import pytest

        for code, message in (
            (["input"], "input requires a prompt"),
            (["make,x"], "make requires a name and a value"),
            (["if"], "if requires two operands and a comparison"),
            (["loop"], "loop requires a count"),
        ):
            with pytest.raises(ValueError, match=re.escape(message)) as caught:
                run_and_capture(code)
            assert str(caught.value) == message

    def test_input_passes_its_own_prompt_down(self) -> None:
        """The prompt written in the program is the one the reader is asked
        with.

        ``ScriptedIO`` ignores its prompt, so a program's output says
        nothing about what reached the read; only the reader can.
        """
        io = _PromptRecordingIO("hi\n")
        run(["input,name?", "print,$answer"], io)
        assert io.prompts == ["name?"]
        assert io.getvalue() == "hi"

    def test_the_partner_scan_counts_every_nested_marker(self) -> None:
        """A false ``if`` clears its whole block, nesting included.

        The suite's nested case puts the two ``endif`` lines back to back,
        where landing on the inner one and landing past the outer one look
        alike -- ``endif`` executes as nothing.  A line between them makes
        the depth the scan tracked visible.
        """
        code = [
            "if,1,<,0",
            "if,1,>,0",
            "print,deep",
            "endif",
            "print,mid",
            "endif",
            "print,done",
        ]
        assert run_and_capture(code) == "done"

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
