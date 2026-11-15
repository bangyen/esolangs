"""The five hang detectors."""

from dataclasses import replace
from functools import lru_cache, wraps
from random import Random

import pytest

from esolangs import Catalog, ExecutionLimits, ExecutionResult, Language
from esolangs.debugger import Debugger
from esolangs.exceptions import (
    ArgumentError,
    ExecutionCapError,
    ExecutionTimeoutError,
    InterpreterLimitError,
)
from esolangs.languages.brainfuck.interpreter import _Machine as Brainfuck
from esolangs.runtime._execution import interpreter_module
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import (
    complete_vm,
    make_vm,
    run_until_halt,
    run_until_halt_or_all_branches_cycle,
    run_until_halt_or_ancestor,
    run_until_halt_or_cycle,
    run_until_halt_or_growth,
    run_until_halt_or_value_growth,
)
from tests.support.reference import REFERENCE


def _bf(code: str, stdin: str = "") -> Brainfuck:
    return Brainfuck(code, ScriptedIO(stdin))


class TestRunUntilHaltOrCycle:
    def test_a_machine_already_halted_is_reported_as_halting(self) -> None:
        """The loop is never entered, and the answer is still ``True``."""
        vm = make_vm(REFERENCE, "++")
        run_until_halt(vm)
        assert vm.halted
        assert run_until_halt_or_cycle(vm) is True


class TestTheDetectorsTakeAVM:
    """Every detector accepts what ``make_vm`` returns, not just a ``_Machine``."""

    def test_the_growth_detector_takes_a_vm(self) -> None:
        """``+[>]`` walks off onto a zero; ``+[>+]`` grows a cell a lap."""
        assert run_until_halt_or_growth(make_vm(REFERENCE, "+[>]")) is True
        assert run_until_halt_or_growth(make_vm(REFERENCE, "+[>+]")) is False

    def test_the_value_growth_detector_refuses_a_bounded_language(self) -> None:
        """Brainfuck's cells wrap, so a climb there is a cycle, not a proof."""
        with pytest.raises(TypeError, match="affine machine"):
            run_until_halt_or_value_growth(make_vm(REFERENCE, "+[>+]"))

    def test_an_object_that_is_neither_raises_type_error(self) -> None:
        """An object without compatible interpreter state cannot supply a proof."""
        with pytest.raises(TypeError, match="steppable with a snapshot"):
            run_until_halt_or_cycle(object())

    @pytest.mark.parametrize("root_halted", [False, True])
    def test_a_zero_branch_cap_stops_before_exploring(
        self, *, root_halted: bool
    ) -> None:
        """A zero cap stops before exploring the initial branching state."""

        class _BranchOnly:
            def branching_snapshot(self) -> int:
                pytest.fail("a zero-state budget cannot acquire the branch root")

            def branching_halted(self, _state: int) -> bool:
                return root_halted

            def branching_successors(self, state: int, _limit: int) -> list[int]:
                return [state + 1]

        with pytest.raises(TimeoutError, match="branching states"):
            run_until_halt_or_all_branches_cycle(_BranchOnly(), limit=0)

    def test_a_live_halt_still_requires_branch_compatibility(self) -> None:
        vm = make_vm(REFERENCE, "")
        assert vm.halted
        with pytest.raises(TypeError, match="branch-enumerable"):
            run_until_halt_or_all_branches_cycle(vm, limit=0)


@pytest.mark.parametrize(("program", "limit"), [("", 0), ("+", 1)])
def test_growth_detector_accepts_halt_at_step_limit(program: str, limit: int) -> None:
    assert run_until_halt_or_growth(make_vm("Brainfuck", program), limit) is True


@pytest.mark.parametrize(
    "detector",
    [
        run_until_halt_or_cycle,
        run_until_halt_or_all_branches_cycle,
        run_until_halt_or_growth,
        run_until_halt_or_value_growth,
        run_until_halt,
        run_until_halt_or_ancestor,
    ],
)
@pytest.mark.parametrize("limit", [float("nan"), float("inf"), 1.5, "3", True, -1])
def test_invalid_limit_is_refused_before_machine_acquisition(detector, limit) -> None:
    with pytest.raises(ArgumentError, match="limit"):
        detector(object(), limit=limit)


