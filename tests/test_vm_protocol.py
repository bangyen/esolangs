"""The VM protocol, swept over every language rather than per language."""

import contextlib
import io
from typing import cast
from unittest.mock import patch

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs import vm as vm_module
from esolangs.debugger import complete_vm
from esolangs.exceptions import InterpreterLimitError, ProgramError
from esolangs.registry import INTERPRETERS
from esolangs.vm import VM, _climbs_forever, make_vm, run_until_halt
from tests.generator_support import CHECK
from tests.pick import languages

from .samples import (
    DUMPS_ON_THE_POST_HALT_STEP,
    NEVER_SELF_HALTS,
    NONDETERMINISTIC_AGAINST_RUN,
    SAMPLES,
)

# The sweep drives every machine to its halt, so a runaway sample would
# hang the suite rather than fail it.  Every sample that halts at all does
# so in well under a hundred steps; this is the bound that turns a hang
# into a readable failure.
_STEP_BUDGET = 100_000

_PARAMS = [
    pytest.param(name, program, stdin, id=name)
    for name, (program, stdin) in sorted(SAMPLES.items())
]


def _drive(vm: VM) -> str:
    """Step ``vm`` to its halt and return everything it wrote."""
    if not run_until_halt(vm, _STEP_BUDGET):
        raise AssertionError(f"no halt within {_STEP_BUDGET} steps")
    return vm.output


# The prefix the never-halting languages are compared over instead of a
# halt.  They have no halt to drive to, so "the same run" has to mean "the
# same state after the same number of steps".
#
# Output alone will not do it.  Suffolk's sample writes within this many
# steps, but A Painter Ant's writes nothing at all -- not at a hundred
# steps and not at ten thousand, because it paints rather than prints --
# so comparing its output would be comparing "" against "" and passing no
# matter what the interpreter did.  The comparison is therefore over the
# observable state as well, which both of them do move.
_PREFIX_STEPS = 100

# What a run is compared on: everything the VM exposes about where it
# ended up.  ``memory`` and ``stack`` are lists, so this is a tuple of
# copies rather than views into the machine.
_Observed = tuple[str, object, list[int], list[object]]


def _observe(vm: VM) -> _Observed:
    """Return everything ``vm`` exposes about its current state."""
    return (vm.output, vm.ip, vm.memory, vm.stack)


def _machine_of(vm: VM) -> object | None:
    """Return the interpreter state object an adapter wraps, if it has one."""
    for value in vars(vm).values():
        if hasattr(value, "snapshot"):
            return cast(object, value)
    return None


class TestSamplesCoverEveryLanguage:
    """The table is the sweep's coverage, so it is the thing to lock."""

    def test_every_registry_language_has_a_sample(self) -> None:
        missing = sorted(set(INTERPRETERS) - set(SAMPLES))
        assert not missing, f"no VM sample for {missing}; {CHECK}"

    def test_no_sample_names_a_language_the_registry_lost(self) -> None:
        stale = sorted(set(SAMPLES) - set(INTERPRETERS))
        assert not stale, f"remove {stale} from SAMPLES in tests/samples.py"

    @pytest.mark.parametrize(
        "exceptions",
        [
            DUMPS_ON_THE_POST_HALT_STEP,
            NEVER_SELF_HALTS,
            NONDETERMINISTIC_AGAINST_RUN,
        ],
        ids=["dumps", "never-halts", "nondeterministic"],
    )
    def test_the_named_exceptions_are_real_languages(
        self, exceptions: frozenset[str]
    ) -> None:
        """A renamed language must not leave an exception silently inert."""
        stale = sorted(exceptions - set(INTERPRETERS))
        assert not stale, f"remove or rename {stale} in tests/samples.py"


def _check_protocol(language: str, program: str, stdin: str) -> _Observed:
    """Run the halt and snapshot contract on one machine; return where it settled."""
    vm = make_vm(language, program, stdin=stdin)
    assert vm.self_halts == (language not in NEVER_SELF_HALTS)
    assert vm.dumps_on_the_post_halt_step == (language in DUMPS_ON_THE_POST_HALT_STEP)
    machine = _machine_of(vm)
    assert machine is not None, f"{language}'s adapter wraps no state object"
    hash(machine.snapshot())  # type: ignore[attr-defined]
    if language in NEVER_SELF_HALTS:
        for _ in range(_PREFIX_STEPS):
            vm.step()
        return _observe(vm)

    at_halt = _drive(vm)
    assert vm.halted
    vm.step()
    assert (vm.output != at_halt) == vm.dumps_on_the_post_halt_step
    if language not in NONDETERMINISTIC_AGAINST_RUN:
        assert vm.output == esolangs.run(language, program, stdin=stdin)

    settled = _observe(vm)
    state = vm.snapshot()
    hash(machine.snapshot())  # type: ignore[attr-defined]
    vm.step()
    assert vm.halted
    assert _observe(vm) == settled
    assert vm.snapshot() == state
    return settled


