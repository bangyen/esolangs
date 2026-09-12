r"""Unit tests for the Flowchart interpreter."""

import pytest

from esolangs.interpreters.grid_based.flowchart import _Machine, run
from esolangs.interpreters.io import ScriptedIO
from esolangs.vm import run_until_halt_or_cycle
from tests.raises import raises_message

# The wiki's truth machine:.
# 1 print it forever.
# heading-relative left.
TRUTH_MACHINE = [
    "       ( )──┐        ",
    "           / /       ",
    "            │        ",
    "(( ))─\\ \\──< >┬─\\ \\─┐",
    "              │     │",
    "              └─────┘",
]

# The wiki's cat: the upper.
# runs out, and the lower loop.
CAT = [
    "( )──┐   ",
    "  ┌─/ /─┐",
    "  │  │  │",
    "  │\\[ ]/│",
    "  │  │  │",
    "  └─< >─┘",
    "     │   ",
    "  ┌/{ }\\┐",
    "  │  │  │",
    "  │ \\ \\ │",
    "  │  │  │",
    "  └─< >─┘",
    "     │   ",
    "   (( )) ",
]

# The wiki's Kolakoski-sequence.
# east and a south path, so it.
KOLAKOSKI = [
    "( )─[ }─\\[ ]/─/{ }\\─\\ \\─( )─< >─( )─( )─( )─{ }─(( ))",
    " │              │        │   └────────────────────┘",
    "{ ]─\\ \\         │      \\{ }/",
    " ┌───┘          │        │",
    "[ }─\\ \\─(( )) \\[ ]/    \\[ ]/",
    "                │        │",
    "              \\[ ]/─────[ ]",
]


def run_program(code: list[str], stdin: str = "") -> str:
    r"""Run ``code`` to completion and return everything it printed."""
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def run_steps(code: list[str], stdin: str, steps: int) -> str:
    r"""Run ``code`` for at most ``steps`` rounds, for programs that loop."""
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    for _ in range(steps):
        if machine.halted:
            break
        machine.step()
    return io.getvalue()


class TestTruthMachine:
    r"""The wiki's truth machine, which pins the switch's orientation."""

    def test_zero_prints_once_and_halts(self) -> None:
        r"""A zero takes the switch's right branch, prints, and ends."""
        assert run_program(TRUTH_MACHINE, "0") == "0"

    def test_one_prints_forever(self) -> None:
        r"""A one takes the left branch onto the ring and never stops."""
        short = run_steps(TRUTH_MACHINE, "1", 100)
        long = run_steps(TRUTH_MACHINE, "1", 400)
        assert set(short) == {"1"}
        assert set(long) == {"1"}
        assert len(long) > len(short)

    def test_one_never_halts(self) -> None:
        r"""The looping branch still has a live pointer after many steps."""
        machine = _Machine(TRUTH_MACHINE, ScriptedIO("1"))
        for _ in range(500):
            machine.step()
        assert not machine.halted

    def test_one_is_a_provable_cycle(self) -> None:
        r"""The looping branch revisits an exact state, proving the hang."""
        machine = _Machine(TRUTH_MACHINE, ScriptedIO("1"))
        assert run_until_halt_or_cycle(machine) is False

    def test_zero_is_reported_as_halting(self) -> None:
        r"""The halting branch is not mistaken for a cycle."""
        machine = _Machine(TRUTH_MACHINE, ScriptedIO("0"))
        assert run_until_halt_or_cycle(machine) is True


class TestCat:
    r"""The wiki's cat, which pins the re-entry rule and the empty register."""

    @pytest.mark.parametrize(
        "bits",
        ["1", "0", "101", "1101", "000", "111"],
    )
    def test_echoes_its_input(self, bits: str) -> None:
        r"""Every bit read is printed back, in order, and the program ends."""
        assert run_program(CAT, "\n".join(bits)) == bits

    def test_no_input_prints_nothing(self) -> None:
        r"""With no bits to read the deque stays empty and nothing is output."""
        assert run_program(CAT, "") == ""

    def test_halts_rather_than_looping(self) -> None:
        r"""The exhausted read sends the pointer forward to the end node."""
        machine = _Machine(CAT, ScriptedIO("1\n0\n1"))
        assert run_until_halt_or_cycle(machine) is True

    def test_no_trailing_zero_from_the_empty_register(self) -> None:
        r"""The final lap's empty register prints nothing."""
        assert not run_program(CAT, "\n".join("101")).endswith("1010")


