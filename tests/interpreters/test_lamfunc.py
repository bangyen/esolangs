"""Unit tests for the Lamfunc interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.lamfunc import run
from tests.interpreters.contract import SnapshotContract


def run_program(code: str) -> str:
    io = ScriptedIO()
    run(code, io)
    return io.getvalue()


class TestBuiltins:
    def test_print_number_as_binary(self) -> None:
        assert run_program("p 5") == "101"
        assert run_program("p 0") == "0"

    def test_print_binary_literal(self) -> None:
        assert run_program("p 0b101") == "101"

    def test_equality(self) -> None:
        assert run_program("p eq 1 1") == "1"
        assert run_program("p eq 1 2") == "0"

    def test_if_selects_branch(self) -> None:
        assert run_program("p i 1 7 8") == "111"
        assert run_program("p i 0 7 8") == "1000"

    def test_if_is_lazy(self) -> None:
        # the unchosen branch's p must not run
        assert run_program("p i 1 3 p 9") == "11"

    def test_combine_bits(self) -> None:
        # 0b10 and 0b110 combine to 0b10110
        assert run_program("p cb 2 6") == "10110"

    def test_last_and_all_but_last_bit(self) -> None:
        assert run_program("p lb 5") == "1"
        assert run_program("p fb 5") == "10"

    def test_set_and_get_variable(self) -> None:
        assert run_program("p vs a 3 p vg a") == "1111"
        assert run_program("p vg missing") == "0"


class TestFunctions:
    def test_identity(self) -> None:
        # F id f - .f returns the argument without calling it
        assert run_program("F id f - .f\np id 7") == "111"

    def test_not(self) -> None:
        # the wiki's not: eq x eq .i .eq
        assert run_program("F not x - eq x eq .i .eq\np not 0") == "1"
        assert run_program("F not x - eq x eq .i .eq\np not 1") == "0"

    def test_call_bound_function(self) -> None:
        # c .p 5 binds a=p, b=5 and calls p 5
        assert run_program("F c a b - a b\np c .p 5") == "101101"

    def test_nested_call(self) -> None:
        # f g x y is f(g(x), y): p takes one arg, so p p 5 prints twice
        assert run_program("p p 5") == "101101"

    def test_reference_a_definition_by_name(self) -> None:
        # .name outside a call returns the function itself (a def here)
        assert run_program("F f x - x\np .f") == "f"

    def test_dot_function_as_a_call(self) -> None:
        # .name at the top level is a call site for the following tokens
        assert run_program("F add a b - p a p b\n.add 1 2") == "110"


class TestRecursion:
    def test_self_call_through_lazy_if(self) -> None:
        # loop halves x each call (via fb) until it reaches 0, printing
        # each value along the way; the recursive call sits inside i's
        # lazy second branch, not at a "statement" position
        code = "F loop x - p x i x loop fb x 0\nloop 0b1000"
        assert run_program(code) == "10001001010"

    def test_deep_recursion_no_longer_capped(self) -> None:
        """A correct, terminating recursion past Python's default 1000-frame
        limit completes, since a call pushes an explicit frame instead of
        recursing natively.
        """
        depth = 2000
        lines = []
        for i in range(depth):
            if i + 1 < depth:
                lines.append(f"F f{i} x - f{i + 1} x")
            else:
                lines.append(f"F f{i} x - p x")
        lines.append("f0 1")
        assert run_program("\n".join(lines)) == "1"


class TestPartialApplication:
    def test_prints_a_partial_application_by_name(self) -> None:
        # p i 5 is a partial of i with only its condition bound; p prints "i.."
        assert run_program("p i 5") == "i.."

    def test_partial_returned_by_a_function_completes_at_top_level(self) -> None:
        # F f - i 5 returns a partial of i; the trailing 1 2 fill its branches
        assert run_program("F f - i 5\nf 1 2") == ""

    def test_i_branch_scanning_off_the_end(self) -> None:
        # the chosen branch's scan may run past the last token (a partial)
        assert run_program("i 1 p") == ""


class TestValues:
    def test_print_a_bare_name_prints_it_as_a_string(self) -> None:
        # an undefined trailing identifier is a string value, printed as text
        assert run_program("p abc") == "abc"

    def test_blank_lines_are_ignored(self) -> None:
        assert run_program("p 5\n\np 6") == "101110"


class TestErrors:
    def test_redefinition_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="redefined"):
            run_program("F f x - x\nF f y - y")

    def test_undefined_function_halts(self) -> None:
        with pytest.raises(HaltError, match="undefined"):
            run_program("nosuch 1")

    def test_definition_needs_dash(self) -> None:
        with pytest.raises(ValueError, match="'-'"):
            run_program("F f x x")

    def test_bit_builtin_on_a_function_halts(self) -> None:
        # lb of a function value is not a number
        with pytest.raises(HaltError, match="expected a number"):
            run_program("lb .p")


class TestMachine:
    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.other.lamfunc import _Machine

        machine = _Machine("p 5", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == "101"
        machine.step()  # stepping a halted machine is a no-op
        assert machine.io.getvalue() == "101"

    def test_referencing_an_undefined_function_halts(self) -> None:
        """``.name`` builds a function value, so an unknown name has no arity."""
        with pytest.raises(HaltError) as caught:
            run_program("p .nope")
        assert str(caught.value) == "calling undefined function 'nope'"


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.other.lamfunc import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "p 5"
