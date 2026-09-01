"""Unit tests for the COD interpreter."""

import pytest

from esolangs.interpreters.grid_based.cod import _Machine, run
from esolangs.interpreters.io import IO, ScriptedIO


def run_and_capture(code: str, stdin: str = "", limit: int = 1000) -> str:
    io = ScriptedIO(stdin)
    run(code, io, limit=limit)
    return io.getvalue()


class _FirstChoiceRNG:
    def choice(self, options: list[str]) -> str:
        return options[0]


class _LastChoiceRNG:
    """Picks the *last* option, so a choice is visible as a direction.

    ``_FirstChoiceRNG`` agrees with "take ``options[0]``" wherever the
    interpreter might skip the draw, which hides whether the draw happened
    at all; this one disagrees.
    """

    def choice(self, options: list[str]) -> str:
        return options[-1]


class _CountingRNG:
    """Records how often it was consulted, and which options were offered."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def choice(self, options: list[str]) -> str:
        self.calls.append(list(options))
        return options[0]


class TestCOD:
    def test_increment_and_output(self) -> None:
        # ')' increments, '---' on the right edge prints and removes
        assert run_and_capture("~~~~~\n~>))---") == "2"

    def test_decrement_and_output(self) -> None:
        assert run_and_capture("~~~~~~\n~>)))((---") == "1"

    def test_decrement_steps_down_from_wherever_it_starts(self) -> None:
        """``(`` subtracts one; it does not put a value there.

        Every other program decrements from 3 to 1, where subtracting and
        assigning 1 land on the same number.  Stopping at 0 and at -1
        separates them, and the negative also shows that a cod's value is
        signed rather than clamped.
        """
        assert run_and_capture("~~~~~~~\n~>))((---") == "0"
        assert run_and_capture("~~~~~\n~>(---") == "-1"

    def test_less_than_removes_zero_valued_cod(self) -> None:
        # value 0 hits '<' and is removed; no cod remains, no output
        assert run_and_capture("~~~~~~\n~><----") == ""

    def test_less_than_passes_nonzero_cod(self) -> None:
        assert run_and_capture("~~~~~~~\n~>)<---") == "1"

    def test_bare_dash_removes_the_cod(self) -> None:
        # a lone '-' (not part of a left/right-edge run of exactly 3)
        # removes the cod outright, per the wiki's "Remove the cod"
        assert run_and_capture("~~~~~~\n~>-)---") == ""

    def test_a_dot_run_that_is_not_a_read(self) -> None:
        """Only a run of exactly three touching an edge reads; others are water.

        A column with two dots is the wrong length, so the scan rejects it
        and moves on rather than treating either cell as an input command --
        the cod crosses them and the program ends with nothing read.
        """
        assert run_and_capture("~~~~~\n~>).\n~~.~~") == ""

    def test_a_three_dot_run_off_both_edges_is_not_a_read(self) -> None:
        """Three dots are only a read where the run reaches the top or bottom."""
        from esolangs.interpreters.grid_based.cod import _edge_dot_cells

        assert _edge_dot_cells(["x", ".", ".", ".", "x"]) == set()
        assert _edge_dot_cells([".", ".", ".", "x"]) == {(0, 0), (1, 0), (2, 0)}

    def test_a_dot_run_against_the_bottom_edge_is_a_read(self) -> None:
        """A run that *ends* at the last row reads, as one starting at the
        first row does.

        Every dot run the suite scans begins at row 0, where the run's
        start index and its length coincide with the numbers the bottom
        arm compares -- so a run reached only from below, whose cells sit
        at rows the scan must offset to, went uncovered.
        """
        from esolangs.interpreters.grid_based.cod import _edge_dot_cells

        assert _edge_dot_cells(["x", ".", ".", "."]) == {(1, 0), (2, 0), (3, 0)}
        assert _edge_dot_cells(["x", "x", "x", ".", ".", "."]) == {
            (3, 0),
            (4, 0),
            (5, 0),
        }
        # and the run is live: the cod turns up the column, reads, and prints
        code = "\n".join(["~~~~~~", "~~.~~~", "~~.~~~", "~>.---"])
        assert run_and_capture(code, stdin="7", limit=60) == "7"

    def test_a_dash_run_against_the_left_edge_prints(self) -> None:
        """``---`` starting at column 0 is an output, as one ending at the
        right edge is.

        Every printing program in the suite puts its run at the right edge,
        so the scan's left-edge arm -- and with it the column the run
        starts on -- was never the reason a cod printed.
        """
        from esolangs.interpreters.grid_based.cod import _edge_dash_cells

        assert _edge_dash_cells(["---~~~"]) == {(0, 0), (0, 1), (0, 2)}
        # the cod's only exit is west, so it passes ')' and enters the run
        code = "\n".join(["~~~~~~", "---)>~", "~~~~~~"])
        assert run_and_capture(code, limit=40) == "1"

    def test_triple_dash_not_on_edge_is_three_removals(self) -> None:
        # '---' with water on both sides is three plain '-' removals, not
        # print+remove; the cod dies on the first one, so nothing prints
        assert run_and_capture("~~~~~~~\n~> ---  \n~~~~~~~") == ""

    def test_duplicate_at_two_way_fork_splits_forward_and_side(self) -> None:
        # a '+' at a T with the entry excluded (2 remaining branches) sends
        # one copy each way; both carry the pre-fork value (1, so the south
        # copy survives its '<' gate), and each reaches its own edge '---'
        # -- the east copy prints immediately (value 1), the south copy
        # passes one more ')' before its own edge (value 2)
        code = "\n".join(
            [
                "~~~~~~~",
                "~>)+---",
                "~~~<~~~",
                "~~~)---",
                "~~~~~~~",
            ]
        )
        out = run_and_capture(code)
        # Outputs are not separated, so the two prints run together; the
        # order is whichever cod reaches its edge first, which this test
        # does not pin, so compare the multiset of characters.
        assert sorted(out) == ["1", "2"]

    def test_reflect_upward_motion_when_nonzero(self) -> None:
        # '_' reflects an upward-moving nonzero cod back down; the value is
        # 1 when it hits '_' (from the ')' passed on the way up), so it
        # turns south and continues through the same ')' again on the way
        # back, reaching value 2
        code = "\n".join(["~~~~~", "~~~~~", "~_~~~", "~)~~~", "~>~~~"])
        io = ScriptedIO("")
        m = _Machine(code, io)
        m.step()  # (4,1,N,0) -> (3,1,N,1): passes ')'
        m.step()  # (3,1,N,1) -> (2,1,S,1): hits '_' with nonzero, reflects
        cod = m.cods[0]
        assert (cod.r, cod.c, cod.d, cod.value) == (2, 1, "S", 1)

    def test_reflect_is_noop_when_zero(self) -> None:
        # '_' hit going up with value 0 does nothing: the cod continues
        # past it (since forward is open, per the standard motion rule),
        # rather than reflecting
        code = "\n".join(["~~~~~", "~~~~~", "~_~~~", "~ ~~~", "~>~~~"])
        io = ScriptedIO("")
        m = _Machine(code, io)
        m.step()  # (4,1,N,0) -> (3,1,N,0)
        m.step()  # (3,1,N,0) -> (2,1,N,0): '_' is a no-op at value 0
        cod = m.cods[0]
        assert (cod.r, cod.c, cod.d, cod.value) == (2, 1, "N", 0)

    def test_truth_machine_zero_halts_with_single_output(self) -> None:
        code = "\n".join(
            [
                " ~.~",
                "~~.~~~~",
                "~>.+---",
                "~~~<~~~",
                "  ~_~~~",
                "  ~+---",
                "  ~ ~~~",
                "  ~~~",
            ]
        )
        assert run_and_capture(code, stdin="0", limit=200) == "0"

    def test_truth_machine_nonzero_loops_forever(self) -> None:
        code = "\n".join(
            [
                " ~.~",
                "~~.~~~~",
                "~>.+---",
                "~~~<~~~",
                "  ~_~~~",
                "  ~+---",
                "  ~ ~~~",
                "  ~~~",
            ]
        )
        out = run_and_capture(code, stdin="1", limit=100)
        assert out.count("1") > 5

    def test_a_grid_with_no_wave_border_is_still_bounded(self) -> None:
        """Off the grid is wall, on every side, even where no ``~`` says so.

        Every other program in the suite draws a wave border, so row 0 and
        column 0 are walls for a reason the bounds check never has to
        supply, and the far edges are never approached at all.  Here the
        cod swims along row 0 from column 0, and each side of the grid is
        the only thing that turns it.
        """
        assert run_and_capture(">))---", limit=40) == "2"
        # ')' in the last column: the probe past it must read as wall, not
        # walk off the end of the row
        assert run_and_capture(">(<)", limit=60) == ""

    def test_column_zero_is_a_cell_a_cod_can_be_sent_to(self) -> None:
        """The leftmost column is inside the grid, not one past its edge.

        The bounds check rejects a negative column, and every wave-bordered
        program makes column 0 a wall anyway -- so a check that also
        rejected column 0 would look the same.  Here it is the start's only
        way out: read as wall, the ``>`` is enclosed and the program never
        runs at all.
        """
        code = "\n".join(["~~~~", "->~~", "~~~~"])
        machine = _Machine(code, IO())
        assert machine._open_dirs(1, 1) == ["W"]
        machine.step()  # west onto the '-', which removes the cod
        assert machine.halted

    def test_a_short_row_is_padded_with_waves(self) -> None:
        """A ragged grid is squared off with wall, not with water.

        Padding is invisible while it only fills cells no cod reaches; a
        start marker whose open side *is* the padding tells the two fills
        apart -- water there would give the cod somewhere to go.
        """
        with pytest.raises(ValueError, match="fully enclosed"):
            run("~~~~\n~>\n~~~~", IO(), limit=5)

    def test_no_start_marker_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="no cod start"):
            run("~~~~~", IO())

    def test_an_empty_program_has_no_start_marker(self) -> None:
        """Code with no rows at all reports the missing ``>``.

        The width of an empty grid is never used, but computing it must
        not itself fail, or the program is rejected for the wrong reason.
        """
        with pytest.raises(ValueError, match="no cod start"):
            run("", IO(), limit=5)

    def test_two_start_markers_is_malformed(self) -> None:
        code = "\n".join(["~~~~~~~", "~> > ~~", "~~~~~~~"])
        with pytest.raises(ValueError, match="multiple cod start"):
            run(code, IO())

    def test_unknown_instruction_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="unknown instruction"):
            run("~>q~", IO())

    def test_an_uppercase_letter_is_no_more_passable_than_a_lowercase_one(
        self,
    ) -> None:
        """The passable set is exactly the characters the language names.

        It is spelled as a string, and a string only ever held the
        operators themselves -- so a rejected character that differs from
        one of them only in case never came through to show the set is
        exact.
        """
        with pytest.raises(ValueError, match="unknown instruction"):
            run("~>X~", IO(), limit=5)

    def test_fully_enclosed_start_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="fully enclosed"):
            run("~~~\n~>~\n~~~", IO())

    def test_the_malformed_messages_read_in_full(self) -> None:
        """Each message entire, not the fragment the tests match on.

        ``match=`` is a substring search, so every assertion above passes
        on a message padded or reworded around the phrase it looks for.
        """
        with pytest.raises(ValueError) as no_start:
            run("~~~~~", IO())
        assert str(no_start.value) == "no cod start marker '>'"

        with pytest.raises(ValueError) as two_starts:
            run("~~~~~~~\n~> > ~~\n~~~~~~~", IO())
        assert str(two_starts.value) == "multiple cod start markers"

        with pytest.raises(ValueError) as enclosed:
            run("~~~\n~>~\n~~~", IO())
        assert str(enclosed.value) == "cod start is fully enclosed"

    def test_deterministic_rng_picks_first_option(self) -> None:
        # at a genuine (non '+') random junction, the injected rng's
        # first-choice policy makes stepping reproducible
        code = "~~~~~\n~   ~\n~>---\n~   ~\n~~~~~"
        machine = _Machine(code, IO(), rng=_FirstChoiceRNG())
        for _ in range(10):
            if machine.halted:
                break
            machine.step()
        assert machine.halted

    def test_the_start_direction_is_drawn_when_more_than_one_is_open(
        self,
    ) -> None:
        """A ``>`` with two ways out asks the chooser, and takes its answer.

        A first-choice chooser agrees with "just take the first open
        direction" wherever the draw might be skipped, so it cannot show
        that a draw happened.  A chooser that answers *last* can.
        """
        code = "\n".join(["~~~~~", "~ > ~", "~~~~~"])
        machine = _Machine(code, IO(), rng=_LastChoiceRNG())
        assert machine._open_dirs(1, 2) == ["E", "W"]
        assert machine.cods[0].d == "W"

    def test_run_hands_its_chooser_to_the_machine(self) -> None:
        """``rng`` reaches the draw, rather than being dropped on the way.

        Nothing else observes the relay: with the argument lost, the run
        falls back to ``secrets`` and still halts, still prints the same
        thing -- the only difference is that the chooser is never asked.
        """
        rng = _CountingRNG()
        run("~~~~~\n~ > ~\n~~~~~", ScriptedIO(), limit=10, rng=rng)
        assert rng.calls == [["E", "W"]]

    def test_step_on_halted_machine_is_noop(self) -> None:
        machine = _Machine("~~~~~\n~><--", IO())
        machine.step()  # cod value 0 hits '<' and dies
        assert machine.halted
        machine.step()  # must not raise
        assert machine.halted

    def test_snapshot_is_hashable_and_stable(self) -> None:
        machine = _Machine("~~~~~\n~>)) --", IO())
        snap1 = machine.snapshot()
        hash(snap1)  # must not raise
        machine.step()
        snap2 = machine.snapshot()
        assert snap1 != snap2

    def test_trailing_blank_lines_are_stripped(self) -> None:
        # a trailing "\n\n" leaves an empty final row, which must not
        # affect grid width or the start scan
        assert run_and_capture("~~~~~~\n~>)---\n\n") == "1"

    def test_trailing_blank_lines_do_not_move_the_bottom_edge(self) -> None:
        """Stripping decides where "bottom" is, so a read depends on it.

        A blank row padded to width is all wall, which changes nothing a
        cod can swim through -- the only thing it moves is the grid's
        height, and the sole rule that reads the height is the bottom arm
        of the dot scan.  Left unstripped, this program's ``...`` no longer
        touches the bottom and the input is never read.
        """
        code = "\n".join(["~~~~~~", "~~.~~~", "~~.~~~", "~>.---"])
        assert run_and_capture(code + "\n\n", stdin="7", limit=60) == "7"

    def test_genuine_random_junction_without_rng_uses_secrets(self) -> None:
        # a real >=2-way fork (not via '+'): forward blocked, both East and
        # West open.  With no rng override, secrets.randbelow drives the
        # choice; run it enough times to be confident both directions are
        # reachable (each is chosen with probability 1/2 per run).
        code = "\n".join(
            [
                "~~~~~~~",
                "~     ~",
                "~ ~ ~ ~",
                "~~~>~~~",
            ]
        )
        seen_dirs = set()
        for _ in range(40):
            machine = _Machine(code, IO())
            machine.step()  # (3,3,N) -> (2,3,N)
            machine.step()  # (2,3,N) -> (1,3,N): enters the junction cell
            machine.step()  # forward (N) blocked: resolves E or W
            seen_dirs.add(machine.cods[0].d)
            if seen_dirs == {"E", "W"}:
                break
        assert seen_dirs == {"E", "W"}

    def test_duplicate_at_dead_end_reverses(self) -> None:
        # '+' landing on a cell whose only open neighbour is the one the
        # cod came from (0 forward branches) reverses, matching a plain
        # dead end
        code = "\n".join(["~~~~~", "~+~~~", "~>~~~"])
        machine = _Machine(code, IO())
        machine.step()
        cod = machine.cods[0]
        assert (cod.r, cod.c, cod.d) == (1, 1, "S")

    def test_a_duplicate_at_a_dead_end_keeps_the_value(self) -> None:
        """The cod ``+`` sends back carries what the cod arrived with.

        Reversing is checked by direction alone, and the cod that reaches
        this dead end in the suite is worth 0 -- which is what a dropped
        value would read as too.  Passing a ``)`` on the way up separates
        them.
        """
        code = "\n".join(["~~~~~", "~+~~~", "~)~~~", "~>~~~"])
        machine = _Machine(code, IO())
        machine.step()  # (3,1,N,0) -> (2,1,N,1): passes ')'
        machine.step()  # (2,1,N,1) -> (1,1,S,1): '+' has no forward branch
        cod = machine.cods[0]
        assert (cod.r, cod.c, cod.d, cod.value) == (1, 1, "S", 1)

    def test_a_cod_starts_at_zero(self) -> None:
        """A cod made without a value is worth 0.

        Every construction the interpreter performs passes one, so the
        default the class documents was never read.
        """
        from esolangs.interpreters.grid_based.cod import _Cod

        assert _Cod(0, 0, "N").value == 0


if __name__ == "__main__":
    pass