def test_direct_vm_and_proof_caps_use_normalized_integer_values() -> None:
    class Zero(int):
        def __le__(self, _other):
            return False

    limit = Zero(0)
    vm = make_vm(REFERENCE, "+.")
    assert not run_until_halt(vm, limit)
    with pytest.raises(TimeoutError, match="after 0 steps"):
        run_until_halt_or_cycle(vm, limit)
    with pytest.raises(ExecutionCapError, match="max_steps"):
        complete_vm(vm, max_steps=limit)
    assert vm.ip == 0
    assert vm.output == ""
    assert complete_vm(vm, max_steps=2) == "\x01"


def test_stop_callback_only_fires_before_a_permitted_step() -> None:
    seen = []

    def stop() -> bool:
        seen.append(vm.ip)
        return False

    for limit, calls in ((0, []), (1, [0]), (2, [0, 1])):
        seen.clear()
        vm = make_vm(REFERENCE, "++")
        assert run_until_halt(vm, limit=limit, stop=stop) is (limit == 2)
        assert seen == calls
        assert vm.ip == limit
    for source, limit in (("", 1), ("++", 0), ("++", 1)):
        vm = make_vm(REFERENCE, source)
        for invalid in (1, lambda _required: False):
            with pytest.raises(ArgumentError, match="stop must be callable"):
                run_until_halt(vm, limit=limit, stop=invalid)
        assert vm.ip == 0

    @wraps(lambda _event: False)
    def adapter() -> bool:
        return True

    @wraps(adapter)
    def needs_argument(_event) -> bool:
        return True

    @wraps(adapter)
    def forwards(*args, **kwargs) -> bool:
        return adapter(*args, **kwargs)

    with pytest.raises(ArgumentError, match="without arguments"):
        run_until_halt(vm, limit=2, stop=needs_argument)
    for predicate in (adapter, forwards, lru_cache(adapter)):
        assert run_until_halt(vm, limit=2, stop=predicate) is False
        assert vm.ip == 0
    assert run_until_halt(vm, limit=2, stop=bool)


def test_halt_driver_requires_a_stepper_before_inspecting_state() -> None:
    class MissingStep:
        @property
        def halted(self):
            pytest.fail("validation must precede reading state")

    class MissingHalted:
        def step(self):
            pytest.fail("validation must precede stepping")

    for machine in (object(), MissingStep()):
        with pytest.raises(ArgumentError, match=r"machine.*step"):
            run_until_halt(machine, limit=0)
    with pytest.raises(ArgumentError, match=r"machine.*halted"):
        run_until_halt(MissingHalted(), limit=0)


def test_branch_search_does_not_hide_an_unexpected_or_global_failure() -> None:
    class _BranchOnly:
        def __init__(self, error_type):
            self.error_type = error_type

        def branching_snapshot(self) -> int:
            return 0

        def branching_halted(self, state: int) -> bool:
            return state == 2

        def branching_successors(self, state: int, _limit: int) -> tuple[int, ...]:
            if state == 0:
                return (1, 2)
            raise self.error_type("branch callback failed")

    for error_type in (TypeError, AssertionError, ValueError, ExecutionTimeoutError):
        with pytest.raises(error_type, match="branch callback failed"):
            run_until_halt_or_all_branches_cycle(_BranchOnly(error_type), limit=3)


class _Climber:
    """Never halts: each step walks onto a fresh cell, pushes a frame with
    the same entry, and adds one to a value -- a hang all three proofs see."""

    halted = False
    ip = 0

    def __init__(self) -> None:
        self.n = 0

    def step(self) -> None:
        self.n += 1

    @property
    def ptr(self) -> int:
        return self.n

    @property
    def tape(self) -> tuple[int, ...]:
        return (1,) + (0,) * self.n

    def input_position(self) -> int:
        return 0

    @property
    def frames(self) -> list[int]:
        return list(range(self.n + 1))

    def frame_entry_key(self, _frame: object) -> int:
        return 0

    key = 0
    clamp_slack = None

    @property
    def values(self) -> tuple[int, ...]:
        return (self.n,)


