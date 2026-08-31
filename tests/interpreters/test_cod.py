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


class TestCOD:
    def test_increment_and_output(self) -> None:
        # ')' increments, '---' on the right edge prints and removes
        assert run_and_capture("~~~~~\n~>))---") == "2"

    def test_decrement_and_output(self) -> None:
        assert run_and_capture("~~~~~~\n~>)))((---") == "1"

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

    def test_no_start_marker_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="no cod start"):
            run("~~~~~", IO())

    def test_two_start_markers_is_malformed(self) -> None:
        code = "\n".join(["~~~~~~~", "~> > ~~", "~~~~~~~"])
        with pytest.raises(ValueError, match="multiple cod start"):
            run(code, IO())

    def test_unknown_instruction_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="unknown instruction"):
            run("~>q~", IO())

    def test_fully_enclosed_start_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="fully enclosed"):
            run("~~~\n~>~\n~~~", IO())

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


if __name__ == "__main__":
    pass