class TestKolakoski:
    r"""The wiki's Kolakoski example, the one that forks into two pointers."""

    def test_start_node_forks_in_reading_order(self) -> None:
        r"""The opening ``( )`` splits east first, then south."""
        machine = _Machine(KOLAKOSKI, ScriptedIO(""))
        assert [(p.row, p.col) for p in machine.pointers] == [(0, 3), (1, 1)]

    def test_it_keeps_producing_output(self) -> None:
        r"""The generator is infinite, so it runs on rather than halting."""
        machine = _Machine(KOLAKOSKI, ScriptedIO(""))
        for _ in range(400):
            machine.step()
        assert not machine.halted

    def test_output_prefix(self) -> None:
        r"""Characterization only: the wiki states no expected output."""
        assert run_steps(KOLAKOSKI, "", 400) == "01111001100110011001"


class TestParsing:
    r"""Grid parsing, node spellings, and malformed programs."""

    def test_longer_spellings_win(self) -> None:
        r"""``\[ ]/`` is one push node, not a ``[ ]`` toggle inside noise."""
        machine = _Machine(["( )─\\[ ]/─(( ))"], ScriptedIO(""))
        assert machine.nodes[(0, 4)][0] == "\\[ ]/"

    def test_end_node_is_not_read_as_a_start(self) -> None:
        r"""``(( ))`` is matched before ``( )`` so an end never starts a run."""
        machine = _Machine(["(( ))─( )"], ScriptedIO(""))
        assert machine.nodes[(0, 0)][0] == "(( ))"

    def test_empty_program_is_rejected(self) -> None:
        r"""An empty grid has no start node to begin from."""
        with pytest.raises(ValueError, match="no '\\( \\)' start node"):
            _Machine([], ScriptedIO(""))

    def test_the_rejection_messages_are_exact(self) -> None:
        r"""Both messages are pinned whole, position included."""
        with raises_message(ValueError, "unknown character '?' at (4, 0)"):
            _Machine(["( )─?─(( ))"], ScriptedIO(""))

        with raises_message(ValueError, "Flowchart program has no '( )' start node"):
            _Machine(["(( ))"], ScriptedIO(""))

    def test_turning_left_rotates_every_heading(self) -> None:
        r"""A left turn is a rotation, so four of them return the heading."""
        from esolangs.interpreters.grid_based.flowchart import _turn_left

        north, south, west, east = (-1, 0), (1, 0), (0, -1), (0, 1)
        assert _turn_left(north) == west
        assert _turn_left(west) == south
        assert _turn_left(south) == east
        assert _turn_left(east) == north

    def test_only_the_newline_is_stripped_from_a_row(self) -> None:
        r"""Trailing spaces stay, since a column is a position in the grid."""
        machine = _Machine(["( )  \n"], ScriptedIO(""))
        assert machine.width == 5
        assert machine.grid == ("( )  ",)

    def test_stacked_nodes_do_not_fork(self) -> None:
        r"""A node drawn directly on top of another is one path, not three."""
        stacked = [" ( )", " [ }", " \\ \\", "(( ))"]
        io = ScriptedIO("")
        run(stacked, io)
        assert io.getvalue() == "1"

        railed = [" ( )", "  │", " [ }", "  │", " \\ \\", "  │", "(( ))"]
        io = ScriptedIO("")
        run(railed, io)
        assert io.getvalue() == "1", "a rail between the nodes must not change it"

    def test_a_genuine_fork_still_splits(self) -> None:
        r"""Deduplicating exits must not collapse real multi-path forks."""
        machine = _Machine(list(KOLAKOSKI), ScriptedIO(""))
        assert len(machine.pointers) == 2

    def test_a_fork_copies_the_register_to_both_branches(self) -> None:
        r"""Each new pointer starts from the forking pointer's register."""
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
        r"""The other half of the copied state: which deque is selected."""
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
        r"""A vertical path must meet the middle of the node it enters."""
        with pytest.raises(ValueError, match="but its middle is column 2"):
            _Machine([" ( )", " │  ", "(( ))"], ScriptedIO(""))

    def test_horizontal_entry_at_an_end_cell_is_allowed(self) -> None:
        r"""Horizontal entry lands on an end cell and is not an error."""
        machine = _Machine(["( )─[ }─(( ))"], ScriptedIO(""))
        assert machine.nodes[(0, 4)][0] == "[ }"

    def test_a_rail_passing_beside_a_node_is_not_an_entry(self) -> None:
        r"""Only a path arm pointing *at* a node counts as entering it."""
        machine = _Machine(["( )────┐  ", "───────┼──", " (( ))─┘  "], ScriptedIO(""))
        assert machine.nodes[(2, 1)][0] == "(( ))"


