"""Unit tests for the Flowchart interpreter.

The command table takes precedence over the examples: empty-register output
is zero, so the wiki's cat appends a spurious bit. Other routing gaps follow
the worked examples; see the interpreter's module docstring.
"""

import pytest

from esolangs.interpreters.grid_based.flowchart import _Machine, run
from esolangs.interpreters.io import ScriptedIO
from tests.raises import raises_message

# The wiki's truth machine: read a bit, and on 0 print it once and halt, on
# 1 print it forever.  The switch is entered travelling downward, so its
# heading-relative left (grid-east) is the looping branch.
TRUTH_MACHINE = [
    "       ( )──┐        ",
    "           / /       ",
    "            │        ",
    "(( ))─\\ \\──< >┬─\\ \\─┐",
    "              │     │",
    "              └─────┘",
]

# The wiki's cat: the upper loop reads bits onto a deque until the input
# runs out, and the lower loop pops them back off and prints them.
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

# The wiki's Kolakoski-sequence generator.  Its opening ``( )`` has both an
# east and a south path, so it is the one example that forks.
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
    """Run ``code`` to completion and return everything it printed."""
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class TestKolakoski:
    """The wiki's Kolakoski example, the one that forks into two pointers."""

    def test_start_node_forks_in_reading_order(self) -> None:
        """The opening ``( )`` splits east first, then south.

        The spec orders pointers "top-most left-most, traveling right, then
        downwards", so the east path on row 0 precedes the south path on
        row 1.
        """
        machine = _Machine(KOLAKOSKI, ScriptedIO(""))
        assert [(p.row, p.col) for p in machine.pointers] == [(0, 3), (1, 1)]


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

    def test_the_rejection_messages_are_exact(self) -> None:
        """Both messages are pinned whole, position included.

        ``match=`` is a substring search, so a fragment leaves the wording
        around it free -- and the unknown character's coordinates would
        never be checked at all.
        """
        with raises_message(ValueError, "unknown character '?' at (4, 0)"):
            _Machine(["( )─?─(( ))"], ScriptedIO(""))

        with raises_message(ValueError, "Flowchart program has no '( )' start node"):
            _Machine(["(( ))"], ScriptedIO(""))

    def test_turning_left_rotates_every_heading(self) -> None:
        """A left turn is a rotation, so four of them return the heading.

        Negating the wrong component agrees on the vertical headings and
        reverses the horizontal ones, which is why the whole cycle has to
        be walked rather than one turn checked: the two spellings differ
        only on the headings a vertical-only test never reaches.
        """
        from esolangs.interpreters.grid_based.flowchart import _turn_left

        north, south, west, east = (-1, 0), (1, 0), (0, -1), (0, 1)
        assert _turn_left(north) == west
        assert _turn_left(west) == south
        assert _turn_left(south) == east
        assert _turn_left(east) == north

    def test_only_the_newline_is_stripped_from_a_row(self) -> None:
        """Trailing spaces stay, since a column is a position in the grid.

        Every program is written without them, so stripping whitespace
        generally would have gone unnoticed -- but it shortens the row and
        moves every column after it.
        """
        machine = _Machine(["( )─(( ))  \n"], ScriptedIO(""))
        assert machine.width == 11
        assert machine.grid == ("( )─(( ))  ",)

    @pytest.mark.parametrize(
        "program", [["( )[ }"], [" ( )", " [ }"], ["( )", "  [ }"]]
    )
    def test_touching_nodes_are_rejected(self, program: list[str]) -> None:
        with pytest.raises(ValueError, match="nodes touch without a path"):
            _Machine(program, ScriptedIO(""))

    def test_separated_nodes_execute(self) -> None:
        for program in (
            ["( )─[ }─\\ \\─(( ))"],
            [" ( )", "  │", " [ }", "  │", " \\ \\", "  │", "(( ))"],
        ):
            io = ScriptedIO("")
            run(program, io)
            assert io.getvalue() == "1"

    def test_a_genuine_fork_still_splits(self) -> None:
        """Deduplicating exits must not collapse real multi-path forks.

        The wiki's Kolakoski program opens with a ``( )`` that has both an
        east and a south path, and those are two distinct destinations.
        """
        machine = _Machine(list(KOLAKOSKI), ScriptedIO(""))
        assert len(machine.pointers) == 2

    def test_a_fork_copies_the_register_to_both_branches(self) -> None:
        """Each new pointer starts from the forking pointer's register.

        The fork tests above only count pointers, and a fork at the
        *start* has an empty register either way -- so nothing pinned
        what a mid-program fork carries.  Here the register is raised to
        1 before the ``( )``, and both branches print it.
        """
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
        """The other half of the copied state: which deque is selected.

        ``[ >`` moves the cursor before the fork, so neither branch may
        fall back to deque 0.
        """
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
        """A vertical path must meet the middle of the node it enters.

        The rail below sits on column 1, but ``(( ))`` spans columns 0-4 and
        centres on column 2.
        """
        with pytest.raises(ValueError, match="but its middle is column 2"):
            _Machine([" ( )", " │  ", "(( ))"], ScriptedIO(""))

    def test_horizontal_entry_at_an_end_cell_is_allowed(self) -> None:
        """Horizontal entry lands on an end cell and is not an error.

        A node occupies one row, so a horizontal neighbour can only ever be
        just past its first or last cell -- the spec's middle rule is about
        vertical paths, and the wiki's Kolakoski program chains nodes this
        way throughout its top row.
        """
        machine = _Machine(["( )─[ }─(( ))"], ScriptedIO(""))
        assert machine.nodes[(0, 4)][0] == "[ }"

    def test_a_rail_passing_beside_a_node_is_not_an_entry(self) -> None:
        """Only a path arm pointing *at* a node counts as entering it.

        ``─`` has no vertical arm, so one drawn above a node's off-centre
        column is passing by rather than connecting into it.
        """
        machine = _Machine(["( )────┐  ", "───────┼──", " (( ))─┘  "], ScriptedIO(""))
        assert machine.nodes[(2, 1)][0] == "(( ))"


