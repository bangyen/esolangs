"""LaserFuck through the shared API, CLI and machinery."""

import inspect
from pathlib import Path

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs._execution import interpreter_module
from esolangs.cli import HELP
from esolangs.vm import make_vm, run_until_halt_or_all_branches_cycle
from tests.cli.test_cli import call_main
from tests.support.cli_support import call_both
from tests.support.generator_support import evaluate_generated, overruns
from tests.vm.test_vm import _run_all, assert_random_steps_reproduce
from tests.vm.test_vm_protocol import assert_starts_downward


def test_bound_execution_passes_the_seed():
    language = esolangs.Language("LaserFuck")
    assert [language.run("o+++.\n", seed=0) for _ in range(6)] == ["3"] * 6


@pytest.mark.medium
def test_isolation_preserves_integer_seeds_beyond_the_decimal_rendering_limit():
    seeds = [*range(8), 10**5000, -(10**5000)]  # strings are refused now
    direct = [
        esolangs.run("LaserFuck", "o+++.\n", seed=seed, timeout=5) for seed in seeds
    ]
    isolated = [
        esolangs.run("LaserFuck", "o+++.\n", seed=seed, timeout=5, isolated=True)
        for seed in seeds
    ]
    assert set(direct) == {"", "3"}
    assert isolated == direct


class TestLaserFuck:
    def test_ip_is_position_and_heading(self) -> None:
        # the adapter's generator is seeded so its first draw is 0 (up), so
        # the laser at (2,4) moves up
        vm = debugger_api.make_vm("LaserFuck", "\u00ff   x\n    +\n    o")
        assert vm.ip == (2, 4, 0)  # the laser's start position and heading
        vm.step()
        assert vm.ip == (1, 4, 0)  # moved up onto the '+'
        assert vm.memory == [1]
        vm.step()
        assert vm.ip == (0, 4, 0)  # moved up onto the 'x', died
        assert vm.halted
        assert vm.output == ""  # the tape is not dumped until the next step
        assert vm.stack == []
        vm.step()  # the post-halt step dumps it, as run's own last step does
        assert vm.output == "\x01"
        vm.step()  # and the dump happens once, not once per step past the halt
        assert vm.output == "\x01"

    def test_dump_output_matches_interpreter(self) -> None:
        from esolangs.interpreters.grid_based.laserfuck import _Machine as _LFMachine
        from esolangs.interpreters.grid_based.laserfuck import run as lf_run
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.randomness import Seeded

        program = "\u00ff   x\n    +\n    o"
        io_obj = ScriptedIO()
        # The VM builds its machine with ``Seeded(reproducible_seed)``, so
        # handing ``run`` the same source is what makes the two sides
        # comparable -- the heading is drawn, not passed, on both.
        lf_run(program.splitlines(), io_obj, rng=Seeded(_LFMachine.reproducible_seed))
        vm = debugger_api.make_vm("LaserFuck", program)
        _run_all(vm)
        vm.step()  # the dump, which run performs as its own last step
        assert vm.output == io_obj.getvalue()


