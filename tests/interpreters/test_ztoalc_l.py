"""Unit tests for the ZTOALC L interpreter.

ZTOALC L L executes lines in Collatz-trajectory order determined by the initial
pointer value. With pointer 3, lines are visited in the order 2, 4, 3, 1.
"""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.interpreters.io import IO
from esolangs.interpreters.other.ztoalc_l import run


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestZTOALC:
    def test_print_constant(self) -> None:
        assert run_and_capture(["10", "print 65"]) == "A"

    def test_print_other_constant(self) -> None:
        assert run_and_capture(["2", "print 66"]) == "B"


class TestZTOALCVariables:
    """Lines are visited in Collatz order: 2 (assign), 4 (arith), 3 (print), 1."""

    def test_assignment_and_subtract(self) -> None:
        """X = 66, x - 1, print x -> 'A'."""
        code = ["3", "jump x 0", "x = 66", "print x", "x - 1"]
        assert run_and_capture(code) == "A"

    def test_assignment_and_add(self) -> None:
        code = ["3", "jump x 0", "x = 66", "print x", "x + 1"]
        assert run_and_capture(code) == "C"

    def test_input(self) -> None:
        """X = input reads a character, then arithmetic applies."""
        code = ["3", "jump x 0", "x = input", "print x", "x - 1"]
        assert run_and_capture(code, inputs=["A"]) == "@"

    def test_array_creation_and_indexing(self) -> None:
        """X = [3] creates a zeroed array; y = x[1] indexes it."""
        code = ["3", "jump y 0", "x = [3]", "print y", "y = x[1]"]
        assert run_and_capture(code) == "\x00"

    def test_array_element_write(self) -> None:
        """x[1] = 5 writes into the array (per the wiki spec)."""
        code = [
            "3",
            "jump y 0",
            "x = [3]",
            "print y",
            "y = x[1]",
            "",
            "",
            "",
            "",
            "x[1] = 5",
        ]
        assert run_and_capture(code) == "\x05"

    def test_runtime_indexed_array_write(self) -> None:
        """x[i] = v with a runtime index writes the indexed element."""
        code = [
            "6",
            "jump y 0",
            "x = [3]",
            "print y",
            "y = x[i]",
            "i = 2",
            "",
            "",
            "",
            "x[i] = 7",
        ]
        assert run_and_capture(code) == "\x07"

    def test_negative_literal(self) -> None:
        """X = -5 then x + 8 gives 3."""
        code = ["3", "jump x 0", "x = -5", "print x", "x + 8"]
        assert run_and_capture(code) == "\x03"

    def test_firing_jump(self) -> None:
        """A jump with a nonzero condition increments the pointer."""
        code = ["3", "print 105", "jump if 1", "print 104"]
        assert run_and_capture(code) == "hi"

    def test_empty_program_rejected(self) -> None:
        """An empty program is malformed."""
        import pytest

        with pytest.raises(ValueError, match="empty"):
            run([], IO())

    def test_missing_print_operand_rejected(self) -> None:
        """A print with no operand is a malformed program."""
        import pytest

        with pytest.raises(ValueError, match="operand"):
            run_and_capture(["2", "print"])

    def test_missing_jump_operand_rejected(self) -> None:
        """A jump with no condition is a malformed program."""
        import pytest

        with pytest.raises(ValueError, match="operand"):
            run_and_capture(["2", "jump"])

    def test_undefined_array_halts(self) -> None:
        """Indexing an undefined array is an invalid operation."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture(["3", "jump y 0", "y = x[1]", "print y"])

    def test_indexing_non_array_halts(self) -> None:
        """Indexing a variable that is not an array is an invalid operation."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture(["3", "jump y 0", "x = 5", "print y", "y = x[1]"])

    def test_out_of_range_index_halts(self) -> None:
        """Indexing past the end of an array is an invalid operation."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture(["3", "jump y 0", "x = [2]", "y = x[5]"])

    def test_store_to_scalar_halts(self) -> None:
        """Writing an element of a scalar variable is an invalid operation."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture(["3", "jump x 0", "x = 5", "print 65", "x[0] = 7"])

    def test_store_out_of_range_halts(self) -> None:
        """Writing past the end of an array is an invalid operation."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture(["3", "jump x 0", "x = [2]", "print 65", "x[5] = 7"])

    def test_negative_pointer_halts(self) -> None:
        """A negative pointer is an invalid operation."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture(["-2", "print 65"])