@pytest.mark.parametrize(("language", "program", "stdin"), _PARAMS)
class TestEveryLanguageHonoursTheProtocol:
    """Execute each sample once for the shared halt and snapshot contract."""

    def test_execution_and_post_halt_state(
        self, language: str, program: str, stdin: str
    ) -> None:
        """Then two interleaved machines must land on the same state, silently.

        Interleaving catches state shared between machines of one language
        (a module-level tape, say); the redirect catches a stray ``print``.
        """
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            settled = _check_protocol(language, program, stdin)
            pair = [make_vm(language, program, stdin=stdin) for _ in range(2)]
            if language in NEVER_SELF_HALTS:
                for _ in range(_PREFIX_STEPS):
                    for vm in pair:
                        vm.step()
            else:
                for _ in range(_STEP_BUDGET):
                    if all(vm.halted for vm in pair):
                        break
                    for vm in pair:
                        if not vm.halted:
                            vm.step()
                else:
                    raise AssertionError(f"no halt within {_STEP_BUDGET} steps")
                for vm in pair:
                    vm.step()  # the post-halt step ``settled`` was taken after
            assert [_observe(vm) for vm in pair] == [settled, settled]
        assert out.getvalue() == ""
        assert err.getvalue() == ""


@pytest.mark.parametrize(("language", "program", "stdin"), _PARAMS)
class TestEveryLanguageImplementsTheSameInterface:
    """Position metadata lets the debugger locate a moving instruction."""

    def test_a_positional_ip_says_what_it_counts(
        self, language: str, program: str, stdin: str
    ) -> None:
        """A tuple ``ip`` declares how to read it, in a shape the reader knows."""
        vm = make_vm(language, program, stdin=stdin)
        shape = vm.ip_shape
        assert shape in {"offset", "grid", "line", "opaque"}, (
            f"{language} declares ip_shape={shape!r}, which nothing reads"
        )
        shapes = set()
        for _ in range(10):
            if vm.halted:
                break
            shapes.add(type(vm.ip))
            with contextlib.suppress(Exception):
                vm.step()
        if tuple in shapes:
            assert shape != "offset", f"{language} reports a tuple ip as an offset"


class TestTheCoordinateOrderIsRowThenColumn:
    """``VM.ip``'s arity is unstable and the *order* is not, and only one
    of those was written down.
    """

    def test_a_single_row_grid_moves_in_the_second_component(self) -> None:
        """Alight and Super SNUSP lay their programs on one row."""
        for name in ("Alight", "Super SNUSP"):
            program, stdin = _row_for(name)
            assert program.count("\n") == 0, name  # one row
            assert _first_move(name, program, stdin)[0] == 0, name

    def test_a_downward_start_moves_in_the_first_component(self) -> None:
        """Dig, Flowchart, LaserFuck and Streetcode begin vertically."""
        widths = {"Flowchart": 1}
        for name in ("Dig", "Flowchart", "LaserFuck", "Streetcode"):
            program, stdin = _row_for(name, widths.get(name))
            before, after = _first_move_pair(name, program, stdin)
            assert before[0] != after[0], name
            assert before[1] == after[1], name


def _row_for(name: str, width: int | None = None) -> tuple[str, str]:
    """A runnable program and its stdin for a two-input table."""
    table = "0110"
    program = (
        esolangs.generate(name, table)
        if width is None
        else esolangs.generate(name, table, width=width)
    )
    if esolangs.describe(name)["parameterized"]:
        return esolangs.instantiate(name, program, [0, 0]), ""
    return program, esolangs.encode_inputs(name, [0, 0], truth_table=table)