class TestASeedMakesARunRepeat:
    """LaserFuck's docstring named a remedy no public function offered."""

    PROGRAM = "o+++.\n"

    def test_a_seeded_run_repeats(self) -> None:
        """Six runs, one answer."""
        answers = {
            esolangs.run("LaserFuck", self.PROGRAM, stdin="", timeout=5, seed=0)
            for _ in range(6)
        }
        assert len(answers) == 1

    def test_the_seed_selects_rather_than_fixes_one_outcome(self) -> None:
        """A seed that always gave the same answer would prove nothing."""
        by_seed = {
            seed: esolangs.run(
                "LaserFuck", self.PROGRAM, stdin="", timeout=5, seed=seed
            )
            for seed in range(8)
        }
        assert len(set(by_seed.values())) == 2
        assert by_seed[0] == "3"

    def test_no_seed_is_the_language_as_specified(self) -> None:
        """The default has to stay the system's randomness, not a fixed draw."""
        assert esolangs.run("LaserFuck", self.PROGRAM, stdin="", timeout=5) in {"", "3"}

    def test_a_seed_for_a_language_that_draws_nothing_is_refused(self) -> None:
        """Ignoring it would be right by accident and hide the likelier fault."""
        with pytest.raises(esolangs.ArgumentError, match="draws no random values"):
            esolangs.run("brainfuck", "+++.", stdin="", timeout=5, seed=1)

    @pytest.mark.parametrize("seed", ["x", "\ud800", 1.5, True, object()])
    def test_a_seed_that_is_not_an_integer_is_an_argument_error(
        self, seed: object
    ) -> None:
        """``random.Random`` took ``"x"`` and ``1.5`` and ran; others leaked."""
        with pytest.raises(esolangs.ArgumentError, match="seed must be an integer"):
            esolangs.run("LaserFuck", self.PROGRAM, timeout=5, seed=seed)  # type: ignore[arg-type]

    def test_the_languages_that_draw_are_the_ones_named(self) -> None:
        """The message lists them and ``random`` marks them, so both must be right."""
        drawing = [
            name
            for name in esolangs.list_languages()
            if "rng" in inspect.signature(interpreter_module(name).run).parameters
        ]
        assert drawing
        with pytest.raises(esolangs.ArgumentError) as caught:
            esolangs.run("brainfuck", "+++.", stdin="", timeout=5, seed=1)
        seed_help = " ".join(HELP["run"].split("\n  --seed N", 1)[1].split())
        for name in drawing:
            assert name in str(caught.value)
            assert esolangs.describe(name)["random"], name
        # The help points at ``describe``'s fact rather than copying the list.
        assert "describe --json" in seed_help
        assert "`random`" in seed_help
        assert "languages that draw" in str(esolangs.run.__doc__)

    def test_the_languages_that_terminate_are_the_ones_named(self) -> None:
        """``run --timeout`` names every language whose answer is halting."""
        halting = [
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["answer_mode"] == "termination"
        ]
        assert halting
        option = HELP["run"].split("\n  --timeout SECONDS", 1)[1]
        timeout_help = " ".join(option.split("\n  --scale N", 1)[0].split())
        for name in halting:
            assert name in timeout_help, f"run --help's --timeout omits {name}"

    def test_the_cli_takes_one(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """And repeats, which is the whole point of the flag."""
        path = tmp_path / "lf.txt"
        path.write_text(self.PROGRAM)
        args = ["run", "--timeout", "5", "--seed", "0", "LaserFuck", str(path)]
        assert call_both(args, capsys)[0] == call_both(args, capsys)[0] == "3"

    def test_the_cli_refuses_a_seed_that_is_not_a_number(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """Named as a flag problem rather than a ValueError from further in."""
        path = tmp_path / "lf.txt"
        path.write_text(self.PROGRAM)
        with pytest.raises(SystemExit):
            call_main(
                ["run", "--timeout", "5", "--seed", "abc", "LaserFuck", str(path)],
                capsys,
            )
        assert "--seed must be a whole number" in capsys.readouterr().err

    def test_the_help_mentions_it(self) -> None:
        """A flag nobody can find is a flag nobody has."""
        assert "--seed" in HELP["run"]


def test_width_floor_matches_its_source_and_overrun_count() -> None:
    """Warnings follow actual rendered widths, including narrower constructions."""
    assert esolangs.describe("LaserFuck")["width_aware"]
    source = esolangs.generate("LaserFuck", "10010110", width=1)
    assert max(map(len, source.splitlines())) == 8
    assert overruns("LaserFuck", "10010110") == (2, 7)
    assert evaluate_generated("LaserFuck", "10010110", width=1) == "10010110"


def test_the_branching_detector_takes_a_vm() -> None:
    """The adapter's seeded ``rng`` must not narrow the search."""
    looping = make_vm("LaserFuck", " v \n}o{\n ^ ")
    assert run_until_halt_or_all_branches_cycle(looping) is False
    assert run_until_halt_or_all_branches_cycle(make_vm("LaserFuck", "}o{")) is True


def test_run_still_takes_one_because_it_takes_any_program() -> None:
    """The distinction: ``run`` executes what a caller wrote."""
    assert {
        esolangs.run("LaserFuck", "o+++.\n", stdin="", timeout=5, seed=0)
        for _ in range(4)
    } == {esolangs.run("LaserFuck", "o+++.\n", stdin="", timeout=5, seed=0)}


def test_stepping_through_the_random_instruction_is_reproducible() -> None:
    """Its random instruction steps the same way twice under one seed."""
    assert_random_steps_reproduce("LaserFuck", "*\no")


def test_the_first_move_is_down_the_rows() -> None:
    """It begins vertically, so ``VM.ip``'s first component moves first."""
    assert_starts_downward("LaserFuck")
