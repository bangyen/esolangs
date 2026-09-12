r"""Unit tests for the Lamfunc interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.lamfunc import run
from tests.interpreters.contract import SnapshotContract
from tests.raises import raises_message


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

    def test_combining_bits_with_a_zero_operand(self) -> None:
        r"""``cb`` concatenates unless *both* operands are zero."""
        assert run_program("p cb 0 1") == "1"
        assert run_program("p cb 1 0") == "10"
        assert run_program("p cb 5 0") == "1010"
        assert run_program("p cb 0 0") == "0"

    def test_printing_a_function_reference(self) -> None:
        r"""``p .f`` prints the function's name once."""
        assert run_program("p .p") == "p"

    def test_a_stored_variable_reads_back_as_its_value(self) -> None:
        r"""``vs`` stores a value under a name, and the name resolves to it."""
        assert run_program("vs 'a' 1\np 'a'") == "1"

    def test_a_binary_literal_needs_digits_and_only_binary_ones(self) -> None:
        r"""``0b`` alone is a name, and so is ``0b`` followed by a 2."""
        assert run_program("p 0b") == "0b"
        assert run_program("p 0b2") == "0b2"
        assert run_program("p 0b12") == "0b12"
        assert run_program("p 0b0") == "0"

    def test_an_unknown_name_in_a_skipped_branch_is_one_token(self) -> None:
        r"""``_scan`` sizes an unevaluated branch without running it."""
        assert run_program("p i 1 3 foo p 7") == "11111"  # 3 then 7, in binary.
        with raises_message(HaltError, "calling undefined function 'foo'"):
            run_program("p i 0 3 foo p 7")

    def test_equality(self) -> None:
        assert run_program("p eq 1 1") == "1"
        assert run_program("p eq 1 2") == "0"

    def test_if_selects_branch(self) -> None:
        assert run_program("p i 1 7 8") == "111"
        assert run_program("p i 0 7 8") == "1000"

    def test_if_is_lazy(self) -> None:
        # the unchosen branch's p must.
        assert run_program("p i 1 3 p 9") == "11"

    def test_combine_bits(self) -> None:
        # 0b10 and 0b110 combine to.
        assert run_program("p cb 2 6") == "10110"

    def test_last_and_all_but_last_bit(self) -> None:
        assert run_program("p lb 5") == "1"
        assert run_program("p fb 5") == "10"

    def test_set_and_get_variable(self) -> None:
        assert run_program("p vs a 3 p vg a") == "1111"
        assert run_program("p vg missing") == "0"


class TestFunctions:
    def test_call_parameters_shadow_and_restore_variables(self) -> None:
        r"""A call temporarily binds its parameter without losing the caller's."""
        code = "F f a - p a\nvs a 3\nf 7\np vg a"
        assert run_program(code) == "11111"

    def test_identity(self) -> None:
        # F id f - .f returns the.
        assert run_program("F id f - .f\np id 7") == "111"

    def test_not(self) -> None:
        # the wiki's not: eq x eq .i.
        assert run_program("F not x - eq x eq .i .eq\np not 0") == "1"
        assert run_program("F not x - eq x eq .i .eq\np not 1") == "0"

    def test_call_bound_function(self) -> None:
        # c .p 5 binds a=p, b=5 and.
        assert run_program("F c a b - a b\np c .p 5") == "101101"

    def test_nested_call(self) -> None:
        # f g x y is f(g(x), y): p.
        assert run_program("p p 5") == "101101"

    def test_reference_a_definition_by_name(self) -> None:
        # .name outside a call returns.
        assert run_program("F f x - x\np .f") == "f"

    def test_dot_function_as_a_call(self) -> None:
        # .name at the top level is a.
        assert run_program("F add a b - p a p b\n.add 1 2") == "110"


class TestRecursion:
    def test_self_call_through_lazy_if(self) -> None:
        # loop halves x each call (via.
        # each value along the way; the.
        # lazy second branch, not at a.
        code = "F loop x - p x i x loop fb x 0\nloop 0b1000"
        assert run_program(code) == "10001001010"

    def test_deep_recursion_no_longer_capped(self) -> None:
        r"""A correct, terminating recursion past Python's default 1000-frame."""
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
    def test_a_returned_one_argument_partial_absorbs_the_next_top_level_token(
        self,
    ) -> None:
        r"""A returned ``p`` partial consumes the remaining main-program token."""
        assert run_program("F f x - p\nf 1 8") == "1000"

    def test_prints_a_partial_application_by_name(self) -> None:
        # p i 5 is a partial of i with.
        assert run_program("p i 5") == "i.."

    def test_partial_returned_by_a_function_completes_at_top_level(self) -> None:
        # F f - i 5 returns a partial.
        assert run_program("F f - i 5\nf 1 2") == ""

    def test_i_branch_scanning_off_the_end(self) -> None:
        # the chosen branch's scan may.
        assert run_program("i 1 p") == ""


class TestValues:
    def test_print_a_bare_name_prints_it_as_a_string(self) -> None:
        # an undefined trailing.
        assert run_program("p abc") == "abc"

    def test_blank_lines_are_ignored(self) -> None:
        assert run_program("p 5\n\np 6") == "101110"


class TestErrors:
    def test_the_rejection_messages_are_exact(self) -> None:
        r"""Each message is pinned whole, and names what it is complaining."""
        with raises_message(ValueError, "function 'f' redefined"):
            run_program("F f x - x\nF f y - y")

        with raises_message(ValueError, "function definition must contain '-'"):
            run_program("F f x x")

        for code in ("nosuch 1", ".nosuch"):
            with pytest.raises(HaltError) as caught:
                run_program(code)
            assert str(caught.value) == "calling undefined function 'nosuch'"

        with pytest.raises(HaltError) as caught:
            run_program("lb .p")
        assert str(caught.value).startswith("expected a number, got ")


class TestMachine:
    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.other.lamfunc import _Machine

        machine = _Machine("p 5", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == "101"
        machine.step()  # stepping a halted machine is.
        assert machine.io.getvalue() == "101"

    def test_referencing_an_undefined_function_halts(self) -> None:
        r"""``.name`` builds a function value, so an unknown name has no arity."""
        with pytest.raises(HaltError) as caught:
            run_program("p .nope")
        assert str(caught.value) == "calling undefined function 'nope'"


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.other.lamfunc import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract):
    r"""The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "p 5"