def _first_move_pair(
    name: str, program: str, stdin: str
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """The coordinate before and after the first move that changes it."""
    vm = debugger_api.make_vm(name, program, stdin=stdin)
    start = vm.ip
    assert isinstance(start, tuple)
    for _ in range(400):
        if vm.halted:
            break
        vm.step()
        here = vm.ip
        if isinstance(here, tuple) and len(here) >= 2 and here[:2] != start[:2]:
            return start[:2], here[:2]
    raise AssertionError(f"{name} never moved")


def _first_move(name: str, program: str, stdin: str) -> tuple[int, int]:
    """Which components changed on the first move, as a (row, col) pair."""
    before, after = _first_move_pair(name, program, stdin)
    return (before[0] != after[0], before[1] != after[1])


def _sampled(**facts: object) -> str:
    """The first language with these facts that has a sample program."""
    return next(name for name in languages(**facts) if name in SAMPLES)


@pytest.mark.medium
# A tape language, a grid language, and one that never halts by itself:
# ``complete_vm`` is the same driver for all of them.
@pytest.mark.parametrize(
    "name",
    [
        _sampled(state_model="tape"),
        _sampled(state_model="grid", self_halts=True),
        _sampled(self_halts=False),
    ],
)
def test_completion_agrees_with_running(name):
    source, stdin = SAMPLES[name]
    vm = make_vm(name, source, stdin=stdin)
    if not vm.self_halts:
        with pytest.raises(esolangs.ArgumentError, match="self-halts"):
            complete_vm(vm)
        return
    expected = esolangs.run(name, source, stdin=stdin)
    assert complete_vm(vm) == expected
    state = vm.snapshot()
    assert complete_vm(vm, max_steps=0) == expected
    assert vm.snapshot() == state


@pytest.mark.medium
def test_exhaustion_keeps_partial_state_and_can_resume():
    vm = make_vm("brainfuck", "+.")
    with pytest.raises(esolangs.InterpreterLimitError):
        complete_vm(vm, max_steps=1)
    assert vm.output == ""
    assert complete_vm(vm, max_steps=2) == "\x01"


@pytest.mark.parametrize("budget", [-1, True, 1.5])
def test_completion_rejects_invalid_budgets(budget):
    with pytest.raises(esolangs.ArgumentError):
        complete_vm(make_vm("brainfuck", "+."), max_steps=budget)


@pytest.mark.medium
def test_completion_can_opt_out_of_the_step_budget():
    assert complete_vm(make_vm("brainfuck", "+."), max_steps=None) == "\x01"


# Three visits, ten steps apart, whose values climb by a constant 1 with
# the input cursor never moving: the shape the certificate accepts.
CLIMBING = [(0, (0,), 0), (10, (1,), 0), (20, (2,), 0)]


class TestClimbsForever:
    def test_a_constant_positive_step_with_held_clamps_is_certified(self) -> None:
        assert _climbs_forever(CLIMBING, [None] * 21) is True

    def test_a_moving_input_cursor_is_not_certified(self) -> None:
        """Consuming input between visits means the laps are not alike."""
        visits = [(0, (0,), 0), (10, (1,), 1), (20, (2,), 1)]
        assert _climbs_forever(visits, [None] * 21) is False

    def test_two_different_steps_are_not_certified(self) -> None:
        """The second lap climbs by 2 where the first climbed by 1."""
        visits = [(0, (0,), 0), (10, (1,), 0), (20, (3,), 0)]
        assert _climbs_forever(visits, [None] * 21) is False

    def test_a_drifting_clamp_is_not_certified(self) -> None:
        """The step repeats, but a slack sinking toward zero will flip."""
        slacks: list[int | None] = [5] * 10 + [3] * 11
        assert _climbs_forever(CLIMBING, slacks) is False


class TestTheArmsThatTranslateWhatAnInterpreterRaises:
    """``make_vm`` and ``step`` promise every deliberate failure is ours."""

    @staticmethod
    def _adapter(fault: BaseException) -> object:
        def build(*_args: object, **_kwargs: object) -> object:
            raise fault

        return build

    def test_a_program_error_from_the_loader_passes_through(self) -> None:
        """Already ours, so it is re-raised rather than wrapped twice."""
        planted = ProgramError("unmatched something")
        with (
            patch.object(
                vm_module.interpreter_module("brainfuck"),
                "_Machine",
                self._adapter(planted),
            ),
            pytest.raises(ProgramError) as exc,
        ):
            debugger_api.make_vm("brainfuck", "+")
        assert exc.value is planted

    def test_a_recursion_error_from_the_loader_becomes_a_limit(self) -> None:
        """A loader that recurses past CPython's stack is a limit, not a bug."""
        with (
            patch.object(
                vm_module.interpreter_module("brainfuck"),
                "_Machine",
                self._adapter(RecursionError()),
            ),
            pytest.raises(InterpreterLimitError, match="recursed deeper"),
        ):
            debugger_api.make_vm("brainfuck", "+")

    def test_a_program_error_from_a_step_passes_through(self) -> None:
        """The same promise one layer down, where the machine is running."""
        machine = debugger_api.make_vm("brainfuck", "+++")
        planted = ProgramError("bad instruction")

        def boom() -> None:
            raise planted

        with (
            patch.object(machine._machine, "step", boom),  # noqa: SLF001 - the arm
            pytest.raises(ProgramError) as exc,
        ):
            machine.step()
        assert exc.value is planted


@pytest.mark.parametrize(
    ("fault", "error_type"),
    [
        (RecursionError(), InterpreterLimitError),
        (MemoryError(), InterpreterLimitError),
        (ValueError("invalid literal for int() with base 10: 'x'"), ProgramError),
        (RuntimeError("unexpected"), RuntimeError),
        (KeyboardInterrupt(), KeyboardInterrupt),
    ],
)
def test_step_keeps_shared_failure_translation(fault, error_type):
    machine = debugger_api.make_vm("brainfuck", "+")
    message = (
        "the brainfuck interpreter recursed deeper than "
        "CPython's stack limit allows on this program"
    )
    with (
        pytest.raises(error_type) as expected,
        vm_module.interpreter_errors(message, language="brainfuck"),
    ):
        raise fault

    def boom():
        raise fault

    with (
        patch.object(machine._machine, "step", boom),  # noqa: SLF001 - planted failure
        pytest.raises(error_type) as actual,
    ):
        machine.step()
    assert type(actual.value) is type(expected.value)
    assert str(actual.value) == str(expected.value)
    assert getattr(actual.value, "__notes__", ()) == getattr(
        expected.value, "__notes__", ()
    )
    assert actual.value.__cause__ is expected.value.__cause__
    if expected.value is fault:
        assert actual.value is fault


class TestRunUntilHalt:
    """The plain bounded drive the four consumers now share."""

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
        """A limit of ``n`` executes ``n`` commands, not ``n - 1`` or ``n + 1``."""
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
        """The predicate fires with the state it watched still intact."""
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

    def test_a_negative_budget_stops_rather_than_running_free(self) -> None:
        """A cap below zero is still a cap."""
        from esolangs.vm import run_until_halt

        for limit in (-1, -1000):
            assert (
                run_until_halt(debugger_api.make_vm("brainfuck", "+[]"), limit) is False
            )


class TestViews:
    """The machine's own named state, found rather than listed."""

    def test_it_finds_the_names_the_machine_gives_its_state(self) -> None:
        vm = debugger_api.make_vm("brainfuck", "+++")
        vm.step()
        assert dict(vm.views)["ptr"] == "0"
        assert dict(vm.views)["ind"] == "1"

    def test_it_leaves_out_what_every_language_already_offers(self) -> None:
        vm = debugger_api.make_vm("brainfuck", "+++")
        named = dict(vm.views)
        for standard in ("ip", "memory", "stack", "output", "halted"):
            assert standard not in named

    def test_a_long_sequence_is_cut_before_it_is_formatted(self) -> None:
        # A tape can be thousands of cells; the view has to be short, and
        # cheap to produce, at every step.
        from esolangs._vm_views import _abbreviate

        text = _abbreviate(list(range(4096)))
        assert len(text) < 80
        assert "+4088 more" in text

    def test_a_sequence_of_exactly_the_limit_is_shown_whole(self) -> None:
        """The cut is one *past* the limit, not at it."""
        from esolangs._vm_views import _VIEW_ITEMS, _abbreviate

        assert "more" not in _abbreviate(list(range(_VIEW_ITEMS)))
        assert "more" in _abbreviate(list(range(_VIEW_ITEMS + 1)))

    def test_the_scalar_cut_is_pinned_at_its_edge(self) -> None:
        """Sixty characters survive whole; sixty-one is cut."""
        from esolangs._vm_views import _abbreviate

        assert _abbreviate("x" * 58) == repr("x" * 58)
        assert len(repr("x" * 58)) == 60
        cut = _abbreviate("x" * 59)
        assert cut.endswith("...")
        assert len(cut) == 60

    def test_a_view_that_raises_is_skipped_rather_than_fatal(self) -> None:
        """One broken property must not take the whole screen down."""
        from esolangs.vm import _DelegatingVM

        class _Machine:
            @property
            def fine(self) -> int:
                return 7

            @property
            def broken(self) -> int:
                raise RuntimeError("no")

        vm = debugger_api.make_vm("brainfuck", "+")
        object.__setattr__(vm, "_machine", _Machine())
        assert _DelegatingVM.views.fget(vm) == (("fine", "7"),)