class TestArraysOfArrays:
    """Arrays can hold arrays; index expressions are general (per the wiki)."""

    def test_read_nested_element(self) -> None:
        """x[0] = [3] makes element 0 an array; x[0][2] reads into it."""
        code = ["6", "jump y 0", "x = [2]", "print x[0][2]", "x[0] = [3]"]
        assert run_and_capture(code) == "\x00"

    def test_write_and_read_nested_element(self) -> None:
        """Writing a deep element and reading it back round-trips."""
        code = [
            "12",
            "",
            "x = [2]",
            "print x[1][2]",
            "x[1] = [5]",
            "jump y 0",
            "",
            "x[1][2] = 66",
            "",
            "",
            "",
            "",
        ]
        assert run_and_capture(code) == "B"

    def test_compound_index_expression(self) -> None:
        """The index can itself be an indexed expression, e.g. a[b[0]]."""
        code = [
            "12",
            "",
            "a = [3]",
            "print a[b[0]]",
            "a[2] = 66",
            "jump y 0",
            "",
            "b[0] = 2",
            "",
            "b = [2]",
            "",
            "",
        ]
        assert run_and_capture(code) == "B"

    def test_array_size_must_be_number(self) -> None:
        """A [expr] whose size is an array is an invalid operation."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture(["3", "jump y 0", "x = [[2]]", "print 65"])

    def test_print_of_array_halts(self) -> None:
        """print requires a number; printing an array is invalid."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture(["3", "jump y 0", "x = [2]", "print x"])

    def test_jump_condition_must_be_number(self) -> None:
        """jump requires a number; an array condition is invalid."""
        import pytest

        from esolangs.exceptions import HaltError

        code = ["12", "", "x = [2]", "print 65", "", "jump y 0", "", "jump if x"]
        with pytest.raises(HaltError):
            run_and_capture(code)

    def test_indexing_scalar_element_halts(self) -> None:
        """x[0][1] needs x[0] to be an array; a scalar element is invalid."""
        import pytest

        from esolangs.exceptions import HaltError

        code = [
            "12",
            "",
            "x = [3]",
            "print 65",
            "x[0] = 5",
            "jump y 0",
            "",
            "y = x[0][1]",
        ]
        with pytest.raises(HaltError):
            run_and_capture(code)

    def test_malformed_index_is_rejected(self) -> None:
        """An unbalanced or empty index on the lhs is a malformed program."""
        import pytest

        with pytest.raises(ValueError, match="unbalanced"):
            run_and_capture(["3", "jump y 0", "a = [2]", "a[1 = 5"])
        with pytest.raises(ValueError, match="missing expression"):
            run_and_capture(["3", "jump y 0", "a = [2]", "a[] = 5"])

    def test_nested_write_through_a_scalar_middle_halts(self) -> None:
        """x[0][1][2] = v needs x[0] to be an array; a scalar middle halts."""
        import pytest

        from esolangs.exceptions import HaltError

        code = [
            "3",
            "jump x 0",
            "x = [2]",
            "print 0",
            "",
            "",
            "print 0",
            "x[0][1][2] = 5",
        ]
        with pytest.raises(HaltError):
            run_and_capture(code)

    def test_nested_write_through_out_of_range_middle_halts(self) -> None:
        """A middle index past the array is rejected rather than wrapping."""
        import pytest

        from esolangs.exceptions import HaltError

        code = [
            "3",
            "jump x 0",
            "x = [2]",
            "x[5][0] = 1",
            "x[0] = [2]",
            "",
            "",
            "x[1] = [2]",
        ]
        with pytest.raises(HaltError):
            run_and_capture(code)

    def test_index_by_an_array_element(self) -> None:
        """An index expression may itself be an indexed array element."""
        code = [
            "3",
            "jump x 0",
            "x = [2]",
            "print x[1]",
            "a = [2]",
            "",
            "",
            "x[a[1]] = 5",
        ]
        assert run_and_capture(code) == "\x00"

    def test_print_out_of_unicode_range_halts(self) -> None:
        import pytest

        from esolangs.exceptions import HaltError

        code = [
            "3",
            "jump x 0",
            "x = [2]",
            "print 99999999",
            "",
            "",
            "print 0",
            "print 0",
        ]
        with pytest.raises(HaltError):
            run_and_capture(code)

    def test_pointer_below_zero_halts(self) -> None:
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture(["0"])
