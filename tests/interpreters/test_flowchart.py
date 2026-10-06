"""Unit tests for the Flowchart interpreter."""

from functools import partial
from pathlib import Path

import pytest

from esolangs.interpreters.grid_based.flowchart import _Machine, run
from esolangs.interpreters.io import ScriptedIO
from esolangs.vm import run_until_halt_or_cycle
from tests.fixtures import grid
from tests.interpreters.runner import run_program as _run_program

# The wiki's truth machine: read a bit, and on 0 print it once and halt, on
# 1 print it forever.  The switch is entered travelling downward, so its
# heading-relative left (grid-east) is the looping branch.
TRUTH_MACHINE = grid("flowchart/truth_machine.txt")

# The wiki's cat: the upper loop reads bits onto a deque until the input
# runs out, and the lower loop pops them back off and prints them.
CAT = grid("flowchart/cat.txt")

# The wiki's Kolakoski-sequence generator.  Its opening ``( )`` has both an
# east and a south path, so it is the one example that forks.
KOLAKOSKI = grid("flowchart/kolakoski.txt")

# The Kolakoski program on the current wiki page.  Bits 0 and 1 stand for 1
# and 2, so its output is the Kolakoski sequence, which the page names.
WIKI_KOLAKOSKI = grid("flowchart/wiki_kolakoski.txt")


run_program = partial(_run_program, run, suppress_eof=False)


def run_steps(code: list[str], stdin: str, steps: int) -> str:
    """Run ``code`` for at most ``steps`` rounds, for programs that loop."""
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    for _ in range(steps):
        if machine.halted:
            break
        machine.step()
    return io.getvalue()


class TestTruthMachine:
    """The wiki's truth machine, which pins the switch's orientation."""

    def test_zero_prints_once_and_halts(self) -> None:
        """A zero takes the switch's right branch, prints, and ends."""
        assert run_program(TRUTH_MACHINE, "0") == "0"

    def test_one_prints_forever(self) -> None:
        """A one takes the left branch onto the ring and never stops."""
        short = run_steps(TRUTH_MACHINE, "1", 100)
        long = run_steps(TRUTH_MACHINE, "1", 400)
        assert set(short) == {"1"}
        assert set(long) == {"1"}
        assert len(long) > len(short)

    def test_one_is_a_provable_cycle(self) -> None:
        """The looping branch revisits an exact state, proving the hang."""
        machine = _Machine(TRUTH_MACHINE, ScriptedIO("1"))
        assert run_until_halt_or_cycle(machine) is False


class TestCat:
    """The wiki's cat, which pins the re-entry rule and the empty register."""

    @pytest.mark.parametrize(
        "bits",
        ["1", "0", "101", "1101", "000", "111"],
    )
    def test_wiki_cat_appends_zero(self, bits: str) -> None:
        """The final empty-deque pop causes the wiki cat to append zero."""
        assert run_program(CAT, "\n".join(bits)) == bits + "0"

    def test_halts_rather_than_looping(self) -> None:
        """The exhausted read sends the pointer forward to the end node."""
        machine = _Machine(CAT, ScriptedIO("1\n0\n1"))
        assert run_until_halt_or_cycle(machine) is True


class TestKolakoski:
    """The wiki's Kolakoski example, the one that forks into two pointers."""

    def test_start_node_forks_in_reading_order(self) -> None:
        """The opening ``( )`` splits east first, then south."""
        machine = _Machine(KOLAKOSKI, ScriptedIO(""))
        assert [(p.row, p.col) for p in machine.pointers] == [(0, 3), (1, 1)]

    def test_it_keeps_producing_output(self) -> None:
        """The generator is infinite, so it runs on rather than halting."""
        machine = _Machine(KOLAKOSKI, ScriptedIO(""))
        for _ in range(400):
            machine.step()
        assert not machine.halted

    def test_output_prefix(self) -> None:
        """Characterization only: this older layout prints no stated output.

        It pushes empty registers, so the pin moved when pushing empty
        stopped being a no-op (it was ``01111001100110011001``).
        """
        assert run_steps(KOLAKOSKI, "", 400)[:20] == "01101100110011001100"

    def test_the_current_wiki_program_prints_the_kolakoski_sequence(self) -> None:
        """1221121221221121122121121221121121221221121 as bits 0 and 1."""
        expected = "0110010110110010011010010110010010110110010"
        assert run_steps(WIKI_KOLAKOSKI, "", 1500)[: len(expected)] == expected


