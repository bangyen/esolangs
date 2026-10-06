"""The five hang detectors."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.laserfuck import _Machine as Laserfuck
from esolangs.interpreters.grid_based.super_snusp import _Machine as SuperSnusp
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.forbin import _Machine as Forbin
from esolangs.interpreters.randomness import FirstDraw
from esolangs.interpreters.stack_based.forth import _Machine as Forth
from esolangs.interpreters.stack_based.grapheme import _Machine as Grapheme
from esolangs.interpreters.stack_based.modulous import _Machine as Modulous
from esolangs.interpreters.tape_based.back import _Machine as Back
from esolangs.interpreters.tape_based.brainfuck import _Machine as Brainfuck
from esolangs.interpreters.tape_based.dimensional import _Machine as Dimensional
from esolangs.interpreters.tape_based.factor import _Machine as Factor
from esolangs.interpreters.tape_based.factor import decode
from esolangs.interpreters.tape_based.jaune import _Machine as Jaune
from esolangs.interpreters.tape_based.painfuck import _Machine as Painfuck
from esolangs.interpreters.tape_based.sbleq import _Machine as Sbleq
from esolangs.interpreters.tape_based.six_five import _Machine as SixFive
from esolangs.interpreters.tape_based.slow_acv_mammalian import (
    _Machine as SlowAcvMammalian,
)
from esolangs.vm import (
    make_vm,
    run_until_halt,
    run_until_halt_or_all_branches_cycle,
    run_until_halt_or_ancestor,
    run_until_halt_or_cycle,
    run_until_halt_or_growth,
    run_until_halt_or_value_growth,
)


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


def _bf(code: str, stdin: str = "") -> Brainfuck:
    return Brainfuck(code, ScriptedIO(stdin))


class TestRunUntilHaltOrCycle:
    def test_painfuck_all_coin_outcomes_can_be_proved_to_loop(self) -> None:
        """Either ``y`` outcome reaches a loop close and returns to ``a``."""
        code = _painfuck_source("paybb")
        machine = Painfuck(code, ScriptedIO())
        assert run_until_halt_or_all_branches_cycle(machine) is False
        # A single path's snapshot counts its coin draws (a later draw could
        # escape), so it never repeats: undecided, not a false cycle.
        for coin in (0, 1):
            draws = FirstDraw(coin, rest=coin)
            with pytest.raises(TimeoutError, match="undecided after 64 steps"):
                run_until_halt_or_cycle(Painfuck(code, ScriptedIO(), draws), limit=64)

    def test_painfuck_one_halting_coin_refutes_an_all_branches_hang(self) -> None:
        code = _painfuck_source("payb")
        machine = Painfuck(code, ScriptedIO())
        assert run_until_halt_or_all_branches_cycle(machine) is True
        halting = Painfuck(code, ScriptedIO(), FirstDraw(1))
        assert run_until_halt_or_cycle(halting) is True
        looping = Painfuck(code, ScriptedIO(), FirstDraw(0, rest=0))
        with pytest.raises(TimeoutError, match="undecided after 64 steps"):
            run_until_halt_or_cycle(looping, limit=64)

    def test_painfuck_later_coin_can_escape_repeated_visible_state(self) -> None:
        """Pins the draw count in the snapshot: tape/cursor repeat, yet the
        fifth coin halts ``payb``, so a single path must not report a cycle."""

        class DelayedEscape:
            def __init__(self) -> None:
                self.draws = 0

            def randbelow(self, upper: int) -> int:
                assert upper == 2
                self.draws += 1
                return int(self.draws == 5)

        coins = DelayedEscape()
        machine = Painfuck(_painfuck_source("payb"), ScriptedIO(), coins)
        assert run_until_halt_or_cycle(machine, limit=64) is True
        assert coins.draws == 5

    def test_painfuck_a_malformed_loop_is_a_terminal_branch(self) -> None:
        """An unmatched ``b`` ends its branch instead of escaping the search."""
        machine = Painfuck(_painfuck_source("b"), ScriptedIO())
        start = machine.branching_snapshot()
        assert machine.branching_halted(start) is False

        (ended,) = machine.branching_successors(start, 100) or ()
        assert machine.branching_halted(ended) is True
        assert ended[3] == machine.n  # cursor parked past the program

    def test_laserfuck_all_initial_headings_can_be_proved_to_loop(self) -> None:
        """The four headings are searched, not the one the machine drew."""
        code = [" v ", "}o{", " ^ "]
        machine = Laserfuck(code, ScriptedIO())
        assert run_until_halt_or_all_branches_cycle(machine) is False
        for heading in range(4):
            draws = FirstDraw(heading, rest=heading)
            machine = Laserfuck(code, ScriptedIO(), draws)
            assert run_until_halt_or_cycle(machine) is False

    def test_laserfuck_one_halting_heading_refutes_an_all_branches_hang(self) -> None:
        """Up and down leave the grid; left and right bounce forever."""
        code = ["}o{"]
        machine = Laserfuck(code, ScriptedIO())
        assert run_until_halt_or_all_branches_cycle(machine) is True
        up = Laserfuck(code, ScriptedIO(), FirstDraw(0))
        assert run_until_halt_or_cycle(up) is True
        left = Laserfuck(code, ScriptedIO(), FirstDraw(2, rest=2))
        assert run_until_halt_or_cycle(left) is False

    def test_laserfuck_grid_without_a_start_marker_places_no_beam(self) -> None:
        """A laserless grid reports empty beams, never the unplaced sentinel."""
        machine = Laserfuck(["+-", "<>"], ScriptedIO())
        assert machine.halted is True
        assert machine.branching_snapshot()[2] == ()
        assert machine.branching_halted(machine.branching_snapshot()) is True
        assert run_until_halt_or_all_branches_cycle(machine) is True

    def test_laserfuck_search_skips_the_command_after_a_hash(self) -> None:
        """``#`` skips in the search exactly as it does in a step."""
        machine = Laserfuck(["o#{"], ScriptedIO())
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
        machine = Laserfuck(["o"], ScriptedIO())
        assert machine.branching_snapshot()[2] is None
        assert machine.branching_halted(machine.branching_snapshot()) is False

    def test_laserfuck_explores_both_beam_splitter_outcomes(self) -> None:
        """``*``'s coin is searched, not sampled."""
        code = ["/{v", "^o^", "*/*"]
        for heading in range(4):
            draws = FirstDraw(heading, rest=0)
            machine = Laserfuck(code, ScriptedIO(), draws)
            assert run_until_halt_or_cycle(machine) is False
        escaping = Laserfuck(code, ScriptedIO(), FirstDraw(1, rest=1))
        assert run_until_halt_or_cycle(escaping) is True
        machine = Laserfuck(code, ScriptedIO())
        assert run_until_halt_or_all_branches_cycle(machine, limit=5000) is True

    def test_laserfuck_a_second_start_marker_halts_every_branch(self) -> None:
        """Two ``o``s stop the machine before it can draw a heading."""
        machine = Laserfuck(["oo"], ScriptedIO())
        assert machine.halted is True
        # the search's start state is halted too, not an unplaced beam
        assert machine.branching_halted(machine.branching_snapshot()) is True
        assert run_until_halt_or_all_branches_cycle(machine) is True

    def test_laserfuck_declines_a_reachable_input_command(self) -> None:
        """``,`` cannot be forked, so the search reports undecided."""
        machine = Laserfuck(["o,"], ScriptedIO("A\n"))
        with pytest.raises(TimeoutError, match="needs input"):
            run_until_halt_or_all_branches_cycle(machine)

    def test_super_snusp_mirror_ring_loops_under_every_draw(self) -> None:
        """A mirror ring circulates forever, and no draw escapes it."""
        code = ['/"\\', "\\ /"]
        machine = SuperSnusp(code, ScriptedIO())
        assert run_until_halt_or_all_branches_cycle(machine, limit=3000) is False
        assert run_until_halt_or_cycle(SuperSnusp(code, ScriptedIO())) is False

    def test_super_snusp_forks_every_value_equals_could_store(self) -> None:
        """``=`` picks from the span between the cell and the stack top."""
        machine = SuperSnusp(['"3{(='], ScriptedIO())
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
        for code, stdin in (('",', "A\n"), ('"@', "1\n")):
            machine = SuperSnusp([code], ScriptedIO(stdin))
            with pytest.raises(TimeoutError, match="needs input"):
                run_until_halt_or_all_branches_cycle(machine)

        # '999{' pushes 999 and '>' moves to a fresh zero cell, so '=' spans
        # 1000 values -- past the per-transition cap whatever the budget.
        wide = SuperSnusp(['"999{>='], ScriptedIO())
        with pytest.raises(TimeoutError, match=r"exceeds the .* cap"):
            run_until_halt_or_all_branches_cycle(wide, limit=100000)

    def test_modulous_reset_loops_and_end_halts(self) -> None:
        """``RST`` rewinds the cursor forever; ``END`` stops."""
        reset = Modulous("[RST]", ScriptedIO())
        assert run_until_halt_or_all_branches_cycle(reset) is False
        assert run_until_halt_or_cycle(Modulous("[RST]", ScriptedIO())) is False
        end = Modulous("[END]", ScriptedIO())
        assert run_until_halt_or_all_branches_cycle(end) is True

    def test_modulous_forks_every_value_rnd_could_draw(self) -> None:
        """``RND n`` opens exactly ``n`` outcomes, one per drawable value."""
        machine = Modulous("[RND 4]", ScriptedIO())
        successors = machine.branching_successors(machine.branching_snapshot(), 100)
        assert successors is not None
        assert sorted(state[0][0][-1] for state in successors) == [0, 1, 2, 3]

        # A bound below one is rejected by the handler, so the search raises
        # exactly where a step would.
        quiet = Modulous("[RND 0]", ScriptedIO())
        with pytest.raises(HaltError):
            quiet.branching_successors(quiet.branching_snapshot(), 100)

    def test_modulous_non_command_tokens_advance_one_branch(self) -> None:
        """A token no handler claims still steps, and forks nothing."""
        machine = Modulous("[]", ScriptedIO())
        successors = machine.branching_successors(machine.branching_snapshot(), 100)
        assert successors is not None
        assert len(successors) == 1

        # Arithmetic changes the named variable without forking.
        for token, expected in (("[VAR1+1]", 1), ("[VAR1-1]", -1)):
            arith = Modulous(token, ScriptedIO())
            (stepped,) = (
                arith.branching_successors(arith.branching_snapshot(), 100) or ()
            )
            assert dict(stepped[0][1])["VAR1"] == expected, token

        word = Modulous("[FOO]", ScriptedIO())
        with pytest.raises(ValueError, match="not a Modulous command"):
            word.branching_successors(word.branching_snapshot(), 100)

    def test_modulous_declines_input_and_caps_a_wide_draw(self) -> None:
        """``INP`` cannot be forked, and one ``RND`` cannot be unbounded."""
        with pytest.raises(TimeoutError, match="needs input"):
            run_until_halt_or_all_branches_cycle(Modulous("[INP]", ScriptedIO("A\n")))
        wide = Modulous("[RND 100000]", ScriptedIO())
        with pytest.raises(TimeoutError, match=r"exceeds the .* cap"):
            run_until_halt_or_all_branches_cycle(wide, limit=100000)

    def test_branching_search_leaves_unbounded_or_input_paths_undecided(self) -> None:
        with pytest.raises(TimeoutError, match="reachable graph may be unbounded"):
            run_until_halt_or_all_branches_cycle(
                Laserfuck(["o*"], ScriptedIO()), limit=1
            )
        # The direct target 'j' reads; sibling paths must not share a cursor.
        with pytest.raises(TimeoutError, match="needs input"):
            run_until_halt_or_all_branches_cycle(
                Painfuck(_painfuck_source("j"), ScriptedIO("A\n"))
            )
        # c repeats y 49 times: the frontier is limited at the transition,
        # before its 2**49 outcomes are materialized.
        with pytest.raises(TimeoutError, match="coin outcomes"):
            run_until_halt_or_all_branches_cycle(
                Painfuck(_painfuck_source("ccy"), ScriptedIO()), limit=4
            )

    def test_sbleq_looping_run_is_detected_as_a_cycle(self) -> None:
        # a=0 b=0 c=2: diff is always 0, so it jumps to mem[2] (address 0) forever
        machine = Sbleq("0 0 0", ScriptedIO(), store="a")
        assert run_until_halt_or_cycle(machine) is False

    def test_dimensional_looping_run_is_detected_as_a_cycle(self) -> None:
        # cell starts nonzero and the loop body never changes it
        machine = Dimensional("+[]", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is False

    def test_slow_acv_mammalian_looping_run_is_detected_as_a_cycle(self) -> None:
        # LEAPFROG jumps back to a point that reproduces the exact same state
        code = "CONFLAGRATE SEED SEED DIGEST FISSION LEAPFROG"
        machine = SlowAcvMammalian(code, ScriptedIO())
        assert run_until_halt_or_cycle(machine) is False

    def test_a_machine_already_halted_is_reported_as_halting(self) -> None:
        """The loop is never entered, and the answer is still ``True``."""
        vm = make_vm("brainfuck", "++")
        run_until_halt(vm)
        assert vm.halted
        assert run_until_halt_or_cycle(vm) is True

    def test_forbin_for_loop_halts_without_a_false_cycle(self) -> None:
        # Every row sets the same local to the same value, so only the loop's
        # own row index (in the snapshot) keeps this from reading as a repeat.
        machine = Forbin("main { for i:0..1 { x = 0; } }", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is True

    def test_forth_replayed_scope_is_detected_as_an_ancestor(self) -> None:
        # Store 1; under key 1, then have that scope call itself forever.
        machine = Forth("1{1;}1;", ScriptedIO())
        assert run_until_halt_or_ancestor(machine) is False

    def test_forth_changing_stack_halts(self) -> None:
        # The scope decrements its shared counter before conditionally
        # calling itself, so every entered scope has a different binding.
        machine = Forth("1{1-(1;)}3v;", ScriptedIO())
        assert run_until_halt_or_ancestor(machine) is True

    def test_jaune_replayed_subroutine_is_detected_as_an_ancestor(self) -> None:
        # Main calls subroutine 1, whose body immediately calls itself.
        machine = Jaune("1@.1$1@;", ScriptedIO())
        assert run_until_halt_or_ancestor(machine) is False

    def test_jaune_changing_tape_halts(self) -> None:
        # Subroutine 1 decrements the tape then recurs until the zero case
        # jumps to its return, so the tape belongs in the entry key.
        machine = Jaune("3+1@.1$1-2!1@;2:;", ScriptedIO())
        assert run_until_halt_or_ancestor(machine) is True

    def test_grapheme_replayed_function_is_detected_as_an_ancestor(self) -> None:
        # The function invokes itself without changing the shared state.
        machine = Grapheme("HKGHKG", ScriptedIO())
        assert run_until_halt_or_ancestor(machine) is False

    def test_grapheme_changing_stack_halts(self) -> None:
        # The function decrements the count before Q recurs, so each entry
        # has a different shared stack and reaches the zero base case.
        code = "FAF" + "H" + "FFTPBKFAFDQ" + "H" + "FAFC" + "FAFD" + "G"
        assert run_until_halt_or_ancestor(Grapheme(code, ScriptedIO())) is True


class TestRunUntilHaltOrGrowth:
    """The unbounded-growth certificate on brainfuck's tape."""

    def test_cycle_detector_cannot_prove_the_growing_loop(self) -> None:
        # The gap this detector closes: 5000 steps of `+[>+]` reach no
        # repeated snapshot, so Brent's has nothing to find.
        machine = _bf("+[>+]")
        seen = {machine.snapshot()}
        for _ in range(5000):
            machine.step()
            assert machine.snapshot() not in seen
            seen.add(machine.snapshot())
        assert len(seen) == 5001

    def test_certificate_holds_only_above_the_periods_lowest_cell(self) -> None:
        # Cell 0 keeps the 1 that `+` left while later cells fill with 2, so
        # the tape is never a full-width shift; only comparing from the
        # period's own minimum pointer proves this one.
        assert run_until_halt_or_growth(_bf("+[>++]")) is False

    def test_certificate_fires_early_rather_than_at_the_limit(self) -> None:
        # The verdict comes from the certificate, not an exhausted budget: a
        # mutant that defeats it raises TimeoutError at this small limit.
        assert run_until_halt_or_growth(_bf("+[>+]"), 12) is False

    def test_a_reading_loop_is_never_certified(self) -> None:
        # Every lap of `+[>,]` reads the same byte, so the tape is a clean
        # right-shift and the other three conditions hold; only the moving
        # input cursor stops a hang verdict for a program that stops.
        with pytest.raises(EOFError):
            run_until_halt_or_growth(_bf("+[>,]", "a\n" * 6), 200)
        # With input still to come at the limit, it is undecided.
        with pytest.raises(TimeoutError, match="undecided after"):
            run_until_halt_or_growth(_bf("+[>,]", "a\n" * 400), 200)

    def test_a_left_edge_loop_is_never_certified(self) -> None:
        # `+[<+]` is why the certificate demands `m >= 1`: its `<` grows the
        # tape leftward each lap, shifting every index, so laps do not
        # translate rightward.
        machine = _bf("+[<+]")
        with pytest.raises(TimeoutError, match="undecided after"):
            run_until_halt_or_growth(machine, 300)
        assert machine.ptr == 0
        assert len(machine.tape) > 50

    def test_in_place_cycles_are_left_to_the_cycle_detector(self) -> None:
        # `+[]` has zero displacement, so this detector declines; the state
        # repeats exactly, which is the cycle detector's to prove.
        with pytest.raises(TimeoutError, match="undecided after"):
            run_until_halt_or_growth(_bf("+[]"), 300)
        assert run_until_halt_or_cycle(_bf("+[]")) is False

    def test_a_growing_run_that_still_halts_is_not_called_a_hang(self) -> None:
        # Nine laps of growth, then cell 0's counter runs out: the period is
        # not a translation because cell 0 falls.
        machine = _bf("+++++++++[>+<-]")
        assert run_until_halt_or_growth(machine) is True
        assert machine.tape[1] == 9

    def test_phased_growing_waves_select_their_own_period(self) -> None:
        # Each outer lap moves right and maps 1 to 2 or 2 to 1, so one lap
        # is not a translated state but two are.
        code = "+[>+++<[->-<]>]"
        assert run_until_halt_or_growth(_bf(code), 1_000) is False

        # Executed positive control: the program is live and growing.
        machine = _bf(code)
        for _ in range(500):
            machine.step()
        assert not machine.halted
        assert len(machine.tape) > 30

    def test_long_phased_wave_is_proved_without_a_period_argument(self) -> None:
        # Copy right and add two: a 128-phase travelling wave Brent finds.
        assert run_until_halt_or_growth(_bf("+[[->+<]>++]")) is False

    def test_a_period_that_walks_to_cell_zero_is_undecided(self) -> None:
        # `>+[[<]>[>]+]` grows a run of ones forever, but every lap walks to
        # cell 0, so its visits share a frozen prefix rather than
        # translating; 5,000 steps is ~70 laps.
        with pytest.raises(TimeoutError, match="undecided after"):
            run_until_halt_or_growth(_bf(">+[[<]>[>]+]"), 5_000)

        machine = _bf(">+[[<]>[>]+]")
        for _ in range(5_000):
            machine.step()
        assert not machine.halted
        assert len(machine.tape) == 50

        # Without the append the walk leaves at the first zero.
        assert run_until_halt_or_growth(_bf(">+[[<]>[>]]")) is True

    def test_a_climbing_wave_that_wraps_to_a_halt_is_never_certified(self) -> None:
        # `+[[->+<]>+]` climbs as it travels until the value wraps at 256
        # and the run halts, 164,222 steps in (measured).  Within a smaller
        # budget the only sound answer is undecided.
        with pytest.raises(TimeoutError, match="undecided after"):
            run_until_halt_or_growth(_bf("+[[->+<]>+]"), 2_000)


class TestGrowthDetectorAcrossLanguages:
    """The certificate is not brainfuck-specific."""

    def test_six_five(self) -> None:
        # `4` marks, `1` moves right by two, `81` jumps back to the marker.
        assert run_until_halt_or_growth(SixFive("4181", ScriptedIO())) is False

        machine = SixFive("4181", ScriptedIO())
        for _ in range(600):
            assert not machine.halted
            machine.step()
        assert len(machine.tape) > 250

        # `5` leaves 5s behind with zeros between: the `i >= m` bound again.
        machine = SixFive("45181", ScriptedIO())
        assert run_until_halt_or_growth(machine) is False
        # No jump, so the cursor runs off the end.
        assert run_until_halt_or_growth(SixFive("41", ScriptedIO())) is True

    def test_factor(self) -> None:
        # 3*7*23*47*107: residues mod 11 spell `+[>+]` in prime order.
        assert decode(2429007) == "+[>+]"
        machine = Factor("2429007", ScriptedIO())
        assert run_until_halt_or_growth(machine) is False

        machine = Factor("2429007", ScriptedIO())
        for _ in range(600):
            assert not machine.halted
            machine.step()
        assert len(machine.tape) > 150

        assert decode(19803) == "+[>]"
        assert run_until_halt_or_growth(Factor("19803", ScriptedIO())) is True

    def test_the_heading_is_part_of_the_code_position(self) -> None:
        # Back's position is (row, col, a, b): two visits to one square
        # travelling different ways are not the same point in the program.
        machine = Back([">"], ScriptedIO())
        assert isinstance(machine.ip, tuple)
        assert len(machine.ip) == 4
        assert run_until_halt_or_growth(machine) is False


class TestTheDetectorsTakeAVM:
    """Every detector accepts what ``make_vm`` returns, not just a ``_Machine``."""

    def test_the_branching_detector_takes_a_vm(self) -> None:
        """The adapter's seeded ``rng`` must not narrow the search."""
        looping = make_vm("LaserFuck", " v \n}o{\n ^ ")
        assert run_until_halt_or_all_branches_cycle(looping) is False
        assert run_until_halt_or_all_branches_cycle(make_vm("LaserFuck", "}o{")) is True

    def test_the_ancestor_detector_takes_a_vm(self) -> None:
        """APL's truth machine, the shape the frame stack exists for."""
        truth = "x? = x & x?\nn?"
        halts = make_vm("Algebraic Programming Language", truth, "0\n")
        assert run_until_halt_or_ancestor(halts) is True
        hangs = make_vm("Algebraic Programming Language", truth, "1\n")
        assert run_until_halt_or_ancestor(hangs) is False

    def test_the_growth_detector_takes_a_vm(self) -> None:
        """``+[>]`` walks off onto a zero; ``+[>+]`` grows a cell a lap."""
        assert run_until_halt_or_growth(make_vm("brainfuck", "+[>]")) is True
        assert run_until_halt_or_growth(make_vm("brainfuck", "+[>+]")) is False

    def test_the_value_growth_detector_proves_a_climbing_cell(self) -> None:
        """Suffolk's ``>>!`` loops climb in value on a tape that never grows."""
        climbing = ">>!>>!>>!>>!>>!>>!>>!>>!>>>!>>!>>!>><!>>"
        assert run_until_halt_or_value_growth(make_vm("Suffolk", climbing)) is False
        lapping = make_vm("Suffolk", "1{z:[}] !. ;")
        assert run_until_halt_or_value_growth(lapping) is False

    def test_the_value_growth_detector_declines_a_repeating_program(self) -> None:
        """A program that cycles is the cycle detector's, and is not certified."""
        sample = "!" * 66 + "<."
        assert run_until_halt_or_cycle(make_vm("Suffolk", sample)) is False
        with pytest.raises(TimeoutError):
            run_until_halt_or_value_growth(make_vm("Suffolk", sample), 20_000)

        # `<` alone rewinds to a cell it already read: a repeat, not a climb.
        with pytest.raises(TimeoutError):
            run_until_halt_or_value_growth(make_vm("Suffolk", "<"), 5_000)

    def test_the_value_growth_detector_refuses_a_bounded_language(self) -> None:
        """Brainfuck's cells wrap, so a climb there is a cycle, not a proof."""
        with pytest.raises(TypeError, match="affine machine"):
            run_until_halt_or_value_growth(make_vm("brainfuck", "+[>+]"))

    def test_an_object_that_is_neither_raises_type_error(self) -> None:
        """The unwrap looks one level deep, and no further."""
        with pytest.raises(TypeError, match="steppable with a snapshot"):
            run_until_halt_or_cycle(object())  # type: ignore[arg-type]

    def test_a_negative_branch_cap_stops_rather_than_exploring_free(self) -> None:
        """A cap below zero is still a cap."""

        class _Unbounded:
            def branching_snapshot(self) -> int:
                return 0

            def branching_halted(self, _state: int) -> bool:
                return False

            def branching_successors(self, state: int, _limit: int) -> list[int]:
                return [state + 1]

        for limit in (0, -1):
            with pytest.raises(TimeoutError, match="branching states"):
                run_until_halt_or_all_branches_cycle(
                    _Unbounded(),  # type: ignore[arg-type]
                    limit=limit,
                )


@pytest.mark.parametrize(("program", "limit"), [("", 0), ("+", 1)])
def test_growth_detector_accepts_halt_at_step_limit(program: str, limit: int) -> None:
    assert run_until_halt_or_growth(make_vm("Brainfuck", program), limit) is True


@pytest.mark.parametrize("limit", [0, 1])
def test_value_growth_detector_accepts_eof_halt_at_step_limit(limit: int) -> None:
    machine = make_vm("Suffolk", ",")
    if limit == 0:
        machine.step()
    assert run_until_halt_or_value_growth(machine, limit) is True
