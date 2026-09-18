"""The five hang detectors, and the bounded drive beside them.

Each proves a different shape of non-termination -- an exact repeat, a
recursion replaying an ancestor, a tape growing by translation, a cell
climbing affinely, every random branch cycling -- and each has to raise
rather than guess on a program it cannot decide.
"""

import re

import pytest

import esolangs


def _painfuck_source(targets: str) -> str:
    """Encode direct Painfuck commands through its source translation."""
    cycles = ("pevkjzwr", "yuctsobqihald")
    out: list[str] = []
    for index, target in enumerate(targets):
        cycle = next(cycle for cycle in cycles if target in cycle)
        out.append(cycle[(cycle.index(target) - index) % len(cycle)])
    return "".join(out)


def _read_cell(state: object) -> int:
    """Return the cell under the pointer of a Super SNUSP branching state."""
    _row, _col, _heading, pointer, cells, *_rest = state  # type: ignore[misc]
    return next((value for index, value in cells if index == pointer), 0)


class TestRunUntilHaltOrCycle:
    def test_wii2d_all_random_turns_can_be_proved_to_loop(self) -> None:
        """Every heading from ``?`` returns to this two-cell ring.

        Running one seeded trace would only show that seed loops.  The
        branching detector must visit all four headings and may return a
        hang verdict only after they merge back into the same finite graph.
        The two fixed traces are the execution control: both are actual
        interpreter runs, not a hand-written successor table.
        """
        from esolangs.interpreters.grid_based.wii2d import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.randomness import FirstDraw
        from esolangs.vm import (
            run_until_halt_or_all_branches_cycle,
            run_until_halt_or_cycle,
        )

        code = [">?", "! "]
        assert (
            run_until_halt_or_all_branches_cycle(_Machine(code, ScriptedIO())) is False
        )
        for turn in range(4):
            assert (
                run_until_halt_or_cycle(
                    _Machine(code, ScriptedIO(), FirstDraw(turn, rest=turn))
                )
                is False
            )

    def test_wii2d_one_halting_turn_refutes_an_all_branches_hang(self) -> None:
        from esolangs.interpreters.grid_based.wii2d import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.randomness import FirstDraw
        from esolangs.vm import (
            run_until_halt_or_all_branches_cycle,
            run_until_halt_or_cycle,
        )

        # East or west lands on '.', while north/south return to '?'.
        code = ["?.", "! "]
        assert (
            run_until_halt_or_all_branches_cycle(_Machine(code, ScriptedIO())) is True
        )
        assert (
            run_until_halt_or_cycle(_Machine(code, ScriptedIO(), FirstDraw(3))) is True
        )
        assert (
            run_until_halt_or_cycle(_Machine(code, ScriptedIO(), FirstDraw(0, rest=0)))
            is False
        )

    def test_painfuck_all_coin_outcomes_can_be_proved_to_loop(self) -> None:
        """Either ``y`` outcome reaches a loop close and returns to ``a``."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.randomness import FirstDraw
        from esolangs.interpreters.tape_based.painfuck import _Machine
        from esolangs.vm import (
            run_until_halt_or_all_branches_cycle,
            run_until_halt_or_cycle,
        )

        # p makes the loop live; y either takes the first b or skips to the
        # second, and both b commands return to a.
        code = _painfuck_source("paybb")
        assert (
            run_until_halt_or_all_branches_cycle(_Machine(code, ScriptedIO())) is False
        )
        for coin in (0, 1):
            assert (
                run_until_halt_or_cycle(
                    _Machine(code, ScriptedIO(), FirstDraw(coin, rest=coin))
                )
                is False
            )

    def test_painfuck_one_halting_coin_refutes_an_all_branches_hang(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.randomness import FirstDraw
        from esolangs.interpreters.tape_based.painfuck import _Machine
        from esolangs.vm import (
            run_until_halt_or_all_branches_cycle,
            run_until_halt_or_cycle,
        )

        code = _painfuck_source("payb")
        assert (
            run_until_halt_or_all_branches_cycle(_Machine(code, ScriptedIO())) is True
        )
        assert (
            run_until_halt_or_cycle(_Machine(code, ScriptedIO(), FirstDraw(1))) is True
        )
        assert (
            run_until_halt_or_cycle(_Machine(code, ScriptedIO(), FirstDraw(0, rest=0)))
            is False
        )

    def test_painfuck_a_malformed_loop_is_a_terminal_branch(self) -> None:
        """An unmatched ``b`` ends its branch instead of escaping the search.

        ``run`` treats a malformed loop as an error outcome, and the branch
        graph has no error flag to carry that, so the successor is the same
        state with its cursor moved past the program -- which is exactly
        what ``branching_halted`` reads as finished.  Letting the exception
        out instead would abort the whole search over a branch that simply
        ended.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.painfuck import _Machine

        machine = _Machine(_painfuck_source("b"), ScriptedIO())
        start = machine.branching_snapshot()
        assert machine.branching_halted(start) is False

        (ended,) = machine.branching_successors(start, 100) or ()
        assert machine.branching_halted(ended) is True
        assert ended[3] == machine.n  # cursor parked past the program

    def test_laserfuck_all_initial_headings_can_be_proved_to_loop(self) -> None:
        """The four headings are searched, not the one the machine drew.

        Each orthogonal neighbour of ``o`` sends the beam straight back
        through it, so every heading oscillates forever and no draw escapes.
        """
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.randomness import FirstDraw
        from esolangs.vm import (
            run_until_halt_or_all_branches_cycle,
            run_until_halt_or_cycle,
        )

        code = [" v ", "}o{", " ^ "]
        assert (
            run_until_halt_or_all_branches_cycle(_Machine(code, ScriptedIO())) is False
        )
        for heading in range(4):
            assert (
                run_until_halt_or_cycle(
                    _Machine(code, ScriptedIO(), FirstDraw(heading, rest=heading))
                )
                is False
            )

    def test_laserfuck_one_halting_heading_refutes_an_all_branches_hang(self) -> None:
        """Up and down leave the grid; left and right bounce forever."""
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.randomness import FirstDraw
        from esolangs.vm import (
            run_until_halt_or_all_branches_cycle,
            run_until_halt_or_cycle,
        )

        code = ["}o{"]
        assert (
            run_until_halt_or_all_branches_cycle(_Machine(code, ScriptedIO())) is True
        )
        assert (
            run_until_halt_or_cycle(_Machine(code, ScriptedIO(), FirstDraw(0))) is True
        )
        assert (
            run_until_halt_or_cycle(_Machine(code, ScriptedIO(), FirstDraw(2, rest=2)))
            is False
        )

    def test_laserfuck_grid_without_a_start_marker_places_no_beam(self) -> None:
        """A laserless grid reports empty beams, never the unplaced sentinel.

        The verdict alone cannot see the difference: a sentinel here would
        invent a beam at the grid's origin, and the origin is a corner, so
        two of its four headings leave the grid at once and report a halt --
        the right answer for the wrong run.  So the state is asserted
        directly, and a grid whose corner would *loop* is what the assertion
        protects against.
        """
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import run_until_halt_or_all_branches_cycle

        machine = _Machine(["+-", "<>"], ScriptedIO())
        assert machine.halted is True
        assert machine.branching_snapshot()[2] == ()
        assert machine.branching_halted(machine.branching_snapshot()) is True
        assert run_until_halt_or_all_branches_cycle(machine) is True

    def test_laserfuck_search_skips_the_command_after_a_hash(self) -> None:
        """``#`` skips in the search exactly as it does in a step.

        A successor that called the transition on the skipped cell would
        turn the beam here, since ``{`` sets the heading to left.  The
        skip is asserted on the states rather than through a verdict:
        every grid tried reaches the same answer either way, so the
        difference is visible only in where the beam ends up.
        """
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO

        machine = _Machine(["o#{"], ScriptedIO())
        start = machine.branching_snapshot()
        rightward = next(
            state
            for state in machine.branching_successors(start, 100) or ()
            if state[2] is not None and state[2][0][2] == 3
        )

        (at_hash,) = machine.branching_successors(rightward, 100) or ()
        assert at_hash[2] == ((0, 1, 3),)
        assert at_hash[4] is True, "'#' arms the skip"

        (skipped,) = machine.branching_successors(at_hash, 100) or ()
        assert skipped[2] == ((0, 2, 3),), "'{' was passed over, not executed"
        assert skipped[4] is False, "the skip disarms itself"

    def test_laserfuck_a_placed_beam_starts_the_search_unplaced(self) -> None:
        """The complement: a grid *with* an ``o`` does use the sentinel."""
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO

        machine = _Machine(["o"], ScriptedIO())
        assert machine.branching_snapshot()[2] is None
        assert machine.branching_halted(machine.branching_snapshot()) is False

    def test_laserfuck_explores_both_beam_splitter_outcomes(self) -> None:
        """``*``'s coin is searched, not sampled.

        The whole verdict rests on the second outcome here: a splitter that
        always chose ``0`` would loop under every one of the four headings,
        and only a ``1`` at the right moment reaches a halt.  So a search
        that tried one outcome per split would answer ``False`` -- claiming
        a program that can terminate never does.
        """
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.randomness import FirstDraw
        from esolangs.vm import (
            run_until_halt_or_all_branches_cycle,
            run_until_halt_or_cycle,
        )

        code = ["/{v", "^o^", "*/*"]
        for heading in range(4):
            assert (
                run_until_halt_or_cycle(
                    _Machine(code, ScriptedIO(), FirstDraw(heading, rest=0))
                )
                is False
            )
        assert (
            run_until_halt_or_cycle(_Machine(code, ScriptedIO(), FirstDraw(1, rest=1)))
            is True
        )
        assert (
            run_until_halt_or_all_branches_cycle(
                _Machine(code, ScriptedIO()), limit=5000
            )
            is True
        )

    def test_laserfuck_a_second_start_marker_halts_every_branch(self) -> None:
        """Two ``o``s stop the machine before it can draw a heading."""
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import run_until_halt_or_all_branches_cycle

        machine = _Machine(["oo"], ScriptedIO())
        assert machine.halted is True
        assert run_until_halt_or_all_branches_cycle(machine) is True

    def test_laserfuck_declines_a_reachable_input_command(self) -> None:
        """``,`` cannot be forked, so the search reports undecided.

        The command has to sit where the beam *arrives*, not under ``o``
        itself: a step moves before it executes, so the start cell is the
        one cell a run never runs.
        """
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import run_until_halt_or_all_branches_cycle

        with pytest.raises(TimeoutError, match="needs input"):
            run_until_halt_or_all_branches_cycle(_Machine(["o,"], ScriptedIO("A\n")))

    def test_super_snusp_mirror_ring_loops_under_every_draw(self) -> None:
        """A ``/`` ring circulates forever, and no draw escapes it."""
        from esolangs.interpreters.grid_based.super_snusp import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import (
            run_until_halt_or_all_branches_cycle,
            run_until_halt_or_cycle,
        )

        code = ["///", '/"/', "///"]
        assert (
            run_until_halt_or_all_branches_cycle(
                _Machine(code, ScriptedIO()), limit=3000
            )
            is False
        )
        assert run_until_halt_or_cycle(_Machine(code, ScriptedIO())) is False

    def test_super_snusp_forks_every_value_equals_could_store(self) -> None:
        """``=`` picks from the span between the cell and the stack top.

        ``3`` writes 3, ``{`` pushes it, ``(`` drops the cell to 2, so the
        span is ``[2..3]`` -- two outcomes, against the one a command
        without a draw would produce.
        """
        from esolangs.interpreters.grid_based.super_snusp import _Machine
        from esolangs.interpreters.io import ScriptedIO

        machine = _Machine(['"3{(='], ScriptedIO())
        state = machine.branching_snapshot()
        for _ in range(4):  # '"', '3', '{', '(' -- all deterministic
            successors = machine.branching_successors(state, 100)
            assert successors is not None
            assert len(successors) == 1, "only '=' draws"
            (state,) = successors

        at_equals = machine.branching_successors(state, 100)
        assert at_equals is not None
        stored = sorted(_read_cell(nxt) for nxt in at_equals)
        assert stored == [2, 3], "both ends of the span are reachable"

    def test_super_snusp_declines_input_and_caps_a_wide_span(self) -> None:
        """The two undecided cases, both raising rather than guessing."""
        from esolangs.interpreters.grid_based.super_snusp import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import run_until_halt_or_all_branches_cycle

        with pytest.raises(TimeoutError, match="needs input"):
            run_until_halt_or_all_branches_cycle(_Machine(['",'], ScriptedIO("A\n")))
        with pytest.raises(TimeoutError, match="needs input"):
            run_until_halt_or_all_branches_cycle(_Machine(['"@'], ScriptedIO("1\n")))

        # Digits accumulate into 999, '{' pushes it, and '>' moves to a
        # fresh zero cell, so '=' spans 1000 values -- past the cap a single
        # transition may open, whatever budget the caller allows.
        wide = _Machine(['"999{>='], ScriptedIO())
        with pytest.raises(TimeoutError, match=r"exceeds the .* cap"):
            run_until_halt_or_all_branches_cycle(wide, limit=100000)

    def test_modulous_reset_loops_and_end_halts(self) -> None:
        """``RST`` rewinds the cursor forever; ``END`` stops."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.modulous import _Machine
        from esolangs.vm import (
            run_until_halt_or_all_branches_cycle,
            run_until_halt_or_cycle,
        )

        assert (
            run_until_halt_or_all_branches_cycle(_Machine("[RST]", ScriptedIO()))
            is False
        )
        assert run_until_halt_or_cycle(_Machine("[RST]", ScriptedIO())) is False
        assert (
            run_until_halt_or_all_branches_cycle(_Machine("[END]", ScriptedIO()))
            is True
        )

    def test_modulous_forks_every_value_rnd_could_draw(self) -> None:
        """``RND n`` opens exactly ``n`` outcomes, one per drawable value."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.modulous import _Machine

        machine = _Machine("[RND 4]", ScriptedIO())
        successors = machine.branching_successors(machine.branching_snapshot(), 100)
        assert successors is not None
        assert sorted(state[0][0][-1] for state in successors) == [0, 1, 2, 3]

        # A bound below one is not a quiet no-op: the handler rejects it,
        # so the search raises exactly where a step would.
        from esolangs.exceptions import HaltError

        quiet = _Machine("[RND 0]", ScriptedIO())
        with pytest.raises(HaltError):
            quiet.branching_successors(quiet.branching_snapshot(), 100)

    def test_modulous_non_command_tokens_advance_one_branch(self) -> None:
        """A token no handler claims still steps, and forks nothing.

        Three shapes reach the branch search without a handler: an empty
        token, a bare word, and a variable assignment.  Only the last
        changes anything -- ``VAR1+1`` is arithmetic the dispatch table does
        not list -- and none of them opens a second outcome, so each must
        return exactly one successor rather than ``None`` (which would
        claim the step needs input) or a fork.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.modulous import _Machine

        for code in ("[]", "[FOO]", "[VAR1+1]", "[VAR1-1]"):
            machine = _Machine(code, ScriptedIO())
            successors = machine.branching_successors(machine.branching_snapshot(), 100)
            assert successors is not None, code
            assert len(successors) == 1, code

        # The arithmetic token is the only one that writes a variable, and
        # the bare word leaves the state alone apart from the cursor.
        for token, expected in (("[VAR1+1]", 1), ("[VAR1-1]", -1)):
            arith = _Machine(token, ScriptedIO())
            (stepped,) = (
                arith.branching_successors(arith.branching_snapshot(), 100) or ()
            )
            assert dict(stepped[0][1])["VAR1"] == expected, token

        word = _Machine("[FOO]", ScriptedIO())
        start = word.branching_snapshot()
        (after,) = word.branching_successors(start, 100) or ()
        assert after[0][0] == start[0][0]  # stack untouched
        assert after[0][2] == start[0][2] + 1  # cursor advanced one token

    def test_modulous_declines_input_and_caps_a_wide_draw(self) -> None:
        """``INP`` cannot be forked, and one ``RND`` cannot be unbounded."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.modulous import _Machine
        from esolangs.vm import run_until_halt_or_all_branches_cycle

        with pytest.raises(TimeoutError, match="needs input"):
            run_until_halt_or_all_branches_cycle(_Machine("[INP]", ScriptedIO("A\n")))
        with pytest.raises(TimeoutError, match=r"exceeds the .* cap"):
            run_until_halt_or_all_branches_cycle(
                _Machine("[RND 100000]", ScriptedIO()), limit=100000
            )

    def test_cod_searches_every_launch_heading(self) -> None:
        """A start with two ways out is quantified over, not sampled.

        ``__init__`` draws the launch heading, so a search starting from the
        live machine would answer for the one it happened to pick.  The
        unlaunched state opens into both instead.
        """
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO

        machine = _Machine(">  \n   ", ScriptedIO())
        start = machine.branching_snapshot()
        assert start is None, "two exits, so the search starts before the launch"

        launched = machine.branching_successors(start, 100)
        assert launched is not None
        assert sorted(cods[0].d for cods in launched) == ["E", "S"]

        # One exit is no choice at all, so that machine starts launched: the
        # search has nothing to quantify over and begins from the live cod.
        single = _Machine("> \n~~", ScriptedIO())
        assert single.branching_snapshot() == single.cods

    def test_cod_corridor_loops_and_a_dash_halts(self) -> None:
        """The two verdicts, against the deterministic detector."""
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import (
            run_until_halt_or_all_branches_cycle,
            run_until_halt_or_cycle,
        )

        # A blind corridor: the cod swims to the end, reverses, and repeats.
        assert (
            run_until_halt_or_all_branches_cycle(_Machine(">  ", ScriptedIO())) is False
        )
        assert run_until_halt_or_cycle(_Machine(">  ", ScriptedIO())) is False
        # '-' removes the only cod, so the pond empties.
        assert (
            run_until_halt_or_all_branches_cycle(_Machine("> -", ScriptedIO())) is True
        )

    def test_cod_forks_a_blocked_junction_both_ways(self) -> None:
        """A junction draws only when forward is blocked.

        The cod swims east into a wall with north and south both open, and
        the way it came from excluded -- so the tick opens two successors
        where an unblocked cell opens one.
        """
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO

        machine = _Machine("~ ~\n> ~\n~ ~", ScriptedIO())
        state = machine.branching_snapshot()

        straight = machine.branching_successors(state, 100)
        assert straight is not None
        assert len(straight) == 1, "an open cell ahead is no junction"
        (state,) = straight

        junction = machine.branching_successors(state, 100)
        assert junction is not None
        assert sorted(cods[0].d for cods in junction) == ["N", "S"]

    def test_cod_declines_a_read_and_caps_a_wide_tick(self) -> None:
        """A tick draws once per blocked cod, so its fanout is a product.

        ``+`` breeds cods faster than the pond kills them, and each one at a
        junction multiplies the tick's outcomes, so the cap is reached in a
        few dozen states rather than at some distant horizon.
        """
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import run_until_halt_or_all_branches_cycle

        with pytest.raises(TimeoutError, match="needs input"):
            run_until_halt_or_all_branches_cycle(
                _Machine(">..\n ..\n ..", ScriptedIO("7\n"))
            )
        with pytest.raises(TimeoutError, match=r"exceeds the .* cap"):
            run_until_halt_or_all_branches_cycle(
                _Machine("> +  \n     \n     ", ScriptedIO()), limit=200000
            )

    def test_branching_search_leaves_unbounded_or_input_paths_undecided(self) -> None:
        from esolangs.interpreters.grid_based.wii2d import _Machine as Wii2dMachine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.painfuck import (
            _Machine as PainfuckMachine,
        )
        from esolangs.vm import run_until_halt_or_all_branches_cycle

        with pytest.raises(TimeoutError, match="reachable graph may be unbounded"):
            run_until_halt_or_all_branches_cycle(
                Wii2dMachine([">?", "! "], ScriptedIO()), limit=1
            )
        # A source program whose translation is the direct target 'j'.
        # The detector must not let sibling paths share its input cursor.
        with pytest.raises(TimeoutError, match="needs input"):
            run_until_halt_or_all_branches_cycle(
                PainfuckMachine(_painfuck_source("j"), ScriptedIO("A\n"))
            )
        # c repeats y 49 times.  Limiting the frontier at the transition,
        # rather than after materializing its 2**49 outcomes, keeps the
        # detector a bounded attempt rather than an accidental OOM.
        with pytest.raises(TimeoutError, match="coin outcomes"):
            run_until_halt_or_all_branches_cycle(
                PainfuckMachine(_painfuck_source("ccy"), ScriptedIO()), limit=4
            )

    def test_sbleq_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # a=0 b=0 c=3: diff (0-0=0) jumps to mem[3], which is negative -> halts
        machine = _Machine("0 0 3 -1", ScriptedIO(), store="a")
        assert run_until_halt_or_cycle(machine) is True

    def test_sbleq_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # a=0 b=0 c=2: diff is always 0, so it jumps to mem[2] (address 0) forever
        machine = _Machine("0 0 0", ScriptedIO(), store="a")
        assert run_until_halt_or_cycle(machine) is False

    def test_dimensional_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.dimensional import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine("+.", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is True

    def test_dimensional_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.dimensional import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # cell starts nonzero and the loop body never changes it, so it never exits
        machine = _Machine("+[]", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is False

    def test_modulous_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.modulous import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine("[END]", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is True

    def test_modulous_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.modulous import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # RST resets the pointer to the start of the program on every pass
        machine = _Machine("[RST]", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is False

    def test_laserfuck_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.randomness import FirstDraw
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine(["o"], ScriptedIO(), rng=FirstDraw(0))
        assert run_until_halt_or_cycle(machine) is True

    def test_laserfuck_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.randomness import FirstDraw
        from esolangs.vm import run_until_halt_or_cycle

        # a closed ring of mirrors the laser circles forever
        grid = ["/ \\", "\\o/", "//\\"]
        machine = _Machine(grid, ScriptedIO(), rng=FirstDraw(2))
        assert run_until_halt_or_cycle(machine) is False

    def test_slow_acv_mammalian_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine("PRONOUNCE", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is True

    def test_slow_acv_mammalian_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # LEAPFROG jumps back to a point that reproduces the exact same state
        machine = _Machine(
            "CONFLAGRATE SEED SEED DIGEST FISSION LEAPFROG", ScriptedIO()
        )
        assert run_until_halt_or_cycle(machine) is False

    def test_a_machine_already_halted_is_reported_as_halting(self) -> None:
        """The loop is never entered, and the answer is still ``True``.

        Every other path returns from inside the walk, so the ``return``
        after it is reached only by a machine that arrived finished.  A
        sweep found it free to say ``False`` -- which would report a
        program that has already run to completion as a hang.
        """
        from esolangs.vm import run_until_halt, run_until_halt_or_cycle

        vm = esolangs.make_vm("brainfuck", "++")
        run_until_halt(vm)
        assert vm.halted
        assert run_until_halt_or_cycle(vm) is True

    def test_forbin_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.forbin import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine("main { x = 1; }", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is True

    def test_forbin_for_loop_halts_without_a_false_cycle(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.forbin import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # each row sets the same local to the same value, so only the loop's
        # own row index (part of the snapshot) keeps this from reading as a
        # repeat before the finite range is exhausted
        machine = _Machine("main { for i:0..1 { x = 0; } }", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is True

    def test_forth_replayed_scope_is_detected_as_an_ancestor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.forth import _Machine
        from esolangs.vm import run_until_halt_or_ancestor

        # Store 1; under key 1, then have that scope call itself forever.
        assert run_until_halt_or_ancestor(_Machine("1{1;}1;", ScriptedIO())) is False

    def test_forth_changing_stack_halts(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.forth import _Machine
        from esolangs.vm import run_until_halt_or_ancestor

        # The scope decrements its shared counter before conditionally
        # calling itself, so every entered scope has a different binding.
        assert (
            run_until_halt_or_ancestor(_Machine("1{1-(1;)}3v;", ScriptedIO())) is True
        )

    def test_jaune_replayed_subroutine_is_detected_as_an_ancestor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.jaune import _Machine
        from esolangs.vm import run_until_halt_or_ancestor

        # Main calls subroutine 1, whose body immediately calls itself.
        assert run_until_halt_or_ancestor(_Machine("1@.1$1@;", ScriptedIO())) is False

    def test_jaune_changing_tape_halts(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.jaune import _Machine
        from esolangs.vm import run_until_halt_or_ancestor

        # Subroutine 1 decrements the tape then recurs until the zero case
        # jumps to its return, so the tape belongs in the entry key.
        code = "3+1@.1$1-2!1@;2:;"
        assert run_until_halt_or_ancestor(_Machine(code, ScriptedIO())) is True

    def test_grapheme_replayed_function_is_detected_as_an_ancestor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.grapheme import _Machine
        from esolangs.vm import run_until_halt_or_ancestor

        # The function invokes itself without changing the shared state.
        assert run_until_halt_or_ancestor(_Machine("HKGHKG", ScriptedIO())) is False

    def test_grapheme_changing_stack_halts(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.grapheme import _Machine
        from esolangs.vm import run_until_halt_or_ancestor

        # The function decrements the count before Q recurs, so each entry
        # has a different shared stack and reaches the zero base case.
        program = "H" + "FFTBKFAFDQ" + "H" + "FAFC" + "FAFD" + "G"
        code = "FAF" + program
        assert run_until_halt_or_ancestor(_Machine(code, ScriptedIO())) is True


class TestRunUntilHaltOrGrowth:
    """The unbounded-growth certificate on brainfuck's tape.

    Every program here is run through the real interpreter: the verdicts
    are what stepping ``_Machine`` produced, not a hand-written trace.
    """

    def test_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainfuck import _Machine
        from esolangs.vm import run_until_halt_or_growth

        # `+[>]` walks right off the set cell onto a zero and leaves.
        assert run_until_halt_or_growth(_Machine("+[>]", ScriptedIO())) is True

    def test_growing_loop_is_proved_to_hang(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainfuck import _Machine
        from esolangs.vm import run_until_halt_or_growth

        # The canonical case: one fresh cell and one cell of displacement
        # per lap, so no whole state ever repeats and Brent's never fires.
        assert run_until_halt_or_growth(_Machine("+[>+]", ScriptedIO())) is False

    def test_cycle_detector_cannot_prove_the_growing_loop(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainfuck import _Machine

        # The gap this detector exists to close, asserted rather than
        # described: 5000 steps of `+[>+]` reach no repeated snapshot, so
        # Brent's has nothing to find however long it is given.
        machine = _Machine("+[>+]", ScriptedIO())
        seen = {machine.snapshot()}
        for _ in range(5000):
            machine.step()
            assert machine.snapshot() not in seen
            seen.add(machine.snapshot())
        assert len(seen) == 5001

    def test_certificate_holds_only_above_the_periods_lowest_cell(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainfuck import _Machine
        from esolangs.vm import run_until_halt_or_growth

        # Cell 0 keeps the 1 that `+` left while every later cell fills
        # with 2, so the tape is never a full-width shift of itself.  Only
        # comparing from the period's own minimum pointer proves this one.
        assert run_until_halt_or_growth(_Machine("+[>++]", ScriptedIO())) is False

    def test_certificate_fires_early_rather_than_at_the_limit(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainfuck import _Machine
        from esolangs.vm import run_until_halt_or_growth

        # A limit far below any wall-clock backstop still returns False:
        # the verdict comes from the certificate, not from exhausting a
        # budget, and a mutant that defeats it raises TimeoutError here.
        assert run_until_halt_or_growth(_Machine("+[>+]", ScriptedIO()), 12) is False

    def test_a_reading_loop_is_never_certified(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainfuck import _Machine
        from esolangs.vm import run_until_halt_or_growth

        # The input cursor matters, and this is the input that
        # proves it.  Every lap of `+[>,]` reads the same byte, so the tape
        # really is a clean right-shift of itself and all three of the
        # other conditions hold -- 16 times over, before the input runs
        # out.  Only the moving cursor stands between the certificate and
        # a hang verdict for a program that stops.  Varying input would
        # fail on cell values instead and pass this test for free.
        machine = _Machine("+[>,]", ScriptedIO("a\n" * 6))
        with pytest.raises(EOFError):
            run_until_halt_or_growth(machine, 200)

        # With input still to come at the step limit, the same program is
        # reported undecided rather than as a hang.
        machine = _Machine("+[>,]", ScriptedIO("a\n" * 400))
        with pytest.raises(TimeoutError, match="undecided after"):
            run_until_halt_or_growth(machine, 200)

    def test_a_clamped_loop_is_never_certified(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainfuck import _Machine
        from esolangs.vm import run_until_halt_or_growth

        # `+[<+]` is the reason the certificate demands `m >= 1`.  Its `<`
        # is clamped at cell 0 every lap, so it does not translate -- and
        # it in fact halts, once the cell wraps at 256.  Certifying a
        # left-edge period would have called a halting program a hang.
        machine = _Machine("+[<+]", ScriptedIO())
        assert run_until_halt_or_growth(machine) is True
        assert machine.tape == (0,)

    def test_in_place_cycles_are_left_to_the_cycle_detector(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainfuck import _Machine
        from esolangs.vm import run_until_halt_or_cycle, run_until_halt_or_growth

        # `+[]` spins on one cell: the tape never grows, so the
        # displacement is zero and this detector declines to rule.  The
        # state repeats exactly, which is the cycle detector's to prove.
        with pytest.raises(TimeoutError, match="undecided after"):
            run_until_halt_or_growth(_Machine("+[]", ScriptedIO()), 300)
        assert run_until_halt_or_cycle(_Machine("+[]", ScriptedIO())) is False

    def test_a_growing_run_that_still_halts_is_not_called_a_hang(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainfuck import _Machine
        from esolangs.vm import run_until_halt_or_growth

        # Nine laps of genuine growth, then the counter in cell 0 runs out
        # and the outer loop leaves.  The certificate must not fire on the
        # growth, because the period is not a translation: cell 0 falls.
        program = "+++++++++[>+<-]"
        machine = _Machine(program, ScriptedIO())
        assert run_until_halt_or_growth(machine) is True
        assert machine.tape[1] == 9

    def test_phased_growing_waves_select_their_own_period(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainfuck import _Machine
        from esolangs.vm import run_until_halt_or_growth

        # Each outer lap moves right one cell and maps 1 to 2 or 2 to 1.
        # One lap is therefore not a translated state, but two are.  The
        # old one-visit certificate reached its budget here; the automatic
        # relative-tape checkpoint discovers the two-visit period instead.
        code = "+[>+++<[->-<]>]"
        assert run_until_halt_or_growth(_Machine(code, ScriptedIO()), 1_000) is False

        # This is an executed positive control, not only a state comparison:
        # the real program remains live and keeps extending its tape.
        machine = _Machine(code, ScriptedIO())
        for _ in range(500):
            machine.step()
        assert not machine.halted
        assert len(machine.tape) > 30

    def test_long_phased_wave_is_proved_without_a_period_argument(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainfuck import _Machine
        from esolangs.vm import run_until_halt_or_growth

        # The source cell is copied right and the new cell gains two.  From
        # the initial odd value, that is a 128-phase travelling wave.  Its
        # phase is not exposed by the API; Brent finds it automatically.
        assert run_until_halt_or_growth(_Machine("+[[->+<]>++]", ScriptedIO())) is False

    def test_a_period_that_walks_to_cell_zero_is_undecided(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainfuck import _Machine
        from esolangs.vm import run_until_halt_or_growth

        # `>+[[<]>[>]+]` grows a run of ones forever, but every lap walks
        # to cell 0, so its visits share a frozen prefix rather than
        # translating.  The docstring's ip-counter machine is why no
        # configuration-pair certificate may close this class, and 5,000
        # steps is ~70 laps -- room for any certificate that could fire.
        with pytest.raises(TimeoutError, match="undecided after"):
            run_until_halt_or_growth(_Machine(">+[[<]>[>]+]", ScriptedIO()), 5_000)

        # Executed positive control: the program is live and still growing.
        machine = _Machine(">+[[<]>[>]+]", ScriptedIO())
        for _ in range(5_000):
            machine.step()
        assert not machine.halted
        assert len(machine.tape) == 50

        # Without the append the walk leaves the loop at the first zero,
        # so undecided above is a judgment, not a default.
        assert run_until_halt_or_growth(_Machine(">+[[<]>[>]]", ScriptedIO())) is True

    def test_a_climbing_wave_that_wraps_to_a_halt_is_never_certified(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainfuck import _Machine
        from esolangs.vm import run_until_halt_or_growth

        # `+[[->+<]>+]` copies the cell right and adds one, so the wave
        # climbs as it travels and no two visits translate -- until the
        # value wraps at 256 and the run halts, 164,222 steps in
        # (measured).  Within any smaller budget the only sound answer is
        # undecided; a certificate loose enough to fire on the climb would
        # have called a halting program a hang.
        with pytest.raises(TimeoutError, match="undecided after"):
            run_until_halt_or_growth(_Machine("+[[->+<]>+]", ScriptedIO()), 2_000)


class TestGrowthDetectorAcrossLanguages:
    """The certificate is not brainfuck-specific.

    Four more tape languages satisfy ``_TapeMachine``'s semantic contract,
    and each is checked the same way: a growing program is proved to hang,
    a halting one still halts, and the growing program is *executed* to
    confirm it really grows -- a hang verdict on a program that stops
    would be the one failure this detector must never produce.
    """

    def test_brainif(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainif import _Machine
        from esolangs.vm import run_until_halt_or_growth

        # `if 0 right` / `goto 1` walks right forever, one fresh cell per
        # lap.  Goto targets are 1-based: `goto 0` would park the cursor
        # at -1, which neither halts nor advances.
        growing = ["if 0 right", "if 0 goto 1"]
        assert run_until_halt_or_growth(_Machine(growing, ScriptedIO())) is False

        machine = _Machine(growing, ScriptedIO())
        for _ in range(600):
            assert not machine.halted
            machine.step()
        assert len(machine.cells) > 250

        # The guard fails on the first pass, so the program runs off the end.
        halting = ["if 9 goto 1", "if 0 increment"]
        assert run_until_halt_or_growth(_Machine(halting, ScriptedIO())) is True

    def test_six_five(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.six_five import _Machine
        from esolangs.vm import run_until_halt_or_growth

        # `4` marks, `1` moves right by two, `81` jumps back to the first
        # marker.  Markers are 1-based, so `80` would find none.
        assert run_until_halt_or_growth(_Machine("4181", ScriptedIO())) is False

        machine = _Machine("4181", ScriptedIO())
        for _ in range(600):
            assert not machine.halted
            machine.step()
        assert len(machine.tape) > 250

        # `5` writes the cell before the move, leaving 5s behind and zeros
        # between them: growth that is never a full-width shift of itself,
        # so this is a second language exercising the `i >= m` bound.
        assert run_until_halt_or_growth(_Machine("45181", ScriptedIO())) is False

        # No jump, so the cursor runs off the end.
        assert run_until_halt_or_growth(_Machine("41", ScriptedIO())) is True

    def test_back(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import _Machine
        from esolangs.vm import run_until_halt_or_growth

        # A one-cell grid holding `>`: the beam wraps onto itself and moves
        # one cell right every lap.  This is the case that needs the
        # heading in the key, which `ip` supplies.
        assert run_until_halt_or_growth(_Machine([">"], ScriptedIO())) is False

        machine = _Machine([">"], ScriptedIO())
        for _ in range(600):
            assert not machine.halted
            machine.step()
        assert len(machine.tape) > 250

        # `*` halts the beam.
        assert run_until_halt_or_growth(_Machine([">*"], ScriptedIO())) is True

    def test_factor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.factor import _Machine, decode
        from esolangs.vm import run_until_halt_or_growth

        # Factor is brainfuck as a prime factorization, so the canonical
        # grower has a numeral: 3*7*23*47*107, whose residues mod 11 spell
        # `+[>+]` in ascending prime order.
        assert decode(2429007) == "+[>+]"
        assert run_until_halt_or_growth(_Machine("2429007", ScriptedIO())) is False

        machine = _Machine("2429007", ScriptedIO())
        for _ in range(600):
            assert not machine.halted
            machine.step()
        assert len(machine.tape) > 150

        # 3*7*23*41 spells `+[>]`, which walks onto a zero and leaves.
        assert decode(19803) == "+[>]"
        assert run_until_halt_or_growth(_Machine("19803", ScriptedIO())) is True

    def test_the_heading_is_part_of_the_code_position(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import _Machine
        from esolangs.vm import run_until_halt_or_growth

        # Why the detector keys on `ip` rather than a bare index.  Back's
        # position is (row, col, a, b): the beam's square *and* direction.
        # Two visits to one square travelling different ways are not the
        # same point in the program, and comparing them as if they were
        # would compare configurations that never replay each other.
        machine = _Machine([">"], ScriptedIO())
        assert isinstance(machine.ip, tuple)
        assert len(machine.ip) == 4
        assert run_until_halt_or_growth(machine) is False


class TestTheDetectorsTakeAVM:
    """Every detector accepts what ``make_vm`` returns, not just a ``_Machine``.

    The detectors were written against the interpreters' private
    ``_Machine`` classes, so every caller in the repo imported one and
    hand-built it -- the class, its ``ScriptedIO``, and for a random
    language the seeded generator -- rather than going through the public
    factory.  A ``VM`` already holds exactly that machine, so ``_unwrap``
    opens it and the private import stops being the only way in.

    Each case asserts the *same verdict* the hand-built machine gets in
    the class above, because the point is that the wrapper changes
    nothing about the answer.  Both directions are checked: a detector
    that always returned ``True`` would pass a halting-only test.
    """

    def test_the_branching_detector_takes_a_vm(self) -> None:
        """The adapter's seeded ``rng`` must not narrow the search.

        This is the case the unwrap could plausibly break: the derived
        adapter passes ``rng=Seeded(...)`` so a stepped VM is
        reproducible, and a search that followed that generator would
        explore one draw and call the other three unreachable.  It does
        not, because ``branching_successors`` forks the immutable state
        rather than the live machine -- so ``?.``, where only east and
        west reach the halt, is still found to halt.
        """
        from esolangs.vm import make_vm, run_until_halt_or_all_branches_cycle

        looping = make_vm("WII2D", ">?\n! ")
        assert run_until_halt_or_all_branches_cycle(looping) is False

        halting = make_vm("WII2D", "?.\n! ")
        assert run_until_halt_or_all_branches_cycle(halting) is True

    def test_the_ancestor_detector_takes_a_vm(self) -> None:
        """APL's truth machine, the shape the frame stack exists for."""
        from esolangs.vm import make_vm, run_until_halt_or_ancestor

        truth = "x? = x & x?\nn?"
        halts = make_vm("Algebraic Programming Language", truth, "0\n")
        assert run_until_halt_or_ancestor(halts) is True

        hangs = make_vm("Algebraic Programming Language", truth, "1\n")
        assert run_until_halt_or_ancestor(hangs) is False

    def test_the_growth_detector_takes_a_vm(self) -> None:
        """``+[>+]`` grows the tape a cell a lap and never repeats a state."""
        from esolangs.vm import make_vm, run_until_halt_or_growth

        # `+[>]` walks right off the set cell onto a zero and leaves.
        assert run_until_halt_or_growth(make_vm("brainfuck", "+[>]")) is True
        assert run_until_halt_or_growth(make_vm("brainfuck", "+[>+]")) is False

    def test_the_value_growth_detector_proves_a_climbing_cell(self) -> None:
        """Suffolk's ``>>!`` loops climb in value on a tape that never grows.

        Neither existing detector can see these.  The tape stays five cells
        wide and the pointer stays put, so nothing grows; a cell climbs by
        4501 a lap and the cells are unbounded ints, so nothing repeats.
        """
        from esolangs.vm import make_vm, run_until_halt_or_value_growth

        climbing = ">>!>>!>>!>>!>>!>>!>>!>>!>>>!>>!>>!>><!>>"
        assert run_until_halt_or_value_growth(make_vm("Suffolk", climbing)) is False
        assert (
            run_until_halt_or_value_growth(make_vm("Suffolk", "1{z:[}] !. ;")) is False
        )

    def test_the_value_growth_detector_declines_a_repeating_program(self) -> None:
        """A program that cycles is the cycle detector's, and is not certified.

        Suffolk's sample returns to a state it has been in, which
        :func:`run_until_halt_or_cycle` proves.  This detector must reach
        its limit rather than claim the run climbs forever -- an undecided
        answer where another detector has a proof, never a wrong one.
        """
        from esolangs.vm import (
            make_vm,
            run_until_halt_or_cycle,
            run_until_halt_or_value_growth,
        )

        sample = "!" * 66 + "<."
        assert run_until_halt_or_cycle(make_vm("Suffolk", sample)) is False
        with pytest.raises(TimeoutError):
            run_until_halt_or_value_growth(make_vm("Suffolk", sample), 20_000)

        # `<` alone rewinds to a cell it already read: a repeat, not a climb.
        assert run_until_halt_or_cycle(make_vm("Suffolk", "<")) is False
        with pytest.raises(TimeoutError):
            run_until_halt_or_value_growth(make_vm("Suffolk", "<"), 5_000)

    def test_a_drifting_clamp_is_not_a_certificate(self) -> None:
        """Two laps agreeing on a delta do not carry to the hundredth.

        ``!`` writes ``max(0, tape[ptr] + 1 - acc)``.  A slack that shrinks
        a little each lap agrees with itself for as long as anyone watches
        and then flips, after which the lap is a different affine map.  The
        clamp conditions are what refuse it, so a delta that repeats while
        a clamp drifts toward zero must not be certified.
        """
        from esolangs.vm import _clamps_hold

        # Unclamped and falling, and clamped and rising: both flip later.
        assert _clamps_hold([5], [3]) is False
        assert _clamps_hold([-5], [-3]) is False
        # Holding: away from the boundary, or already past it and sinking.
        assert _clamps_hold([3], [5]) is True
        assert _clamps_hold([-3], [-5]) is True
        # A clamp that already changed side between the two laps.
        assert _clamps_hold([1], [-1]) is False
        # Laps that clamped in different places are not comparable at all.
        assert _clamps_hold([None, 1], [1, None]) is False
        assert _clamps_hold([1], [1, 1]) is False

        # Zero is the boundary itself, and every comparison here is written
        # against it, so it is the one value that separates ``>= 0`` from
        # ``> 0`` -- a mutation sweep found four readings of these lines
        # that no case above could tell apart.
        assert _clamps_hold([0], [5]) is True
        assert _clamps_hold([0], [0]) is True
        # A slack that does not move at all holds: the conditions refuse
        # *drift* toward a flip, and standing still is not drift.
        assert _clamps_hold([3], [3]) is True
        assert _clamps_hold([-3], [-3]) is True
        # A pair that both clamped is skipped, not a verdict on the rest:
        # the laps after it still have to agree.
        assert _clamps_hold([None, 5], [None, 3]) is False
        assert _clamps_hold([None], [None]) is True

    @pytest.mark.parametrize(
        ("detector", "role"),
        [
            ("run_until_halt_or_all_branches_cycle", "branch-enumerable"),
            ("run_until_halt_or_ancestor", "framed"),
            ("run_until_halt_or_growth", "a tape machine"),
            ("run_until_halt_or_value_growth", "an affine machine"),
        ],
    )
    def test_a_detector_names_the_thing_the_language_is_not(
        self, detector: str, role: str
    ) -> None:
        """The refusal says which sub-protocol was missing, not just that one was.

        ``_unwrap``'s whole point is that the interesting failure is "this
        language has no such thing" rather than "wrong type": a machine
        without frames does not recurse, one without a tape has nothing to
        grow.  The role is the only part of the message carrying that, and
        nothing pinned it -- a sweep found every detector's wording free to
        change.  Sophie has none of the four.
        """
        import esolangs.vm as module

        # The class is named as well as the role: "wrong type" alone is the
        # message this function exists to improve on, so both halves are
        # pinned -- the sweep found each free to change on its own.
        with pytest.raises(TypeError, match=f"_SophieVM is not {re.escape(role)}:"):
            getattr(module, detector)(esolangs.make_vm("Sophie", ""))

    def test_the_value_growth_detector_refuses_a_bounded_language(self) -> None:
        """Brainfuck's cells wrap, so a climb there is a cycle, not a proof.

        The certificate needs values with no ceiling; a byte that keeps
        being incremented comes back around and is
        :func:`run_until_halt_or_cycle`'s to prove.  Brainfuck exposes no
        ``values``, so the question is refused rather than answered.
        """
        from esolangs.vm import make_vm, run_until_halt_or_value_growth

        with pytest.raises(TypeError, match="affine machine"):
            run_until_halt_or_value_growth(make_vm("brainfuck", "+[>+]"))

    def test_an_object_that_is_neither_raises_type_error(self) -> None:
        """The unwrap looks one level deep, and no further."""
        from esolangs.vm import run_until_halt_or_cycle

        with pytest.raises(TypeError, match="steppable with a snapshot"):
            run_until_halt_or_cycle(object())  # type: ignore[arg-type]


class TestRunUntilHalt:
    """The plain bounded drive the four consumers now share.

    Not a hang detector: it proves nothing and returns a verdict about one
    bounded run.  What is worth pinning is the part each caller silently
    depended on when it wrote the loop itself -- how many steps a budget
    buys, and that a ``stop`` fires *before* the step it stops.  A helper
    that ran one step too many, or checked the predicate after stepping,
    would leave every caller's tests green and change what a breakpoint
    means.
    """

    @staticmethod
    def _counter(halt_after: int) -> object:
        """A machine that halts after exactly ``halt_after`` steps."""

        class _Counter:
            def __init__(self) -> None:
                self.steps = 0

            @property
            def halted(self) -> bool:
                return self.steps >= halt_after

            def step(self) -> None:
                self.steps += 1

        return _Counter()

    def test_a_machine_that_halts_within_budget_reports_true(self) -> None:
        from esolangs.vm import run_until_halt

        machine = self._counter(3)
        assert run_until_halt(machine, 10) is True  # type: ignore[arg-type]
        assert machine.steps == 3  # type: ignore[attr-defined]

    def test_the_budget_buys_exactly_that_many_steps(self) -> None:
        """A limit of ``n`` executes ``n`` commands, not ``n - 1`` or ``n + 1``.

        ``Debugger.run(max_steps=10)`` is documented as stopping "once that
        many commands have executed", so a caller escalating a cap relies on
        a run at cap ``n`` having really covered ``n`` steps.
        """
        from esolangs.vm import run_until_halt

        machine = self._counter(100)
        assert run_until_halt(machine, 10) is False  # type: ignore[arg-type]
        assert machine.steps == 10  # type: ignore[attr-defined]

    def test_no_limit_runs_to_the_halt(self) -> None:
        """``None`` is unbounded, which is what a known-halting run wants."""
        from esolangs.vm import run_until_halt

        machine = self._counter(500)
        assert run_until_halt(machine) is True  # type: ignore[arg-type]
        assert machine.steps == 500  # type: ignore[attr-defined]

    def test_an_already_halted_machine_takes_no_step(self) -> None:
        from esolangs.vm import run_until_halt

        machine = self._counter(0)
        assert run_until_halt(machine, 10) is True  # type: ignore[arg-type]
        assert machine.steps == 0  # type: ignore[attr-defined]

    def test_stop_is_checked_before_the_step_it_stops(self) -> None:
        """The predicate fires with the state it watched still intact.

        This is the whole meaning of a breakpoint: ``break_on_cell`` must
        stop while the cell still holds the value, not after the step that
        moved past it.  A helper that stepped first and asked afterwards
        would report the state one command too late.
        """
        from esolangs.vm import run_until_halt

        machine = self._counter(100)
        assert (
            run_until_halt(
                machine,  # type: ignore[arg-type]
                50,
                stop=lambda: machine.steps == 4,  # type: ignore[attr-defined]
            )
            is False
        )
        assert machine.steps == 4  # type: ignore[attr-defined]

    def test_stop_true_at_the_start_takes_no_step(self) -> None:
        """A breakpoint on the initial position fires without executing it."""
        from esolangs.vm import run_until_halt

        machine = self._counter(100)
        assert (
            run_until_halt(machine, 50, stop=lambda: True)  # type: ignore[arg-type]
            is False
        )
        assert machine.steps == 0  # type: ignore[attr-defined]

    def test_a_halt_beats_a_stop_that_would_also_fire(self) -> None:
        """The halt check comes first, so a halted machine is never a stop.

        Returning ``False`` here would tell a caller its program did not
        finish when it did -- and the leak sweep would rerun it at every
        larger cap forever.
        """
        from esolangs.vm import run_until_halt

        machine = self._counter(0)
        assert (
            run_until_halt(machine, 10, stop=lambda: True)  # type: ignore[arg-type]
            is True
        )

    def test_it_drives_a_real_vm(self) -> None:
        """The callers pass a ``VM``, so the surface has to fit one."""
        from esolangs.vm import run_until_halt

        vm = esolangs.make_vm("brainfuck", "++++++++[>++++++++<-]>+.")
        assert run_until_halt(vm, 10_000) is True
        assert vm.output == "A"

    def test_a_budget_short_of_the_halt_reports_false(self) -> None:
        from esolangs.vm import run_until_halt

        vm = esolangs.make_vm("brainfuck", "++++++++[>++++++++<-]>+.")
        assert run_until_halt(vm, 5) is False
        assert vm.output == ""