def test_ancestor_proof_prefers_halt_on_a_pushed_frame() -> None:
    class FrameMachine(_Climber):
        def __init__(self, stop_after: int | None) -> None:
            super().__init__()
            self.stop_after = stop_after

        def step(self) -> None:
            super().step()
            self.halted = self.n == self.stop_after

    for stop_after in (1, 2, None):
        machine = FrameMachine(stop_after)
        expected = stop_after is not None
        assert run_until_halt_or_ancestor(machine, limit=2) is expected
        assert machine.halted is expected
        assert machine.n == (stop_after or 2)

    machine = FrameMachine(2)
    with pytest.raises(TimeoutError, match="after 1 pushed frames"):
        run_until_halt_or_ancestor(machine, limit=1)
    assert machine.n == 1
    assert not machine.halted


class _RandomClimber(_Climber):
    """The same machine, declaring a draw it could branch on."""

    def branching_snapshot(self) -> int:
        return self.n

    def branching_halted(self, _state: object) -> bool:
        return False

    def branching_successors(self, state: object, _limit: int) -> list[object]:
        return [state]


_PROOFS = [
    run_until_halt_or_ancestor,
    run_until_halt_or_growth,
    run_until_halt_or_value_growth,
]


def test_proof_drivers_refuse_noncallable_members_before_stepping() -> None:
    class Machine(_Climber):
        def snapshot(self) -> int:
            return self.n

    for detector, member, machine in (
        *(
            (detector, "step", Machine())
            for detector in (run_until_halt_or_cycle, *_PROOFS)
        ),
        (run_until_halt_or_cycle, "snapshot", Machine()),
        (
            run_until_halt_or_all_branches_cycle,
            "branching_successors",
            _RandomClimber(),
        ),
    ):
        setattr(machine, member, 1)
        with pytest.raises(TypeError, match=rf"{member} must be callable"):
            detector(machine, limit=0)
        assert machine.n == 0


@pytest.mark.parametrize("detector", _PROOFS)
def test_a_lap_proof_refuses_a_random_machine(detector) -> None:
    """A draw can change the next lap, which every lap proof assumes away."""
    assert detector(_Climber()) is False  # control: the deterministic hang is proved
    with pytest.raises(TypeError, match="random machines"):
        detector(_RandomClimber())


def test_scoped_random_proofs_require_branch_enumeration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Seed 4 first repeats a state, while seed 1 first grows it twice.
    def prepare(source, options):
        rng = options["rng"]

        def bind(io):
            class Machine(_Climber):
                def snapshot(self):
                    return self.n, self.halted

                def step(self) -> None:
                    if rng.randbelow(2):
                        io.print_str("H")
                        self.halted = True
                    elif source == "++":
                        super().step()

            return Machine()

        return bind

    stock = Language(REFERENCE)
    declaration = stock.catalog.languages[stock.name]
    monkeypatch.setattr(
        interpreter_module(stock.name), "branchless_random", prepare, raising=False
    )
    runtime = replace(
        declaration.runtime, random=True, machine_preparation="branchless_random"
    )
    scoped = Catalog([replace(declaration, runtime=runtime)]).bind(stock.name)
    cases = [
        (run_until_halt_or_cycle, "+", 4, 2, "requires branch enumeration"),
        *((proof, "++", 1, 3, "random machines") for proof in _PROOFS),
    ]
    for detector, source, seed, steps, message in cases:
        prepared = scoped.prepare(source)
        limits = ExecutionLimits(max_steps=steps)
        for execution in (
            scoped.run(source, seed=seed, limits=limits),
            prepared.run(seed=seed, limits=limits),
        ):
            assert (execution.output, execution.steps) == ("H", steps)
        for machine in (
            scoped.make_vm(source, seed=seed),
            scoped.make_debugger(source, seed=seed),
            prepared.make_vm(seed=seed),
            prepared.make_debugger(seed=seed),
            Debugger(Debugger(prepared.make_debugger(seed=seed))),
        ):
            initial = machine.snapshot()
            with pytest.raises(TypeError, match=message):
                detector(machine, limit=steps)
            with pytest.raises(TypeError, match="branch-enumerable"):
                run_until_halt_or_all_branches_cycle(machine, limit=steps)
            assert machine.snapshot() == initial
            assert machine.output == ""
            assert run_until_halt(machine, limit=steps)
            assert machine.output == "H"
            assert detector(machine, limit=0) is True
            assert run_until_halt_or_all_branches_cycle(machine, limit=0) is True


