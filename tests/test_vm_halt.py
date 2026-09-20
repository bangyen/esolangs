"""The plain bounded VM drive stops at its exact budget or predicate."""

import esolangs


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
