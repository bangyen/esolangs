"""LaserFuck through the shared API, CLI and machinery."""

import pytest

import esolangs
import esolangs.debugger as debugger_api
from tests.test_vm import _run_all


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
