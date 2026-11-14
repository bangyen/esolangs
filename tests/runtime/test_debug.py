"""Tests for the breakpoint/watch debugger over the VM."""

import pytest

import esolangs
import esolangs.debugger as debugger_api
from tests.support.pick import one
from tests.support.reference import REFERENCE


class TestRun:
    def test_run_to_completion_matches_interpreter(self) -> None:
        dbg = debugger_api.make_debugger(REFERENCE, "+++[>+++<-]>.")
        dbg.run()
        assert dbg.halted
        assert dbg.output == esolangs.run(REFERENCE, "+++[>+++<-]>.").output

    def test_max_steps_bounds_runaway(self) -> None:
        dbg = debugger_api.make_debugger(REFERENCE, "+[]")
        dbg.run(limits=esolangs.ExecutionLimits(max_steps=10))
        assert not dbg.halted

    def test_step_guards_on_halt(self) -> None:
        dbg = debugger_api.make_debugger(REFERENCE, "+")
        dbg.run()
        dbg.step()  # must not raise
        assert dbg.halted


def test_breakpoint_predicate_is_checked_once_at_a_stop() -> None:
    dbg = debugger_api.make_debugger(REFERENCE, "+++.")
    positions = []

    def first_check(vm):
        positions.append(vm.ip)
        return len(positions) == 1

    dbg.break_when(first_check)
    assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=3)) == "breakpoint"
    assert positions == [0]
    assert dbg.observation.steps == 0
    assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=4)) == "halted"


def test_manual_steps_rearm_a_breakpoint_after_leaving_it() -> None:
    dbg = debugger_api.make_debugger(REFERENCE, "+[+]")
    dbg.break_at(2)
    assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=3)) == "breakpoint"
    dbg.step()
    assert dbg.ip == 3
    dbg.step()
    assert dbg.ip == 2
    assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=0)) == "breakpoint"


def test_debugger_breakpoint_and_watch_counts_use_integer_storage() -> None:
    class Index(int):
        def __hash__(self):
            raise AssertionError("subclass hashing must not affect a watch")

        def __eq__(self, _other):
            raise AssertionError("subclass equality must not affect a breakpoint")

    dbg = debugger_api.make_debugger(REFERENCE, "+.")
    watch = dbg.watch_cell(Index(0))
    dbg.break_at(Index(0))
    dbg.break_on_cell(Index(0), Index(1))
    limits = esolangs.ExecutionLimits(max_steps=2)
    assert dbg.run(limits=limits) == "breakpoint"
    assert dbg.observation.steps == 0
    assert dbg.run(limits=limits) == "breakpoint"
    assert dbg.observation.steps == 1
    assert watch == [1]
    assert dbg.run(limits=limits) == "halted"
    assert dbg.output == "\x01"


#: Two of the nine dump-on-post-halt languages, one reader and one template:
#: the dump step is the debugger's shared code, and test_vm_protocol already
#: checks every language's flag against its behaviour.
_DUMPERS = [
    name
    for template in (False, True)
    for name in one(dumps_on_the_post_halt_step=True, parameterized=template)
]


def _runnable(name: str, table: str = "0110") -> tuple[esolangs.ProgramArtifact, str]:
    """Return a filled program and the stdin to drive it with."""
    program = esolangs.generate(name, table)
    if esolangs.describe(name).parameterized:
        return esolangs.instantiate(name, program, [0, 0]), ""
    return program, esolangs.encode_inputs(name, [0, 0])


class TestABreakpointAtTheHaltIsReported:
    """``run`` reported ``"halted"`` over a watch that had fired."""

    def test_an_output_watch_on_the_last_step_fires(self) -> None:
        """The case it was reported for, on the flagship language."""
        dbg = debugger_api.make_debugger(
            REFERENCE, esolangs.generate(REFERENCE, "0110"), stdin="10"
        )
        dbg.break_on_output("1")
        assert (
            dbg.run(limits=esolangs.ExecutionLimits(max_steps=100_000)) == "breakpoint"
        )
        assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=100_000)) == "halted"
        assert dbg.halted

    @pytest.mark.parametrize("name", _DUMPERS)
    def test_the_answer_is_never_stranded_by_that_stop(self, name: str) -> None:
        """A stop before the dump must not cost the caller the answer."""
        assert esolangs.describe(name).dumps_on_the_post_halt_step
        program, stdin = _runnable(name)
        dbg = debugger_api.make_debugger(name, program, stdin=stdin)
        dbg.break_when(lambda vm: vm.halted and vm.output == "")
        assert (
            dbg.run(limits=esolangs.ExecutionLimits(max_steps=300_000)) == "breakpoint"
        )
        assert dbg.output == ""
        assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=300_000)) == "halted"
        assert (
            dbg.output
            == esolangs.run(
                name,
                program,
                stdin=stdin,
                limits=esolangs.ExecutionLimits(execution_timeout=30),
            ).output
        )

    @pytest.mark.parametrize("name", _DUMPERS)
    def test_the_dump_step_is_taken_once_not_once_per_run(self, name: str) -> None:
        """Three idle runs grew a watch history by three."""
        program, stdin = _runnable(name)
        dbg = debugger_api.make_debugger(name, program, stdin=stdin)
        history = dbg.watch_cell(0)
        dbg.run(limits=esolangs.ExecutionLimits(max_steps=300_000))
        after_one = len(history)
        for _ in range(4):
            dbg.run(limits=esolangs.ExecutionLimits(max_steps=300_000))
        assert len(history) == after_one

    def test_an_expired_deadline_leaves_the_pending_dump_unfinished(
        self, monkeypatch
    ) -> None:
        name = _DUMPERS[0]
        source, stdin = _runnable(name)
        dbg = debugger_api.make_debugger(name, source, stdin=stdin)
        dbg.break_when(lambda vm: vm.halted)
        assert (
            dbg.run(limits=esolangs.ExecutionLimits(max_steps=300_000)) == "breakpoint"
        )
        assert dbg.halted
        assert dbg.observation.completion is None
        dbg.clear_breakpoints()
        times = iter((0.0, 1.0))
        monkeypatch.setattr(
            "esolangs.runtime._controller.monotonic", lambda: next(times)
        )
        assert (
            dbg.run(limits=esolangs.ExecutionLimits(execution_timeout=0.5))
            == "execution_timeout"
        )
        assert dbg.observation.completion is None
        assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=0)) == "halted"
        assert dbg.observation.completion is not None


class TestPointerFallback:
    """A tape machine that names no state still shows where it points."""

    def test_the_debugger_mirrors_the_pointer(self) -> None:
        dbg = debugger_api.make_debugger(REFERENCE, ">>,", stdin="")
        assert dbg.ptr == 0
        dbg.step()
        assert dbg.ptr == 1
