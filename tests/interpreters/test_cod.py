r"""Unit tests for the COD interpreter."""

import pytest

from esolangs.interpreters.grid_based.cod import _Machine, run
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.randomness import Randomness


def run_and_capture(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def step_and_capture(
    code: str, steps: int, stdin: str = "", rng: Randomness | None = None
) -> str:
    r"""Step a COD program a fixed number of times and return what it."""
    io = ScriptedIO(stdin)
    machine = _Machine(code, io, rng=rng)
    for _ in range(steps):
        if machine.halted:
            break
        machine.step()
    return io.getvalue()


class _FirstChoiceRNG:
    r"""Picks the first option, by returning index zero."""

    def randbelow(self, upper: int) -> int:
        assert upper > 0
        return 0


class _LastChoiceRNG:
    r"""Picks the *last* option, so a choice is visible as a direction."""

    def randbelow(self, upper: int) -> int:
        assert upper > 0
        return upper - 1


class _CountingRNG:
    r"""Records how often it was consulted, and over how many options."""

    def __init__(self) -> None:
        self.calls: list[int] = []

    def randbelow(self, upper: int) -> int:
        self.calls.append(upper)
        return 0


class TestCOD:
    def test_increment_and_output(self) -> None:
        # ')' increments, '---' on the.
        assert run_and_capture("~~~~~\n~>))---") == "2"

    def test_decrement_and_output(self) -> None:
        assert run_and_capture("~~~~~~\n~>)))((---") == "1"

    def test_decrement_steps_down_from_wherever_it_starts(self) -> None:
        r"""``(`` subtracts one; it does not put a value there."""
        assert run_and_capture("~~~~~~~\n~>))((---") == "0"
        assert run_and_capture("~~~~~\n~>(---") == "-1"

    def test_less_than_removes_zero_valued_cod(self) -> None:
        # value 0 hits '<' and is.
        assert run_and_capture("~~~~~~\n~><----") == ""

    def test_less_than_passes_nonzero_cod(self) -> None:
        assert run_and_capture("~~~~~~~\n~>)<---") == "1"

    def test_bare_dash_removes_the_cod(self) -> None:
        # a lone '-' (not part of a.
        # removes the cod outright, per.
        assert run_and_capture("~~~~~~\n~>-)---") == ""

    def test_a_dot_run_that_is_not_a_read(self) -> None:
        r"""Only a run of exactly three touching an edge reads; others are."""
        assert step_and_capture("~~~~~\n~>).\n~~.~~", steps=50) == ""

    def test_a_three_dot_run_off_both_edges_is_not_a_read(self) -> None:
        r"""Three dots are only a read where the run reaches the top or bottom."""
        from esolangs.interpreters.grid_based.cod import _edge_dot_cells

        assert _edge_dot_cells(["x", ".", ".", ".", "x"]) == set()
        assert _edge_dot_cells([".", ".", ".", "x"]) == {(0, 0), (1, 0), (2, 0)}

    def test_a_dot_run_against_the_bottom_edge_is_a_read(self) -> None:
        r"""A run that *ends* at the last row reads, as one starting at the."""
        from esolangs.interpreters.grid_based.cod import _edge_dot_cells

        assert _edge_dot_cells(["x", ".", ".", "."]) == {(1, 0), (2, 0), (3, 0)}
        assert _edge_dot_cells(["x", "x", "x", ".", ".", "."]) == {
            (3, 0),
            (4, 0),
            (5, 0),
        }
        # and the run is live: the cod.
        code = "\n".join(["~~~~~~", "~~.~~~", "~~.~~~", "~>.---"])
        assert run_and_capture(code, stdin="7") == "7"

    def test_a_dash_run_against_the_left_edge_prints(self) -> None:
        r"""``---`` starting at column 0 is an output, as one ending at the."""
        from esolangs.interpreters.grid_based.cod import _edge_dash_cells

        assert _edge_dash_cells(["---~~~"]) == {(0, 0), (0, 1), (0, 2)}
        # the cod's only exit is west,.
        code = "\n".join(["~~~~~~", "---)>~", "~~~~~~"])
        assert run_and_capture(code) == "1"

    def test_triple_dash_not_on_edge_is_three_removals(self) -> None:
        # '---' with water on both.
        # print+remove; the cod dies on.
        assert run_and_capture("~~~~~~~\n~> ---  \n~~~~~~~") == ""

    def test_duplicate_at_two_way_fork_splits_forward_and_side(self) -> None:
        # a '+' at a T with the entry.
        # one copy each way; both carry.
        # copy survives its '<' gate),.
        # -- the east copy prints.
        # passes one more ')' before.
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
        # Outputs are not separated, so.
        # order is whichever cod.
        # does not pin, so compare the.
        assert sorted(out) == ["1", "2"]

    def test_reflect_upward_motion_when_nonzero(self) -> None:
        # '_' reflects an upward-moving.
        # 1 when it hits '_' (from the.
        # turns south and continues.
        # back, reaching value 2.
        code = "\n".join(["~~~~~", "~~~~~", "~_~~~", "~)~~~", "~>~~~"])
        io = ScriptedIO("")
        m = _Machine(code, io)
        m.step()  # (4,1,N,0) -> (3,1,N,1):.
        m.step()  # (3,1,N,1) -> (2,1,S,1): hits.
        cod = m.cods[0]
        assert (cod.r, cod.c, cod.d, cod.value) == (2, 1, "S", 1)

    def test_reflect_is_noop_when_zero(self) -> None:
        # '_' hit going up with value 0.
        # past it (since forward is.
        # rather than reflecting.
        code = "\n".join(["~~~~~", "~~~~~", "~_~~~", "~ ~~~", "~>~~~"])
        io = ScriptedIO("")
        m = _Machine(code, io)
        m.step()  # (4,1,N,0) -> (3,1,N,0).
        m.step()  # (3,1,N,0) -> (2,1,N,0): '_'.
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
        assert run_and_capture(code, stdin="0") == "0"

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
        out = step_and_capture(code, steps=100, stdin="1")
        assert out.count("1") > 5

    def test_a_grid_with_no_wave_border_is_still_bounded(self) -> None:
        r"""Off the grid is wall, on every side, even where no ``~`` says so."""
        assert run_and_capture(">))---") == "2"
        # ')' in the last column: the.
        # walk off the end of the row.
        assert run_and_capture(">(<)") == ""

    def test_column_zero_is_a_cell_a_cod_can_be_sent_to(self) -> None:
        r"""The leftmost column is inside the grid, not one past its edge."""
        code = "\n".join(["~~~~", "->~~", "~~~~"])
        machine = _Machine(code, IO())
        assert [(cod.r, cod.c, cod.d) for cod in machine.cods] == [(1, 1, "W")]
        machine.step()  # west onto the '-', which.
        assert machine.halted

    def test_a_short_row_is_padded_with_waves(self) -> None:
        r"""A ragged grid is squared off with wall, not with water."""
        with pytest.raises(ValueError, match="fully enclosed"):
            run("~~~~\n~>\n~~~~", IO())

    def test_an_empty_program_has_no_start_marker(self) -> None:
        r"""Code with no rows at all reports the missing ``>``."""
        with pytest.raises(ValueError, match="no cod start"):
            run("", IO())

    def test_an_uppercase_letter_is_no_more_passable_than_a_lowercase_one(
        self,
    ) -> None:
        r"""The passable set is exactly the characters the language names."""
        with pytest.raises(ValueError, match="unknown instruction"):
            run("~>X~", IO())

    def test_the_malformed_messages_read_in_full(self) -> None:
        r"""Each message entire, not the fragment the tests match on."""
        import re

        for code, message in (
            ("~~~~~", "no cod start marker '>'"),
            ("~~~~~~~\n~> > ~~\n~~~~~~~", "multiple cod start markers"),
            ("~~~\n~>~\n~~~", "cod start is fully enclosed"),
            ("~>q~", "unknown instruction 'q'"),
        ):
            with pytest.raises(ValueError, match=re.escape(message)) as caught:
                run(code, IO())
            assert str(caught.value) == message

    def test_deterministic_rng_picks_first_option(self) -> None:
        # at a genuine (non '+') random.
        # first-choice policy makes.
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
        r"""A ``>`` with two ways out asks the chooser, and takes its answer."""
        code = "\n".join(["~~~~~", "~ > ~", "~~~~~"])
        machine = _Machine(code, IO(), rng=_LastChoiceRNG())
        assert machine.cods[0].d == "W"

    def test_run_hands_its_chooser_to_the_machine(self) -> None:
        r"""``rng`` reaches the draw, rather than being dropped on the way."""
        rng = _CountingRNG()
        step_and_capture("~~~~~\n~ > ~\n~~~~~", steps=10, rng=rng)
        assert rng.calls == [2]  # one draw, between two open.

    def test_step_on_halted_machine_is_noop(self) -> None:
        machine = _Machine("~~~~~\n~><--", IO())
        machine.step()  # cod value 0 hits '<' and dies.
        assert machine.halted
        machine.step()  # must not raise.
        assert machine.halted

    def test_snapshot_is_hashable_and_stable(self) -> None:
        machine = _Machine("~~~~~\n~>)) --", IO())
        snap1 = machine.snapshot()
        hash(snap1)  # must not raise.
        machine.step()
        snap2 = machine.snapshot()
        assert snap1 != snap2

    def test_trailing_blank_lines_are_stripped(self) -> None:
        # a trailing "\n\n" leaves an.
        # affect grid width or the.
        assert run_and_capture("~~~~~~\n~>)---\n\n") == "1"

    def test_trailing_blank_lines_do_not_move_the_bottom_edge(self) -> None:
        r"""Stripping decides where "bottom" is, so a read depends on it."""
        code = "\n".join(["~~~~~~", "~~.~~~", "~~.~~~", "~>.---"])
        assert run_and_capture(code + "\n\n", stdin="7") == "7"

    def test_genuine_random_junction_without_rng_uses_secrets(self) -> None:
        # a real >=2-way fork (not via.
        # West open.
        # choice; run it enough times.
        # reachable (each is chosen.
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
            machine.step()  # (3,3,N) -> (2,3,N).
            machine.step()  # (2,3,N) -> (1,3,N): enters.
            machine.step()  # forward (N) blocked: resolves.
            seen_dirs.add(machine.cods[0].d)
            if seen_dirs == {"E", "W"}:
                break
        assert seen_dirs == {"E", "W"}

    def test_duplicate_at_dead_end_reverses(self) -> None:
        # '+' landing on a cell whose.
        # cod came from (0 forward.
        # dead end.
        code = "\n".join(["~~~~~", "~+~~~", "~>~~~"])
        machine = _Machine(code, IO())
        machine.step()
        cod = machine.cods[0]
        assert (cod.r, cod.c, cod.d) == (1, 1, "S")

    def test_a_duplicate_at_a_dead_end_keeps_the_value(self) -> None:
        r"""The cod ``+`` sends back carries what the cod arrived with."""
        code = "\n".join(["~~~~~", "~+~~~", "~)~~~", "~>~~~"])
        machine = _Machine(code, IO())
        machine.step()  # (3,1,N,0) -> (2,1,N,1):.
        machine.step()  # (2,1,N,1) -> (1,1,S,1): '+'.
        cod = machine.cods[0]
        assert (cod.r, cod.c, cod.d, cod.value) == (1, 1, "S", 1)

    def test_a_cod_starts_at_zero(self) -> None:
        r"""A cod made without a value is worth 0."""
        from esolangs.interpreters.grid_based.cod import _Cod

        assert _Cod(0, 0, "N").value == 0


if __name__ == "__main__":
    pass