class TestNodes:
    r"""The register and deque nodes, driven through short straight."""

    def _register(self, body: str) -> int | None:
        r"""Run ``body`` between a start and an end node, returning the."""
        io = ScriptedIO("")
        machine = _Machine([f"( )─{body}─(( ))"], io)
        while not machine.halted:
            machine.step()
        return machine.pointers[0].reg

    def test_set_to_one(self) -> None:
        r"""``[ }`` sets the register to one."""
        assert self._register("[ }") == 1

    def test_set_to_zero(self) -> None:
        r"""``{ ]`` sets the register to zero."""
        assert self._register("[ }─{ ]") == 0

    def test_toggle_from_empty_is_one(self) -> None:
        r"""``[ ]`` on an empty register yields one."""
        assert self._register("[ ]") == 1

    def test_toggle_flips(self) -> None:
        r"""``[ ]`` twice returns the register to zero."""
        assert self._register("[ ]─[ ]") == 0

    def test_clear_empties(self) -> None:
        r"""``{ }`` empties the register."""
        assert self._register("[ }─{ }") is None

    def test_push_then_pop_round_trips(self) -> None:
        r"""A pushed bit comes back off the top of the deque."""
        assert self._register("[ }─\\[ ]/─{ }─\\{ }/") == 1

    def test_pop_from_empty_leaves_it_empty(self) -> None:
        r"""Popping an exhausted deque clears the register."""
        assert self._register("[ }─\\{ }/") is None

    def test_pushing_an_empty_register_pushes_nothing(self) -> None:
        r"""A push with nothing to push leaves the deque as it was."""
        assert self._register("{ }─\\[ ]/─\\{ }/") is None
        assert self._register("{ }─/[ ]\\─/{ }\\") is None

    def test_push_bottom_pop_bottom(self) -> None:
        r"""``/[ ]\`` and ``/{ }\`` use the other end of the deque."""
        assert self._register("[ }─/[ ]\\─{ }─/{ }\\") == 1

    def test_deques_are_separate(self) -> None:
        r"""A bit pushed on one deque is not visible from the next."""
        assert self._register("[ }─\\[ ]/─[ >─\\{ }/") is None

    def test_switching_back_finds_the_bit(self) -> None:
        r"""Selecting the previous deque again restores its contents."""
        assert self._register("[ }─\\[ ]/─[ >─< ]─\\{ }/") == 1

    def test_output_prints_the_bit(self) -> None:
        r"""``\ \`` writes the register as a character."""
        assert run_program(["( )─[ }─\\ \\─(( ))"]) == "1"

    def test_output_of_an_empty_register_prints_nothing(self) -> None:
        r"""An empty register writes no character at all."""
        assert run_program(["( )─\\ \\─(( ))"]) == ""

    def test_input_reads_one_bit_per_line(self) -> None:
        r"""``/ /`` takes one bit from each line of input."""
        assert run_program(["( )─/ /─\\ \\─/ /─\\ \\─(( ))"], "1\n0") == "10"

    def test_exhausted_input_leaves_the_register_empty(self) -> None:
        r"""Reading past the end of the input empties the register."""
        assert run_program(["( )─/ /─\\ \\─(( ))"], "") == ""


class TestPointersStop:
    r"""Every way a pointer runs out of places to go."""

    @staticmethod
    def _halts(code: list[str], steps: int = 20) -> bool:
        machine = _Machine(code, ScriptedIO(""))
        for _ in range(steps):
            if machine.halted:
                return True
            machine.step()
        return machine.halted

    def test_start_with_no_exits_stops_immediately(self) -> None:
        r"""A start node with nothing attached has nowhere to send a pointer."""
        assert self._halts(["( )"])
        assert run_program(["( )"]) == ""

    def test_stepping_a_halted_machine_does_nothing(self) -> None:
        r"""``step`` returns early once every pointer is done."""
        machine = _Machine(["( )"], ScriptedIO(""))
        machine.step()
        assert machine.halted
        machine.step()  # the early return: no pointer.
        assert machine.halted

    def test_rail_running_off_the_grid_stops(self) -> None:
        r"""A rail that reaches the edge stops instead of stepping outside."""
        assert self._halts(["( )─"])
        assert self._halts(["( )", " │ "])

    def test_rail_into_a_gap_stops(self) -> None:
        r"""A rail that ends in blank space has no cell to continue into."""
        assert self._halts(["( )─ ─"])

    def test_node_with_no_onward_rail_stops(self) -> None:
        r"""A node reached by a rail but leading nowhere stops the pointer."""
        assert self._halts(["( )─\\[ ]/"])
        assert self._halts(["( )─< >"])
        assert self._halts(["( )─{ }"])

    def test_start_touching_only_another_node_stops(self) -> None:
        r"""A start whose sole neighbour is the node it came from forks nowhere."""
        assert self._halts(["( )( )"])


class TestAmbiguousExits:
    r"""Junctions where neither memory nor the current heading settles the."""

    def test_head_on_junction_falls_past_the_heading(self) -> None:
        r"""A rail entered head-on turns, because straight on is not an arm."""
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
        r"""An empty register sends a switch straight on; with no straight on,."""
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
        assert io.getvalue() == ""

    def test_a_set_register_still_turns_at_that_switch(self) -> None:
        r"""The same grid, with the turn available: the switch does turn."""
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