class TestParsing:
    """Grid parsing, node spellings, and malformed programs."""

    def test_longer_spellings_win(self) -> None:
        """``\\[ ]/`` is one push node, not a ``[ ]`` toggle inside noise."""
        machine = _Machine(["( )─\\[ ]/─(( ))"], ScriptedIO(""))
        assert machine.nodes[(0, 4)][0] == "\\[ ]/"

    def test_end_node_is_not_read_as_a_start(self) -> None:
        """``(( ))`` is matched before ``( )`` so an end never starts a run."""
        machine = _Machine(["(( ))─( )"], ScriptedIO(""))
        assert machine.nodes[(0, 0)][0] == "(( ))"

    def test_empty_program_is_rejected(self) -> None:
        """An empty grid has no start node to begin from."""
        with pytest.raises(ValueError, match="no '\\( \\)' start node"):
            _Machine([], ScriptedIO(""))

    def test_turning_left_rotates_every_heading(self) -> None:
        """A left turn is a rotation, so four of them return the heading."""
        from esolangs.interpreters.grid_based.flowchart import _turn_left

        north, south, west, east = (-1, 0), (1, 0), (0, -1), (0, 1)
        assert _turn_left(north) == west
        assert _turn_left(west) == south
        assert _turn_left(south) == east
        assert _turn_left(east) == north

    def test_only_the_newline_is_stripped_from_a_row(self) -> None:
        """Trailing spaces stay, since a column is a position in the grid."""
        machine = _Machine(["( )─(( ))  \n"], ScriptedIO(""))
        assert machine.width == 11
        assert machine.grid == ("( )─(( ))  ",)

    def test_nodes_touching_side_by_side_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="nodes touch without a path"):
            _Machine(["( )[ }"], ScriptedIO(""))

    @pytest.mark.parametrize("name", ["parallel", "serial"])
    def test_the_wiki_hello_worlds(self, name: str) -> None:
        """Both stack nodes in adjacent rows; bits come out low bit first.

        The eight-pointer version also needs the spec's pointer order and
        its left-most start, and paths that take no time.
        """
        path = Path(__file__).parent.parent / "fixtures" / f"flowchart_hello_{name}.txt"
        bits = run_program(path.read_text(encoding="utf-8").splitlines())
        chars = [bits[i : i + 8][::-1] for i in range(0, len(bits), 8)]
        assert "".join(chr(int(c, 2)) for c in chars) == "Hello, world!"

    def test_separated_nodes_execute(self) -> None:
        for program in (
            ["( )─[ }─\\ \\─(( ))"],
            [" ( )", "  │", " [ }", "  │", " \\ \\", "  │", "(( ))"],
        ):
            io = ScriptedIO("")
            run(program, io)
            assert io.getvalue() == "1"

    def test_a_genuine_fork_still_splits(self) -> None:
        """Deduplicating exits must not collapse real multi-path forks."""
        machine = _Machine(list(KOLAKOSKI), ScriptedIO(""))
        assert len(machine.pointers) == 2

    def test_a_fork_copies_the_register_to_both_branches(self) -> None:
        """Each new pointer starts from the forking pointer's register."""
        program = [
            "( )─[ }─[ }─( )─\\ \\─(( ))",
            "             │",
            "            \\ \\",
            "             │",
            "           (( ))",
        ]
        io = ScriptedIO("")
        run(program, io)
        assert io.getvalue() == "11", "both branches print the inherited register"

    def test_a_fork_copies_the_deque_cursor_to_both_branches(self) -> None:
        """The other half of the copied state: which deque is selected."""
        program = [
            "( )─[ >─[ }─( )─{ }─(( ))",
            "             │",
            "            { }",
            "             │",
            "           (( ))",
        ]
        machine = _Machine(program, ScriptedIO(""))
        for _ in range(14):
            if machine.halted:
                break
            machine.step()
        assert [p.deque for p in machine.pointers] == [1, 1]

    def test_off_centre_vertical_entry_is_rejected(self) -> None:
        """A vertical path must meet the middle of the node it enters."""
        with pytest.raises(ValueError, match="but its middle is column 2"):
            _Machine([" ( )", " │  ", "(( ))"], ScriptedIO(""))

    def test_horizontal_entry_at_an_end_cell_is_allowed(self) -> None:
        """Horizontal entry lands on an end cell and is not an error."""
        machine = _Machine(["( )─[ }─(( ))"], ScriptedIO(""))
        assert machine.nodes[(0, 4)][0] == "[ }"

    def test_a_rail_passing_beside_a_node_is_not_an_entry(self) -> None:
        """Only a path arm pointing *at* a node counts as entering it."""
        machine = _Machine(["( )────┐  ", "───────┼──", " (( ))─┘  "], ScriptedIO(""))
        assert machine.nodes[(2, 1)][0] == "(( ))"


