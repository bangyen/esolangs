"""Threading arguments through a call, and what comes back."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.forbin import run
from tests.interpreters.forbin_support import run_program


class TestDiscardTarget:
    """``_`` as an assignment target evaluates the value and drops it."""

    def test_discard_in_a_paired_assignment(self) -> None:
        """The remaining name still takes the value opposite *its* position."""
        code = "main { _, x = 1, 0; out 0,0,0,0,0,0,0,x; }"
        assert run_program(code) == "\x00"

        code = "main { x, _ = 1, 0; out 0,0,0,0,0,0,0,x; }"
        assert run_program(code) == "\x01"

    def test_discard_in_a_broadcast_assignment(self) -> None:
        """One value for several targets skips the ``_`` and fills the rest."""
        code = "main { _, x = 1; out 0,0,0,0,0,0,0,x; }"
        assert run_program(code) == "\x01"

    def test_discard_is_not_readable_afterwards(self) -> None:
        """``_`` is dropped rather than stored, so reading it is an error."""
        with pytest.raises(HaltError, match="undeclared identifier"):
            run_program("main { _ = 1; out 0,0,0,0,0,0,0,_; }")

    def test_every_binding_site_honours_the_discard(self) -> None:
        """Each of the four places a name is bound must skip ``_``."""
        for code in (
            # broadcast assignment
            "main { _ = 1; out 0,0,0,0,0,0,0,_; }",
            # paired assignment, where the value comes by position
            "main { _, x = 1, 0; out 0,0,0,0,0,0,0,_; }",
            # the step machine's row binder, range and iteration spellings
            "main { for _:0..1 { } out 0,0,0,0,0,0,0,_; }",
            "main { for _:(0, 1) { } out 0,0,0,0,0,0,0,_; }",
            # the recursive binder, reached through an expression-position call
            "g { for _:0..1 { } return _; }\nmain { x = (g 0); }\n",
            "g { for _:(0, 1) { } return _; }\nmain { x = (g 0); }\n",
        ):
            with pytest.raises(HaltError) as caught:
                run(code, ScriptedIO(""))
            assert str(caught.value) == "undeclared identifier '_'"


class TestArgumentThreading:
    r"""Programs that notice ``_eval``'s arguments going astray."""

    def test_a_call_returning_a_call(self) -> None:
        """``globals_`` and ``depth`` threaded through nested returns."""
        assert (
            run_program(
                "one { return 1; }\nf { return (one 0); }\n"
                "main {\n a = (f 0);\n out 0,1,0,0,0,0,0,a;\n}\n"
            )
            == "A"
        )

    def test_a_call_as_a_range_bound(self) -> None:
        """A ``for`` bound is a value, so it may itself be a call."""
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\none { return 1; }\n"
                "main {\n for i:0..(one 0) { g i; }\n}\n"
            )
            == "@A"
        )

    def test_a_call_in_a_nested_loop_bound(self) -> None:
        """The inner bound is re-evaluated on every row of the outer loop."""
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\none { return 1; }\n"
                "main {\n for i:0..1 {\n  for j:0..(one 0) { g j; }\n }\n}\n"
            )
            == "@A@A"
        )

    def test_a_nested_definition_reads_the_enclosing_frame(self) -> None:
        """``_lookup`` walks ``frame.parent`` until it finds the name."""
        assert (
            run_program(
                "main {\n a = 1;\n inner { out 0,1,0,0,0,0,0,a; }\n inner 0;\n}\n"
            )
            == "A"
        )
        assert (
            run_program(
                "main {\n a = 1;\n mid {\n  deep { out 0,1,0,0,0,0,0,a; }\n"
                "  deep 0;\n }\n mid 0;\n}\n"
            )
            == "A"
        )

    def test_two_wildcards_expand_to_four_rows(self) -> None:
        """``*`` doubles the row count, and the columns are independent."""
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\n"
                "main {\n for (i,j):((*,*)) { g i; g j; }\n}\n"
            )
            == "@@@AA@AA"
        )

    def test_arity_mismatches_are_tolerated(self) -> None:
        """Extra arguments are dropped and missing ones default to zero."""
        assert run_program("f x,y { out 0,1,0,0,0,0,y,x; }\nmain { f 1; }\n") == "A"
        assert run_program("f x { out 0,1,0,0,0,0,0,x; }\nmain { f 1,1,1; }\n") == "A"
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\n"
                "main {\n for (i,j):((0,1),(1)) { g i; }\n}\n"
            )
            == "@A"
        )

    def test_a_loop_variable_named_underscore_stays_unbound(self) -> None:
        """``_`` is the discard name, so it must not enter the frame."""
        with pytest.raises(HaltError, match="undeclared identifier '_'"):
            run(
                "main {\n for _:0..0 { out 0,1,0,0,0,0,0,0; }\n"
                " out 0,1,0,0,0,0,0,_;\n}\n",
                ScriptedIO(""),
            )


class TestCallResultDefaults:
    """What a call evaluates to when it returns nothing."""

    def test_a_function_that_returns_nothing_evaluates_to_zero(self) -> None:
        assert run_program("g { }\nmain { x = (g 0); out 0,1,0,0,0,0,0,x; }\n") == "@"

    def test_out_evaluates_to_zero(self) -> None:
        """``out`` is a call like any other and yields a value."""
        assert (
            run_program("main { x = (out 0,1,0,0,0,0,0,1); out 0,1,0,0,0,0,0,x; }")
            == "A@"
        )


class TestPairedLengthsAreNotChecked:
    """Forbin pairs by position and stops at the shorter side."""

    def test_an_assignment_may_have_uneven_sides(self) -> None:
        """Extra targets stay unset and extra values are dropped."""
        assert run_program("main { a, b = 1, 0, 1; out 0,1,0,0,0,0,0,a; }") == "A"
        assert run_program("main { a, b, c = 1, 0; out 0,1,0,0,0,0,0,a; }") == "A"

    def test_a_row_narrower_than_its_variable_list_is_tolerated(self) -> None:
        """Two loop variables over one-wide rows leave the second unbound."""
        assert (
            run_program("main { for (i,j):((0),(1)) { out 0,1,0,0,0,0,0,i; } }") == "@A"
        )
        # and again through the recursive evaluator
        assert (
            run_program(
                "g { for (i,j):((0),(1)) { return 0; } return 0; }\n"
                "main { x = (g 0); out 0,1,0,0,0,0,0,x; }\n"
            )
            == "@"
        )