class TestPointersStop:
    """Every way a pointer runs out of places to go.

    A pointer stops rather than erroring whenever its next step would leave
    the grid or lead nowhere, so each of these programs halts quietly with
    nothing printed.  They are stepped with a bound rather than run to
    completion, because a program that never halts would hang the suite.
    """

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
    """Junctions where neither memory nor the current heading settles the exit.

    Three of the interpreter's tie-breaks only matter when the obvious answer
    is unavailable: the pointer's own heading is not among a junction's arms,
    or a switch's chosen turn is not among a node's exits.  Both need a grid
    drawn for them -- the wiki's examples always leave the heading available.
    """

    def test_head_on_junction_falls_past_the_heading(self) -> None:
        """A rail entered head-on turns, because straight on is not an arm.

        ``├`` carries up, down, and right.  Arriving travelling *left* takes
        right away as the way back, so the arms are up and down and the
        pointer's own heading is neither.  Nothing is remembered on a first
        visit either, so the first arm is taken -- upward here, which is the
        branch that prints.
        """
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

        The switch is entered from above and its only exits are sideways, so
        ``{ }`` (which clears the register, choosing "carry on") asks for a
        direction that is not there.  The pointer leaves by the first exit
        instead, and the empty register prints zero.
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
        """The same grid, with the turn available: the switch does turn.

        This is the control for the test above -- it shows the empty-register
        case is choosing a different exit, not merely failing to print.
        """
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


class TestThePointerMemoryIsAValue:
    """The memory is a map keyed by cell, and still a value.

    It was a tuple of pairs, which made reading one cell a scan and
    recording one a rebuild.  These pin what the new spelling has to keep:
    a record leaves the original alone, so two generations can be compared
    and a loop proved.
    """

    def test_recording_leaves_the_original_alone(self) -> None:
        """A fork shares a memory, so recording must not edit it."""
        from esolangs.interpreters.grid_based.flowchart import _Memory

        before = _Memory({(0, 0): (1, 0)})
        after = before.leaving((1, 1), (0, 1))
        assert before.exit_from((1, 1)) is None
        assert after.exit_from((1, 1)) == (0, 1)
        assert after.exit_from((0, 0)) == (1, 0)

    def test_a_later_exit_replaces_an_earlier_one(self) -> None:
        """A cell is remembered by its *last* exit, not its first."""
        from esolangs.interpreters.grid_based.flowchart import _Memory

        twice = _Memory({}).leaving((0, 0), (1, 0)).leaving((0, 0), (0, 1))
        assert twice.exit_from((0, 0)) == (0, 1)
        assert twice.sorted_items() == (((0, 0), (0, 1)),)

    def test_equal_memories_compare_and_hash_together(self) -> None:
        """Equality is the exits recorded; the hash follows it."""
        from esolangs.interpreters.grid_based.flowchart import _Memory

        one = _Memory({(0, 0): (1, 0)})
        two = _Memory({}).leaving((0, 0), (1, 0))
        assert one == two
        assert len({one, two}) == 1
        assert hash(one) == hash(one)

    def test_a_memory_is_unequal_to_other_things(self) -> None:
        """Comparing against a non-memory answers False rather than raising."""
        from esolangs.interpreters.grid_based.flowchart import _Memory

        assert _Memory({}) != ()


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
    machine.step()
    machine.step()
    assert machine.ip == (1, 5, -1, 0)