def test_caller_branch_protocol_precedes_private_machine_storage(monkeypatch) -> None:
    class BranchMachine(_Climber):
        output = ""
        steppable_to_answer = True
        dumps_on_the_post_halt_step = False

        def __init__(self) -> None:
            super().__init__()
            self._machine = Random(4)
            self.commands = 0

        def step(self) -> None:
            self.commands += 1
            self.halted = bool(self._machine.randrange(2))

        def snapshot(self) -> bool:
            return self.halted

        def branching_snapshot(self) -> int:
            return int(self.halted)

        def branching_halted(self, state: int) -> bool:
            return state == 1

        def branching_successors(self, state: int, _limit: int) -> tuple[int, ...]:
            return (1,) if state else (0, 1)

    for layers in range(3):
        machine = BranchMachine()
        live = machine
        for _ in range(layers):
            live = Debugger(live)
        with pytest.raises(TypeError, match="some draws halt"):
            run_until_halt_or_cycle(live, limit=2)
        for detector in _PROOFS:
            with pytest.raises(TypeError, match="random machines"):
                detector(live, limit=2)
        assert run_until_halt_or_all_branches_cycle(live, limit=2)
        assert machine.commands == 0
        assert not live.halted
        assert run_until_halt(live, limit=2)
        assert machine.commands == 2
        for detector in (run_until_halt_or_cycle, *_PROOFS):
            assert detector(live, limit=0) is True

    class FixedBranchDebugger(Debugger):
        def branching_snapshot(self):
            return 0

        def branching_halted(self, _state):
            return False

        def branching_successors(self, _state, _limit):
            return (0,)

    machine = BranchMachine()
    live = Debugger(FixedBranchDebugger(machine))
    assert run_until_halt_or_all_branches_cycle(live, limit=1) is False
    assert run_until_halt_or_cycle(live, limit=1) is False
    assert machine.commands == 0

    _check_malformed_branch_states(monkeypatch)


