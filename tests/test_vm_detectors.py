"""The five hang detectors."""

import pytest

import esolangs.debugger as debugger_api


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
    _cursor, (pointer, cells), *_rest = state  # type: ignore[misc]
    return next((value for index, value in cells if index == pointer), 0)


class TestRunUntilHaltOrCycle:
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
        # A single path's snapshot counts its coin draws (a later draw could
        # escape), so it never repeats: undecided, not a false cycle.
        for coin in (0, 1):
            with pytest.raises(TimeoutError, match="undecided after 64 steps"):
                run_until_halt_or_cycle(
                    _Machine(code, ScriptedIO(), FirstDraw(coin, rest=coin)), limit=64
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
        with pytest.raises(TimeoutError, match="undecided after 64 steps"):
            run_until_halt_or_cycle(
                _Machine(code, ScriptedIO(), FirstDraw(0, rest=0)), limit=64
            )

    def test_painfuck_later_coin_can_escape_repeated_visible_state(self) -> None:
        """Pins the draw count in the snapshot: tape/cursor repeat, yet the
        fifth coin halts ``payb``, so a single path must not report a cycle."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.painfuck import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        class DelayedEscape:
            def __init__(self) -> None:
                self.draws = 0

            def randbelow(self, upper: int) -> int:
                assert upper == 2
                self.draws += 1
                return int(self.draws == 5)

        coins = DelayedEscape()
        machine = _Machine(_painfuck_source("payb"), ScriptedIO(), coins)
        assert run_until_halt_or_cycle(machine, limit=64) is True
        assert coins.draws == 5

    def test_painfuck_a_malformed_loop_is_a_terminal_branch(self) -> None:
        """An unmatched ``b`` ends its branch instead of escaping the search."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.painfuck import _Machine

        machine = _Machine(_painfuck_source("b"), ScriptedIO())
        start = machine.branching_snapshot()
        assert machine.branching_halted(start) is False

        (ended,) = machine.branching_successors(start, 100) or ()
        assert machine.branching_halted(ended) is True
        assert ended[3] == machine.n  # cursor parked past the program

    def test_laserfuck_all_initial_headings_can_be_proved_to_loop(self) -> None:
        """The four headings are searched, not the one the machine drew."""
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
        """A laserless grid reports empty beams, never the unplaced sentinel."""
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import run_until_halt_or_all_branches_cycle

        machine = _Machine(["+-", "<>"], ScriptedIO())
        assert machine.halted is True
        assert machine.branching_snapshot()[2] == ()
        assert machine.branching_halted(machine.branching_snapshot()) is True
        assert run_until_halt_or_all_branches_cycle(machine) is True

    def test_laserfuck_search_skips_the_command_after_a_hash(self) -> None:
        """``#`` skips in the search exactly as it does in a step."""
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
        assert at_hash[4] == frozenset({0}), "'#' arms beam 0's skip"

        (skipped,) = machine.branching_successors(at_hash, 100) or ()
        assert skipped[2] == ((0, 2, 3),), "'{' was passed over, not executed"
        assert skipped[4] == frozenset(), "the skip disarms itself"

    def test_laserfuck_a_placed_beam_starts_the_search_unplaced(self) -> None:
        """The complement: a grid *with* an ``o`` does use the sentinel."""
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO

        machine = _Machine(["o"], ScriptedIO())
        assert machine.branching_snapshot()[2] is None
        assert machine.branching_halted(machine.branching_snapshot()) is False

    def test_laserfuck_explores_both_beam_splitter_outcomes(self) -> None:
        """``*``'s coin is searched, not sampled."""
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
        # the search's start state is halted too, not an unplaced beam
        assert machine.branching_halted(machine.branching_snapshot()) is True
        assert run_until_halt_or_all_branches_cycle(machine) is True

    def test_laserfuck_declines_a_reachable_input_command(self) -> None:
        """``,`` cannot be forked, so the search reports undecided."""
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import run_until_halt_or_all_branches_cycle

        with pytest.raises(TimeoutError, match="needs input"):
            run_until_halt_or_all_branches_cycle(_Machine(["o,"], ScriptedIO("A\n")))

    def test_super_snusp_mirror_ring_loops_under_every_draw(self) -> None:
        """A mirror ring circulates forever, and no draw escapes it."""
        from esolangs.interpreters.grid_based.super_snusp import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import (
            run_until_halt_or_all_branches_cycle,
            run_until_halt_or_cycle,
        )

        code = ['/"\\', "\\ /"]
        assert (
            run_until_halt_or_all_branches_cycle(
                _Machine(code, ScriptedIO()), limit=3000
            )
            is False
        )
        assert run_until_halt_or_cycle(_Machine(code, ScriptedIO())) is False

    def test_super_snusp_forks_every_value_equals_could_store(self) -> None:
        """``=`` picks from the span between the cell and the stack top."""
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
        """A token no handler claims still steps, and forks nothing."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.modulous import _Machine

        for code in ("[]", "[VAR1+1]", "[VAR1-1]"):
            machine = _Machine(code, ScriptedIO())
            successors = machine.branching_successors(machine.branching_snapshot(), 100)
            assert successors is not None, code
            assert len(successors) == 1, code

        # Arithmetic changes the named variable without forking.
        for token, expected in (("[VAR1+1]", 1), ("[VAR1-1]", -1)):
            arith = _Machine(token, ScriptedIO())
            (stepped,) = (
                arith.branching_successors(arith.branching_snapshot(), 100) or ()
            )
            assert dict(stepped[0][1])["VAR1"] == expected, token

        word = _Machine("[FOO]", ScriptedIO())
        start = word.branching_snapshot()
        with pytest.raises(ValueError, match="not a Modulous command"):
            word.branching_successors(start, 100)

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

    def test_branching_search_leaves_unbounded_or_input_paths_undecided(self) -> None:
        from esolangs.interpreters.grid_based.laserfuck import (
            _Machine as LaserfuckMachine,
        )
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.painfuck import (
            _Machine as PainfuckMachine,
        )
        from esolangs.vm import run_until_halt_or_all_branches_cycle

        with pytest.raises(TimeoutError, match="reachable graph may be unbounded"):
            run_until_halt_or_all_branches_cycle(
                LaserfuckMachine(["o*"], ScriptedIO()), limit=1
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

    def test_sbleq_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # a=0 b=0 c=2: diff is always 0, so it jumps to mem[2] (address 0) forever
        machine = _Machine("0 0 0", ScriptedIO(), store="a")
        assert run_until_halt_or_cycle(machine) is False

    def test_dimensional_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.dimensional import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # cell starts nonzero and the loop body never changes it, so it never exits
        machine = _Machine("+[]", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is False

    def test_modulous_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.modulous import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # RST resets the pointer to the start of the program on every pass
        machine = _Machine("[RST]", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is False

    def test_laserfuck_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.randomness import FirstDraw
        from esolangs.vm import run_until_halt_or_cycle

        # a closed ring of mirrors the laser circles forever
        grid = ["/ \\", "\\o/", "//\\"]
        machine = _Machine(grid, ScriptedIO(), rng=FirstDraw(2))
        assert run_until_halt_or_cycle(machine) is False

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
        """The loop is never entered, and the answer is still ``True``."""
        from esolangs.vm import run_until_halt, run_until_halt_or_cycle

        vm = debugger_api.make_vm("brainfuck", "++")
        run_until_halt(vm)
        assert vm.halted
        assert run_until_halt_or_cycle(vm) is True

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
        program = "H" + "FFTPBKFAFDQ" + "H" + "FAFC" + "FAFD" + "G"
        code = "FAF" + program
        assert run_until_halt_or_ancestor(_Machine(code, ScriptedIO())) is True


class TestRunUntilHaltOrGrowth:
    """The unbounded-growth certificate on brainfuck's tape."""

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
    """The certificate is not brainfuck-specific."""

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
    """Every detector accepts what ``make_vm`` returns, not just a ``_Machine``."""

    def test_the_branching_detector_takes_a_vm(self) -> None:
        """The adapter's seeded ``rng`` must not narrow the search."""
        from esolangs.vm import make_vm, run_until_halt_or_all_branches_cycle

        looping = make_vm("LaserFuck", " v \n}o{\n ^ ")
        assert run_until_halt_or_all_branches_cycle(looping) is False

        halting = make_vm("LaserFuck", "}o{")
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
        """Suffolk's ``>>!`` loops climb in value on a tape that never grows."""
        from esolangs.vm import make_vm, run_until_halt_or_value_growth

        climbing = ">>!>>!>>!>>!>>!>>!>>!>>!>>>!>>!>>!>><!>>"
        assert run_until_halt_or_value_growth(make_vm("Suffolk", climbing)) is False
        assert (
            run_until_halt_or_value_growth(make_vm("Suffolk", "1{z:[}] !. ;")) is False
        )

    def test_the_value_growth_detector_declines_a_repeating_program(self) -> None:
        """A program that cycles is the cycle detector's, and is not certified."""
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

    def test_the_value_growth_detector_refuses_a_bounded_language(self) -> None:
        """Brainfuck's cells wrap, so a climb there is a cycle, not a proof."""
        from esolangs.vm import make_vm, run_until_halt_or_value_growth

        with pytest.raises(TypeError, match="affine machine"):
            run_until_halt_or_value_growth(make_vm("brainfuck", "+[>+]"))

    def test_an_object_that_is_neither_raises_type_error(self) -> None:
        """The unwrap looks one level deep, and no further."""
        from esolangs.vm import run_until_halt_or_cycle

        with pytest.raises(TypeError, match="steppable with a snapshot"):
            run_until_halt_or_cycle(object())  # type: ignore[arg-type]

    def test_a_negative_branch_cap_stops_rather_than_exploring_free(self) -> None:
        """A cap below zero is still a cap."""
        from esolangs.vm import run_until_halt_or_all_branches_cycle

        class _Unbounded:
            def branching_snapshot(self) -> int:
                return 0

            def branching_halted(self, _state: int) -> bool:
                return False

            def branching_successors(self, state: int, _limit: int) -> list[int]:
                return [state + 1]

        for limit in (0, -1, -1000):
            with pytest.raises(TimeoutError, match="branching states"):
                run_until_halt_or_all_branches_cycle(
                    _Unbounded(),  # type: ignore[arg-type]
                    limit=limit,
                )


@pytest.mark.parametrize(("program", "limit"), [("", 0), ("+", 1), ("++", 2)])
def test_growth_detector_accepts_halt_at_step_limit(program: str, limit: int) -> None:
    from esolangs.vm import make_vm, run_until_halt_or_growth

    assert run_until_halt_or_growth(make_vm("Brainfuck", program), limit) is True


@pytest.mark.parametrize("limit", [0, 1, 2])
def test_value_growth_detector_accepts_eof_halt_at_step_limit(limit: int) -> None:
    from esolangs.vm import make_vm, run_until_halt_or_value_growth

    machine = make_vm("Suffolk", ",")
    if limit == 0:
        machine.step()
    assert run_until_halt_or_value_growth(machine, limit) is True