class TestNodes:
    """The register and deque nodes, driven through short straight programs."""

    def _register(self, body: str) -> int | None:
        """Run ``body`` between a start and an end node, returning the register."""
        io = ScriptedIO("")
        machine = _Machine([f"( )─{body}─(( ))"], io)
        while not machine.halted:
            machine.step()
        return machine.pointers[0].reg

    def test_set_to_one(self) -> None:
        """``[ }`` sets the register to one."""
        assert self._register("[ }") == 1

    def test_set_to_zero(self) -> None:
        """``{ ]`` sets the register to zero."""
        assert self._register("[ }─{ ]") == 0

    def test_toggle_from_empty_is_one(self) -> None:
        """``[ ]`` on an empty register yields one."""
        assert self._register("[ ]") == 1

    def test_toggle_flips(self) -> None:
        """``[ ]`` twice returns the register to zero."""
        assert self._register("[ ]─[ ]") == 0

    def test_clear_empties(self) -> None:
        """``{ }`` empties the register."""
        assert self._register("[ }─{ }") is None

    def test_push_then_pop_round_trips(self) -> None:
        """A pushed bit comes back off the top of the deque."""
        assert self._register("[ }─\\[ ]/─{ }─\\{ }/") == 1

    def test_pushing_an_empty_register_pushes_an_empty(self) -> None:
        """The spec lets a deque hold empty, so it covers the bit beneath."""
        assert self._register("[ }─\\[ ]/─{ }─\\[ ]/─\\{ }/") is None
        assert self._register("[ }─/[ ]\\─{ }─/[ ]\\─/{ }\\") is None
        assert self._register("[ }─\\[ ]/─{ }─\\[ ]/─\\{ }/─\\{ }/") == 1

    def test_push_bottom_pop_bottom(self) -> None:
        """``/[ ]\\`` and ``/{ }\\`` use the other end of the deque."""
        assert self._register("[ }─/[ ]\\─{ }─/{ }\\") == 1

    def test_deques_are_separate(self) -> None:
        """A bit pushed on one deque is not visible from the next."""
        assert self._register("[ }─\\[ ]/─[ >─\\{ }/") is None

    def test_switching_back_finds_the_bit(self) -> None:
        """Selecting the previous deque again restores its contents."""
        assert self._register("[ }─\\[ ]/─[ >─< ]─\\{ }/") == 1

    def test_output_prints_the_bit(self) -> None:
        """``\\ \\`` writes the register as a character."""
        assert run_program(["( )─[ }─\\ \\─(( ))"]) == "1"

    def test_output_of_an_empty_register_prints_zero(self) -> None:
        """The command table defines empty-register output as zero."""
        assert run_program(["( )─\\ \\─(( ))"]) == "0"

    def test_input_reads_one_bit_per_line(self) -> None:
        """``/ /`` takes one bit from each line of input."""
        assert run_program(["( )─/ /─\\ \\─/ /─\\ \\─(( ))"], "1\n0") == "10"

    def test_a_cursorless_read_loop_cycles_only_after_eof(self) -> None:
        """Reads count in the snapshot: no repeat is seen while bits remain."""
        from tests.interpreters.cursorless_io import CursorlessIO

        io = CursorlessIO("11111111")
        loop = ["( )─┬─/ /─┐", "    │     │", "    └─────┘"]
        assert run_until_halt_or_cycle(_Machine(loop, io)) is False
        assert io.exhausted