def _check_malformed_branch_states(monkeypatch) -> None:
    stock = Language(REFERENCE)
    declaration = stock.catalog.languages[stock.name]
    runtime = replace(
        declaration.runtime, random=True, machine_preparation="probe_branch_states"
    )
    contract = replace(
        declaration.contract,
        answer_mode="termination",
        answer_values=("halts", "diverges"),
    )
    api = Catalog([replace(declaration, runtime=runtime, contract=contract)]).bind(
        stock.name
    )
    states = {"root": (0,), "successor": (1,), "replay": (1,)}

    class Machine:
        halted = False

        def __init__(self, io):
            self.io = io
            io.print_char(chr(io.input_char()))

        def step(self):
            self.io.print_str("!")
            self.halted = True

        def snapshot(self):
            return self.halted

        def branching_snapshot(self):
            return states["replay" if self.halted else "root"]

        def branching_halted(self, state):
            return state == (1,)

        def branching_successors(self, _state, _limit):
            return (states["successor"],)

    module = interpreter_module(stock.name)
    monkeypatch.setattr(
        module, "probe_branch_states", lambda *_args: Machine, raising=False
    )
    artifact = api.from_source("+.")
    limits = ExecutionLimits(max_steps=2)
    detectors = (run_until_halt_or_cycle, run_until_halt_or_all_branches_cycle)
    for detector in detectors:
        assert detector(api.make_debugger(artifact, stdin="1"), limit=2)
    result = api.evaluate(artifact, [1], limits=limits)
    assert result.termination.branches.terminal == (1,)
    assert result.observation == ExecutionResult("1!", 1, 1, 0)
    _check_branch_successor_containers(api, artifact, limits, Machine, monkeypatch)

    class EqualUnhashable(list):
        __hash__ = None

        def __eq__(self, other):
            return tuple(self) == other

    for field, values in (
        ("root", ([0], ([0],))),
        ("successor", ([1], ([1],))),
        ("replay", ([1], EqualUnhashable([1]))),
    ):
        original = states[field]
        for value in values:
            states[field] = value
            for detector in detectors:
                debug = api.make_debugger(artifact, stdin="1")
                if field == "replay":
                    assert detector(debug, limit=2)
                else:
                    with pytest.raises(TypeError, match="hashable state"):
                        detector(debug, limit=2)
                assert debug.observation == ExecutionResult("1", 1, 1, 0, steps=0)
            with pytest.raises(InterpreterLimitError, match="hashable state") as caught:
                api.evaluate(artifact, [1], limits=limits)
            output = "1!" if field == "replay" else "1"
            assert caught.value.observation == ExecutionResult(output, 1, 1, 0)
            assert caught.value.partial_output == output
        states[field] = original

    with monkeypatch.context() as hooks:
        hooks.setattr(Machine, "branching_successors", 7)
        debug = api.make_debugger(artifact, stdin="1")
        with pytest.raises(TypeError, match="branching_successors must be callable"):
            run_until_halt_or_all_branches_cycle(debug, limit=2)
        with pytest.raises(
            InterpreterLimitError, match="branching_successors must be callable"
        ) as caught:
            api.evaluate(artifact, [1], limits=limits)
        assert caught.value.observation == ExecutionResult("1", 1, 1, 0)
        assert caught.value.partial_output == "1"

    original = TypeError("branching callback refused")

    def refuse(*_args):
        raise original

    for name in ("branching_snapshot", "branching_successors"):
        with monkeypatch.context() as hooks:
            hooks.setattr(Machine, name, refuse)
            debug = api.make_debugger(artifact, stdin="1")
            with pytest.raises(TypeError, match="branching callback refused") as caught:
                run_until_halt_or_all_branches_cycle(debug, limit=2)
            assert caught.value is original
            with pytest.raises(TypeError, match="branching callback refused") as caught:
                api.evaluate(artifact, [1], limits=limits)
            assert caught.value is original


def _check_branch_successor_containers(api, artifact, limits, machine, monkeypatch):
    class Miscounted(list):
        def __len__(self):
            return 1

    class NonIterable(list):
        __iter__ = None

    def prove():
        live = api.make_debugger(artifact, stdin="1")
        return run_until_halt_or_all_branches_cycle(live, limit=2)

    for container, diagnostic in (
        ((), "requires a successor"),
        ([], "requires a successor"),
        (7, "sequence or None"),
        (NonIterable([(1,)]), "finite sequence"),
        (Miscounted([(0,), (1,)]), "count disagrees"),
    ):
        with monkeypatch.context() as hooks:
            hooks.setattr(
                machine, "branching_successors", lambda *_args, result=container: result
            )
            with pytest.raises(TypeError, match=diagnostic):
                prove()
            with pytest.raises(InterpreterLimitError, match=diagnostic) as caught:
                api.evaluate(artifact, [1], limits=limits)
            assert caught.value.observation == ExecutionResult("1", 1, 1, 0)
            assert caught.value.partial_output == "1"

    with monkeypatch.context() as hooks:
        hooks.setattr(machine, "branching_successors", lambda *_args: [(1,)])
        assert prove()
        result = api.evaluate(artifact, [1], limits=limits)
        assert result.termination.branches.terminal == (1,)
        assert result.observation == ExecutionResult("1!", 1, 1, 0)
        hooks.setattr(machine, "branching_successors", lambda *_args: None)
        with pytest.raises(TimeoutError, match="cannot be safely forked"):
            prove()
        with pytest.raises(
            InterpreterLimitError, match="cannot be safely forked"
        ) as caught:
            api.evaluate(artifact, [1], limits=limits)
        assert caught.value.observation == ExecutionResult("1", 1, 1, 0)
