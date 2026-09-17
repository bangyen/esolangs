"""Threading arguments through a call, and what comes back."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.forbin import run
from tests.interpreters.forbin_support import run_program


class TestDiscardTarget:
    """``_`` as an assignment target evaluates the value and drops it."""

    def test_discard_in_a_paired_assignment(self) -> None:
        """The remaining name still takes the value opposite *its* position.

        Both targets are assigned by position, so the ``_`` consumes the
        first value and ``x`` the second rather than the first surviving
        into it.
        """
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
        """Each of the four places a name is bound must skip ``_``.

        The sentinel is compared in four separate places -- broadcast
        assignment, paired assignment, the step machine's ``for`` row
        binder, and the recursive evaluator's row binder -- and a test
        that reaches only one of them leaves the other three free to stop
        honouring ``_`` unnoticed.  Each program below is the witness for
        exactly one site: breaking that site alone makes it print
        ``\x01`` instead of halting, and breaking any other leaves it
        halting.

        The last two run their loop inside an *expression-position* call,
        which is evaluated recursively rather than by pushing a frame --
        the only route to the recursive binder.
        """
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


class TestCallingANonFunction:
    """A call whose callee resolves to a bit rather than to a function.

    An undeclared name is rejected earlier, as an unknown identifier, so
    reaching the "not a function" check needs a callee that *does* resolve
    -- a local holding a bit -- rather than one that does not.
    """

    def test_calling_a_local_with_arguments(self) -> None:
        with pytest.raises(HaltError, match="called value is not a function"):
            run_program("main { y = 1; y 1,0; }")

    def test_calling_a_local_without_arguments(self) -> None:
        with pytest.raises(HaltError, match="called value is not a function"):
            run_program("main { y = 1; y; }")


class TestArgumentThreading:
    r"""Programs that notice ``_eval``'s arguments going astray.

    A mutation run left 216 survivors, and half of them replace one
    argument of ``_eval(node, frame, globals_, reader, depth)`` with
    ``None`` at one call site.  Such an edit is invisible unless something
    that *consumes* that argument is evaluated in that syntactic position:

        ``globals_``  a reference to a top-level function
        ``reader``    an ``in``
        ``frame``     a local variable
        ``depth``     a nested call, which increments it

    and the consuming construct has to sit **at** the position rather than
    be assigned to a local first -- reading a local forces ``frame``, not
    whatever filled it.  So each program below puts one forcing construct
    in one place a value can appear: a range bound, an iteration pattern,
    a call argument, an ``out`` argument, a ``!``, a return.
    """

    def test_a_call_returning_a_call(self) -> None:
        """``globals_`` and ``depth`` threaded through nested returns.

        ``f`` returns the result of calling ``one``, so the return value
        is evaluated in a frame one deeper than the call that produced it.
        """
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

    def test_a_call_opens_a_range_through_not(self) -> None:
        r"""``!`` is how a call reaches the *start* of a range.

        ``for i:(one 0)..1`` does not parse -- a leading ``(`` is claimed
        by the iteration-list branch of ``_for_spec`` -- but ``!`` is read
        by ``_value``, where ``(`` builds a call.  So ``!(zero 0)`` both
        parses and evaluates a call in start position, which no other
        program here reaches.  The same route carries an ``in``.
        """
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\nzero { return 0; }\n"
                "main {\n for i:!(zero 0)..1 { g i; }\n}\n"
            )
            == "A"
        )
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\nmain {\n for i:!(in 0)..1 { g i; }\n}\n",
                "\x00",
            )
            == "A"
        )
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\none { return 1; }\n"
                "main {\n for i:0..!(one 0) { g i; }\n}\n"
            )
            == "@"
        )

    def test_a_call_at_the_remaining_positions(self) -> None:
        """The call twins of the ``in`` cases: argument, pattern, multi-RHS.

        A call and an ``in`` force different arguments through the same
        slot -- ``globals_`` and ``depth`` for the call, ``reader`` for the
        input -- so each position needs both.
        """
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\none { return 1; }\nmain { g (one 0); }\n"
            )
            == "A"
        )
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\none { return 1; }\n"
                "main {\n for i:((one 0)) { g i; }\n}\n"
            )
            == "A"
        )
        assert (
            run_program(
                "one { return 1; }\n"
                "main {\n a,b = (one 0),(one 0);\n out 0,1,0,0,0,0,b,a;\n}\n"
            )
            == "C"
        )

    def test_input_read_at_each_position(self) -> None:
        """``in`` at the position, not assigned to a local first.

        Binding the byte to a local and using the local forces ``frame``;
        only an ``in`` sitting in the slot forces the bit reader through
        it.
        """
        assert run_program("main { out 0,1,0,0,0,0,0,(in 0); }\n", "\x01") == "@"
        assert run_program("main { out 0,1,0,0,0,0,0,!(in 0); }\n", "\x00") == "A"
        assert (
            run_program("g x { out 0,1,0,0,0,0,0,x; }\nmain { g (in 0); }\n", "\x01")
            == "@"
        )
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\nmain {\n for i:0..(in 0) { g i; }\n}\n",
                "\x01",
            )
            == "@"
        )
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\nmain {\n for i:((in 0)) { g i; }\n}\n",
                "\x01",
            )
            == "@"
        )
        assert (
            run_program(
                "f { return (in 0); }\nmain {\n a = (f 0);\n out 0,1,0,0,0,0,0,a;\n}\n",
                "\x01",
            )
            == "@"
        )
        assert (
            run_program(
                "main {\n a,b = (in 0),(in 0);\n out 0,1,0,0,0,0,b,a;\n}\n", "\x01\x01"
            )
            == "@"
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
        """``*`` doubles the row count, and the columns are independent.

        One wildcard cannot tell a product over the wildcard *count* from
        a product over a fixed repeat, nor the order the expanded columns
        are filled in; two can.
        """
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\n"
                "main {\n for (i,j):((*,*)) { g i; g j; }\n}\n"
            )
            == "@@@AA@AA"
        )

    def test_arity_mismatches_are_tolerated(self) -> None:
        """Extra arguments are dropped and missing ones default to zero.

        The zips that bind parameters and loop variables are deliberately
        not ``strict``; a mismatch is a documented case, not an error.
        """
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


class TestThreadedResources:
    """Every evaluator argument, loaded in every position that forwards it.

    ``_eval``/``_exec_stmt``/``_call`` thread four things through every
    recursive step -- the frame, the globals, the bit reader, and the call
    depth -- and a suite whose programs never *use* one of them in a given
    position cannot notice that position forwarding the wrong thing.  Each
    program below puts a load on exactly one resource:

    ``(in 0)`` needs the reader, a bare local name needs the frame, a call
    needs the globals, and a call nested inside an expression-position
    call needs the depth, which is read once as ``depth + 1``.

    The positions matter as much as the loads.  A loop bound, a call
    argument, an assignment right-hand side, and an iteration pattern are
    four separate forwarding sites, and the whole set is duplicated between
    the step machine and the recursive evaluator an expression-position
    call runs in.
    """

    def test_the_reader_reaches_every_position_that_can_read(self) -> None:
        """``(in 0)`` in each spot that forwards the reader.

        ``in`` yields one bit, most significant first, so the stdin byte
        here is ``\xff`` -- a leading 1.  That matters: a leading 0 would
        make the read indistinguishable from an unset variable, and the
        test would pass against a reader that was never consulted.
        """
        assert (
            run_program("main { for i:0..(in 0) { out 0,1,0,0,0,0,0,i; } }", "\xff")
            == "@A"
        )
        assert (
            run_program("g a { out 0,1,0,0,0,0,0,a; }\nmain { g (in 0); }\n", "\xff")
            == "A"
        )
        assert run_program("main { x = (in 0); out 0,1,0,0,0,0,0,x; }", "\xff") == "A"
        assert (
            run_program("main { for i:((in 0)) { out 0,1,0,0,0,0,0,i; } }", "\xff")
            == "A"
        )
        # inside an expression-position call, which runs recursively
        assert (
            run_program(
                "g { x = (in 0); return x; }\n"
                "main { y = (g 0); out 0,1,0,0,0,0,0,y; }\n",
                "\xff",
            )
            == "A"
        )

    def test_the_frame_reaches_every_position_that_reads_a_local(self) -> None:
        """A bare local name in each spot that forwards the frame."""
        assert (
            run_program("main { n = 1; for i:0..n { out 0,1,0,0,0,0,0,i; } }") == "@A"
        )
        assert (
            run_program("g a { out 0,1,0,0,0,0,0,a; }\nmain { n = 1; g n; }\n") == "A"
        )
        assert (
            run_program(
                "g { n = 1; return n; }\nmain { y = (g 0); out 0,1,0,0,0,0,0,y; }\n"
            )
            == "A"
        )

    def test_the_globals_reach_every_position_that_can_call(self) -> None:
        """A call in each spot that forwards the function table."""
        assert (
            run_program(
                "h { return 1; }\nmain { for i:0..(h 0) { out 0,1,0,0,0,0,0,i; } }\n"
            )
            == "@A"
        )
        assert (
            run_program(
                "h { return 1; }\ng a { out 0,1,0,0,0,0,0,a; }\nmain { g (h 0); }\n"
            )
            == "A"
        )

    def test_an_argument_list_carries_its_own_resources(self) -> None:
        """``_eval``'s argument list is a separate forwarding site.

        A call node evaluates its callee, then its arguments, then calls.
        Those are three lines, each forwarding the same four things, and
        the argument list was the one no program loaded: every call in the
        suite passed a literal or a bare name, which needs neither the
        globals nor the reader.

        An argument that is *itself* a call needs the globals; an argument
        that reads input needs the reader.  Both are wrapped in an
        expression-position call so the recursive evaluator is what runs
        them.
        """
        # an argument that is a call: needs the function table
        assert (
            run_program(
                "k { return 1; }\nh a { return a; }\n"
                "g { x = (h (k 0)); return x; }\n"
                "main { y = (g 0); out 0,1,0,0,0,0,0,y; }\n"
            )
            == "A"
        )
        # an argument that reads input: needs the reader
        assert (
            run_program(
                "h a { return a; }\ng { x = (h (in 0)); return x; }\n"
                "main { y = (g 0); out 0,1,0,0,0,0,0,y; }\n",
                "\xff",
            )
            == "A"
        )

    def test_a_call_nested_in_a_call_is_what_reads_the_depth(self) -> None:
        """``depth`` is forwarded everywhere and read once, as ``depth + 1``.

        That single read is in ``_call``, so it needs a call reached from
        *inside* another call's recursive evaluation -- one level of
        expression-position nesting is not enough to notice a depth that
        arrived as something other than a number.
        """
        assert (
            run_program(
                "h { return 1; }\ng { x = (h 0); return x; }\n"
                "main { y = (g 0); out 0,1,0,0,0,0,0,y; }\n"
            )
            == "A"
        )
        assert (
            run_program(
                "k { return 1; }\nh { x = (k 0); return x; }\n"
                "g { x = (h 0); return x; }\n"
                "main { y = (g 0); out 0,1,0,0,0,0,0,y; }\n"
            )
            == "A"
        )


class TestWildcardExpansion:
    """``*`` in an iteration pattern expands to every bit combination.

    The expansion is written twice -- once in ``_for_rows`` for the step
    machine, once inside ``_exec_stmt`` for the recursive evaluator -- and
    each copy walks the pattern with a *separate* cursor ``w`` into the
    combination tuple.  A wrong cursor is invisible with fewer than three
    wildcards (with two, the only wrong index still lands in range and the
    rows come out permuted rather than short), and invisible in the
    recursive copy unless the loop is inside an expression-position call.
    """

    def test_three_wildcards_expand_to_eight_rows_in_order(self) -> None:
        """Three ``*`` need a cursor that reaches index two.

        With one or two wildcards a cursor that resets or counts backwards
        still indexes a valid element; the third column is what makes a
        wrong ``w`` either repeat a bit or run off the tuple.
        """
        code = (
            "g a, b, c { out 0,1,0,0,0,0,0,a; out 0,1,0,0,0,1,0,b; "
            "out 0,1,0,0,1,0,0,c; }\n"
            "main { for (i,j,k):((*,*,*)) { g i, j, k; } }\n"
        )
        assert run_program(code) == "@DH@DI@EH@EIADHADIAEHAEI"

    def test_the_recursive_copy_expands_too(self) -> None:
        """The same expansion, reached through an expression-position call.

        ``_exec_stmt`` carries its own copy of the wildcard walk, and a
        top-level ``for`` never runs it -- the step machine builds those
        rows in ``_for_rows`` instead.  These loops return on their first
        row, so what they pin is that a row was produced at all and that
        the pattern's fixed columns kept their values.
        """
        assert (
            run_program(
                "g { for (i,j):((*,*)) { return 0; } return 1; }\n"
                "main { x = (g 0); out 0,1,0,0,0,0,0,x; }\n"
            )
            == "@"
        )
        # a fixed column either side of the wildcard: the cursor must not
        # consume one of them
        assert (
            run_program(
                "g { for (i,j,k):((1,*,0)) { return j; } return 1; }\n"
                "main { x = (g 0); out 0,1,0,0,0,0,0,x; }\n"
            )
            == "@"
        )


class TestCallResultDefaults:
    """What a call evaluates to when it returns nothing.

    Both are ``0``, and both were only ever used in statement position --
    where the value is discarded, so a mutant returning ``1`` changed
    nothing observable.  Assigning the call's value is what reads it.
    """

    def test_a_function_that_returns_nothing_evaluates_to_zero(self) -> None:
        assert run_program("g { }\nmain { x = (g 0); out 0,1,0,0,0,0,0,x; }\n") == "@"

    def test_out_evaluates_to_zero(self) -> None:
        """``out`` is a call like any other and yields a value."""
        assert (
            run_program("main { x = (out 0,1,0,0,0,0,0,1); out 0,1,0,0,0,0,0,x; }")
            == "A@"
        )


class TestPairedLengthsAreNotChecked:
    """Forbin pairs by position and stops at the shorter side.

    Five ``zip`` calls bind names to values -- parameters to arguments
    (twice, once per call path), targets to right-hand sides, and loop
    variables to a row (twice again).  Each passes ``strict=False``, and
    tightening any one of them to ``strict=True`` turns a length mismatch
    from a tolerated program into a crash.  The suite ran no program whose
    two sides differed, so every one of those edits was invisible.
    """

    def test_arity_mismatch_is_tolerated_on_both_call_paths(self) -> None:
        """A statement call and an expression call bind arguments separately."""
        # statement-position call: too few arguments, then too many
        assert run_program("g a, b { out 0,1,0,0,0,0,0,a; }\nmain { g 1; }\n") == "A"
        assert run_program("g a { out 0,1,0,0,0,0,0,a; }\nmain { g 1, 0; }\n") == "A"
        # expression-position call, which binds through the other zip
        assert (
            run_program(
                "g a { return a; }\nmain { x = (g 1, 0); out 0,1,0,0,0,0,0,x; }\n"
            )
            == "A"
        )

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