class TestPointersStop:
    """Every way a pointer runs out of places to go."""

    @staticmethod
    def _halts(code: list[str], steps: int = 20) -> bool:
        machine = _Machine(code, ScriptedIO(""))
        for _ in range(steps):
            if machine.halted:
                return True
            machine.step()
        return machine.halted

    def test_start_with_no_exits_is_invalid(self) -> None:
        with pytest.raises(ValueError, match="no exit path"):
            _Machine(["( )"], ScriptedIO(""))

    def test_stepping_a_halted_machine_does_nothing(self) -> None:
        machine = _Machine(["( )─(( ))"], ScriptedIO(""))
        while not machine.halted:
            machine.step()
        before = machine.snapshot()
        machine.step()
        assert machine.snapshot() == before

    def test_rail_running_off_the_grid_stops(self) -> None:
        """A rail that reaches the edge stops instead of stepping outside."""
        assert self._halts(["( )─"])
        assert self._halts(["( )", " │ "])

    def test_rail_into_a_gap_stops(self) -> None:
        """A rail that ends in blank space has no cell to continue into."""
        assert self._halts(["( )─ ─"])

    @pytest.mark.parametrize("node", ["\\[ ]/", "< >", "{ }", "( )"])
    def test_node_with_no_onward_rail_is_invalid(self, node: str) -> None:
        with pytest.raises(ValueError, match="no exit path"):
            run_program([f"( )─{node}"])

    def test_touching_start_nodes_are_rejected(self) -> None:
        """Start nodes also need a connecting path."""
        with pytest.raises(ValueError, match="nodes touch without a path"):
            _Machine(["( )( )"], ScriptedIO(""))


class TestAmbiguousExits:
    """Junctions where neither memory nor the current heading settles the exit."""

    def test_head_on_junction_falls_past_the_heading(self) -> None:
        """A rail entered head-on turns, because straight on is not an arm."""
        grid = [
            "          (( ))              ( )",
            "            │                 │",
            "           \\ \\               [ }",
            "            │                 │",
            "            ├─────────────────┘",
            "            │",
            "           \\ \\",
            "            │",
            "          (( ))",
        ]
        io = ScriptedIO("")
        run(grid, io)
        assert io.getvalue() == "1"

    def test_switch_with_no_forward_path_takes_the_first_exit(self) -> None:
        """An empty register sends a switch straight on; with no straight on,
        neither the preferred heading nor the arrival heading is available.
        """
        grid = [
            "                   ( )",
            "                    │",
            "                   { }",
            "                    │",
            "             ┌─────< >─────┐",
            "             │             │",
            "            \\ \\           \\ \\",
            "             │             │",
            "           (( ))         (( ))",
        ]
        io = ScriptedIO("")
        run(grid, io)
        assert io.getvalue() == "0"

    def test_a_set_register_still_turns_at_that_switch(self) -> None:
        """The same grid, with the turn available: the switch does turn."""
        for setter, expected in (("[ }", "1"), ("{ ]", "0")):
            grid = [
                "                   ( )",
                "                    │",
                f"                   {setter}",
                "                    │",
                "             ┌─────< >─────┐",
                "             │             │",
                "            \\ \\           \\ \\",
                "             │             │",
                "           (( ))         (( ))",
            ]
            io = ScriptedIO("")
            run(grid, io)
            assert io.getvalue() == expected, setter


def test_counterclockwise_entry_prefers_clockwise_exit() -> None:
    grid = [
        "   (( ))",
        "     │",
        "    [ ]─( )",
        "     │",
        "    [ }",
        "     │",
        "    \\ \\",
        "     │",
        "   (( ))",
    ]
    machine = _Machine(grid, ScriptedIO())
    machine.step()  # rides west into [ ] and leaves it clockwise, northward
    assert machine.ip == (1, 5, -1, 0)


def test_a_fork_keeps_its_own_pointer_on_the_forward_exit() -> None:
    """The spec's forward-first rule names only ``< >`` as an exception."""
    machine = _Machine([" ┌─(( ))", "( )─(( ))"], ScriptedIO(""))
    assert [p.d for p in machine.pointers] == [(0, 1), (-1, 0)]
