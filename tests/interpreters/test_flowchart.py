"""Unit tests for the Flowchart interpreter.

The wiki page carries three worked examples -- a truth machine, a cat, and a
Kolakoski-sequence generator -- and they are the ground truth here, because
the spec leaves the switch's orientation, the re-entry rule, the empty
register's I/O, and the pointer interleaving unstated.  See the module
docstring of ``esolangs.interpreters.grid_based.flowchart`` for how each of
those gaps is resolved and which example pins it down.
"""

import pytest

from esolangs.interpreters.grid_based.flowchart import _Machine, run
from esolangs.interpreters.io import ScriptedIO
from esolangs.vm import run_until_halt_or_cycle

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
        """A one takes the left branch onto the ring and never stops.

        Each lap of the ring emits one bit, so the count grows with the
        step budget; what matters is that every bit is a one and that more
        of them arrive the longer the machine runs.
        """
        short = run_steps(TRUTH_MACHINE, "1", 100)
        long = run_steps(TRUTH_MACHINE, "1", 400)
        assert set(short) == {"1"}
        assert set(long) == {"1"}
        assert len(long) > len(short)

    def test_one_never_halts(self) -> None:
        """The looping branch still has a live pointer after many steps."""
        machine = _Machine(TRUTH_MACHINE, ScriptedIO("1"))
        for _ in range(500):
            machine.step()
        assert not machine.halted

    def test_one_is_a_provable_cycle(self) -> None:
        """The looping branch revisits an exact state, proving the hang."""
        machine = _Machine(TRUTH_MACHINE, ScriptedIO("1"))
        assert run_until_halt_or_cycle(machine) is False

    def test_zero_is_reported_as_halting(self) -> None:
        """The halting branch is not mistaken for a cycle."""
        machine = _Machine(TRUTH_MACHINE, ScriptedIO("0"))
        assert run_until_halt_or_cycle(machine) is True


class TestCat:
    """The wiki's cat, which pins the re-entry rule and the empty register."""

    @pytest.mark.parametrize(
        "bits",
        ["1", "0", "101", "1101", "000", "111"],
    )
    def test_echoes_its_input(self, bits: str) -> None:
        """Every bit read is printed back, in order, and the program ends."""
        assert run_program(CAT, "\n".join(bits)) == bits

    def test_no_input_prints_nothing(self) -> None:
        """With no bits to read the deque stays empty and nothing is output."""
        assert run_program(CAT, "") == ""

    def test_halts_rather_than_looping(self) -> None:
        """The exhausted read sends the pointer forward to the end node."""
        machine = _Machine(CAT, ScriptedIO("1\n0\n1"))
        assert run_until_halt_or_cycle(machine) is True

    def test_no_trailing_zero_from_the_empty_register(self) -> None:
        """The final lap's empty register prints nothing.

        The spec's table says "empty is zero", but the last lap of this very
        program pops an exhausted deque and reaches the output node with an
        empty register -- printing a zero there would append a bit the cat
        never read.

        This pins a judgment call, not a fact the wiki states outright: the
        page's diagrams were never run, so the cat may simply be buggy and
        the prose may mean what it says.  See the interpreter's module
        docstring for why the example won here, and flip both together if
        that call is ever revisited.
        """
        assert not run_program(CAT, "\n".join("101")).endswith("1010")


class TestKolakoski:
    """The wiki's Kolakoski example, the one that forks into two pointers."""

    def test_start_node_forks_in_reading_order(self) -> None:
        """The opening ``( )`` splits east first, then south.

        The spec orders pointers "top-most left-most, traveling right, then
        downwards", so the east path on row 0 precedes the south path on
        row 1.
        """
        machine = _Machine(KOLAKOSKI, ScriptedIO(""))
        assert [(p.x, p.y) for p in machine.pointers] == [(3, 0), (1, 1)]

    def test_it_keeps_producing_output(self) -> None:
        """The generator is infinite, so it runs on rather than halting."""
        machine = _Machine(KOLAKOSKI, ScriptedIO(""))
        for _ in range(400):
            machine.step()
        assert not machine.halted

    def test_output_prefix(self) -> None:
        """Characterization only: the wiki states no expected output.

        The page gives the program but never says what it should print, so
        this pins the current behaviour against regressions rather than
        claiming the wiki blesses it.

        The interleaving turns out to matter far less than expected: running
        the two pointers in creation order, reverse order, or re-sorted into
        reading order every step all give byte-identical output, and giving
        each pointer long consecutive runs instead of single steps only
        swaps the first two bits (the south branch prints one ``0`` and
        halts, so scheduling decides whether it lands before or after the
        east branch's first bit).  The repeating ``100110011001`` tail is
        identical under every policy tried, and also under every combination
        of the two contested semantic rules (see the roadmap entry), so it
        is neither an interleaving nor a routing artifact.

        The east pointer in fact emits one bit and halts eleven nodes in:
        the mid-row ``( )`` nodes do not fork, because the ``─`` run under
        them is the return rail passing *beneath* the row rather than a
        path attached to them -- both its ends turn upward, closing the
        loop elsewhere.  The tail is entirely the south branch's, and the
        open question is whether the diagram generates the sequence at all
        as drawn.
        """
        assert run_steps(KOLAKOSKI, "", 400) == "01111001100110011001"


class TestParsing:
    """Grid parsing, node spellings, and malformed programs."""

    def test_longer_spellings_win(self) -> None:
        """``\\[ ]/`` is one push node, not a ``[ ]`` toggle inside noise."""
        machine = _Machine(["( )─\\[ ]/─(( ))"], ScriptedIO(""))
        assert machine.nodes[(4, 0)][0] == "\\[ ]/"

    def test_end_node_is_not_read_as_a_start(self) -> None:
        """``(( ))`` is matched before ``( )`` so an end never starts a run."""
        machine = _Machine(["(( ))─( )"], ScriptedIO(""))
        assert machine.nodes[(0, 0)][0] == "(( ))"

    def test_program_without_a_start_is_rejected(self) -> None:
        """A grid with no ``( )`` has nowhere to begin."""
        with pytest.raises(ValueError, match="no '\\( \\)' start node"):
            _Machine(["(( ))"], ScriptedIO(""))

    def test_unknown_character_is_rejected(self) -> None:
        """Anything that is neither a node, a line, nor a space is an error."""
        with pytest.raises(ValueError, match="unknown character"):
            _Machine(["( )─?─(( ))"], ScriptedIO(""))

    def test_empty_program_is_rejected(self) -> None:
        """An empty grid has no start node either."""
        with pytest.raises(ValueError, match="no '\\( \\)' start node"):
            _Machine([], ScriptedIO(""))

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
        assert machine.nodes[(4, 0)][0] == "[ }"

    def test_a_rail_passing_beside_a_node_is_not_an_entry(self) -> None:
        """Only a path arm pointing *at* a node counts as entering it.

        ``─`` has no vertical arm, so one drawn above a node's off-centre
        column is passing by rather than connecting into it.
        """
        machine = _Machine(["( )────┐  ", "───────┼──", " (( ))─┘  "], ScriptedIO(""))
        assert machine.nodes[(1, 2)][0] == "(( ))"


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

    def test_pop_from_empty_leaves_it_empty(self) -> None:
        """Popping an exhausted deque clears the register."""
        assert self._register("[ }─\\{ }/") is None

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

    def test_output_of_an_empty_register_prints_nothing(self) -> None:
        """An empty register writes no character at all."""
        assert run_program(["( )─\\ \\─(( ))"]) == ""

    def test_input_reads_one_bit_per_line(self) -> None:
        """``/ /`` takes one bit from each line of input."""
        assert run_program(["( )─/ /─\\ \\─/ /─\\ \\─(( ))"], "1\n0") == "10"

    def test_exhausted_input_leaves_the_register_empty(self) -> None:
        """Reading past the end of the input empties the register."""
        assert run_program(["( )─/ /─\\ \\─(( ))"], "") == ""


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

    def test_start_with_no_exits_stops_immediately(self) -> None:
        """A start node with nothing attached has nowhere to send a pointer."""
        assert self._halts(["( )"])
        assert run_program(["( )"]) == ""

    def test_stepping_a_halted_machine_does_nothing(self) -> None:
        """``step`` returns early once every pointer is done."""
        machine = _Machine(["( )"], ScriptedIO(""))
        machine.step()
        assert machine.halted
        machine.step()  # the early return: no pointer is live to advance
        assert machine.halted

    def test_rail_running_off_the_grid_stops(self) -> None:
        """A rail that reaches the edge stops instead of stepping outside."""
        assert self._halts(["( )─"])
        assert self._halts(["( )", " │ "])

    def test_rail_into_a_gap_stops(self) -> None:
        """A rail that ends in blank space has no cell to continue into."""
        assert self._halts(["( )─ ─"])

    def test_node_with_no_onward_rail_stops(self) -> None:
        """A node reached by a rail but leading nowhere stops the pointer."""
        assert self._halts(["( )─\\[ ]/"])
        assert self._halts(["( )─< >"])
        assert self._halts(["( )─{ }"])

    def test_start_touching_only_another_node_stops(self) -> None:
        """A start whose sole neighbour is the node it came from forks nowhere."""
        assert self._halts(["( )( )"])
