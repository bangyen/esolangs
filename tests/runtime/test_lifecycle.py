"""Completion preserves halt boundaries and requires periodic evidence."""

import json
import subprocess
import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest

import esolangs
from esolangs import vm
from esolangs.debugger import make_debugger
from esolangs.exceptions import ExecutionTimeoutError
from esolangs.registry import LANGUAGES
from esolangs.runtime._drive import drive, drive_periodic, finalize
from esolangs.runtime._execution import interpreter_module
from esolangs.runtime._lifecycle import (
    HALTED_REPORT,
    BoundaryCycle,
    Completion,
)
from tests.support.certification_barrier import guarded_worker
from tests.support.samples import SAMPLES


class _Periodic:
    completion = Completion.PERIODIC
    halted = False

    def __init__(self):
        self.state = 10
        self.steps = 0
        self.interrupted = False
        self.output = ""

    def snapshot(self):
        return self.state

    def interrupt(self):
        self.interrupted = True

    def step(self):
        if self.interrupted:
            self.output = str(self.state)
        else:
            self.state = {10: 11, 11: 0}.get(self.state, (self.state + 1) % 3)
            self.steps += 1


def test_periodic_completion_excludes_the_transient_and_keeps_pass_boundaries():
    machine = _Periodic()
    cycle = drive_periodic(machine, 2, policy=Completion.PERIODIC)
    assert cycle.first_pass >= 1
    assert cycle.repeat_pass - cycle.first_pass == 3
    assert machine.steps == cycle.repeat_pass * cycle.commands_per_pass
    assert machine.state == cycle.state
    assert machine.output == str(cycle.state)
    assert machine.interrupted
    assert not machine.halted


def test_an_empty_pass_still_renders_the_initial_state():
    machine = _Periodic()
    cycle = drive_periodic(machine, 0, policy=Completion.PERIODIC)
    assert cycle == BoundaryCycle(10, 0, 1, 0)
    assert machine.steps == 0
    assert machine.output == "10"


def test_periodic_completion_refuses_missing_or_stale_evidence():
    machine = _Periodic()
    with pytest.raises(ValueError, match="needs boundary-cycle evidence"):
        finalize(machine, policy=Completion.PERIODIC)
    with pytest.raises(ValueError, match="no longer matches"):
        finalize(machine, cycle=BoundaryCycle(0, 0, 1, 2), policy=Completion.PERIODIC)
    assert not machine.interrupted
    assert machine.steps == 0
    assert machine.output == ""


@pytest.mark.parametrize("policy", [Completion.HALTED, Completion.POST_HALT])
def test_halt_completion_never_executes_an_active_machine(policy):
    machine = _Periodic()
    machine.completion = policy
    with pytest.raises(ValueError, match="requires a halted machine"):
        finalize(machine, policy=policy)
    with pytest.raises(ValueError, match="requires periodic completion"):
        finalize(machine, cycle=BoundaryCycle(10, 0, 1, 2), policy=policy)
    assert machine.steps == 0
    with pytest.raises(ValueError, match="requires periodic completion"):
        drive_periodic(machine, 2, policy=policy)


def test_declared_post_halt_output_remains_available():
    class PostHalt:
        completion = Completion.POST_HALT

        def __init__(self):
            self.halted = False
            self.output = ""

        def step(self):
            if self.halted:
                self.output = "done"
            else:
                self.halted = True

    machine = PostHalt()
    drive(machine, policy=Completion.POST_HALT)
    assert machine.output == "done"
    with pytest.raises(TypeError, match="policy"):
        drive(machine)
    with pytest.raises(TypeError, match="Completion policy"):
        drive(machine, policy=None)


@pytest.mark.parametrize(
    ("first", "repeat", "stride"), [(-1, 1, 1), (1, 1, 1), (0, 1, -1)]
)
def test_cycle_evidence_needs_ordered_boundaries(first, repeat, stride):
    with pytest.raises(ValueError, match="ordered passes"):
        BoundaryCycle(0, first, repeat, stride)
    for invalid in (False, True, 0.0, 1.5, float("nan"), float("inf"), "1", None):
        for index in range(3):
            counts = [0, 1, 1]
            counts[index] = invalid
            with pytest.raises(ValueError, match="ordered passes"):
                BoundaryCycle(0, *counts)
    for state in ([], {}, ([],)):
        with pytest.raises(TypeError, match="unhashable"):
            BoundaryCycle(state, 0, 1, 1)
    assert BoundaryCycle(frozenset(), 0, 1, 0).commands_per_pass == 0


def test_a_timeout_does_not_finalize_periodic_output():
    class TimedOut(_Periodic):
        def step(self):
            raise ExecutionTimeoutError("test deadline")

    machine = TimedOut()
    with pytest.raises(ExecutionTimeoutError, match="test deadline"):
        drive_periodic(machine, 2, policy=Completion.PERIODIC)
    assert not machine.interrupted
    assert machine.output == ""


@pytest.mark.parametrize("name", sorted(LANGUAGES))
def test_interpreter_completion_has_one_declaration(name):
    machine = interpreter_module(name)._Machine
    assert isinstance(LANGUAGES[name].runtime.capabilities.completion, Completion)
    assert "dumps_on_the_post_halt_step" not in vars(machine)
    assert "steppable_to_answer" not in vars(machine)


@pytest.mark.medium
def test_declared_post_halt_factories_and_routes(monkeypatch):
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from esolangs.registry import LANGUAGES
from esolangs.runtime._lifecycle import Completion
from esolangs.vm import machine_traits, make_vm
selected = [lang for lang in LANGUAGES.values()
            if lang.runtime.capabilities is not None
            and lang.runtime.capabilities.completion is Completion.POST_HALT]
modules = {f'esolangs.languages.{lang.id}.interpreter' for lang in selected}
assert selected and not modules.intersection(sys.modules)
for lang in selected:
    assert machine_traits(lang.name)['dumps_on_the_post_halt_step']
assert not modules.intersection(sys.modules)
import json
samples = json.loads(sys.argv[1])
for lang in selected:
    code, stdin = samples[lang.name]
    make_vm(lang.name, code, stdin=stdin)
assert modules <= sys.modules.keys(), 'loading control did not fire'
""",
            json.dumps(
                {
                    name: SAMPLES[name]
                    for name, lang in LANGUAGES.items()
                    if lang.runtime.capabilities is not None
                    and lang.runtime.capabilities.completion is Completion.POST_HALT
                }
            ),
        ],
        check=True,
        timeout=10,
    )
    for name, language in LANGUAGES.items():
        caps = language.runtime.capabilities
        if caps is None or caps.completion is not Completion.POST_HALT:
            continue
        source, stdin = SAMPLES[name]
        seed = language.runtime.reproducible_seed if language.runtime.random else None
        native = esolangs.run(name, source, stdin=stdin, seed=seed)
        with guarded_worker():
            assert (
                esolangs.run(name, source, stdin=stdin, seed=seed, isolated=True)
                == native
            )
        module = interpreter_module(name)
        with monkeypatch.context() as control:
            control.setattr(module._Machine, "completion", Completion.HALTED)
            control.setattr(
                module._Machine,
                "incidental_view",
                property(lambda _self: 99),
                raising=False,
            )
            preparation = language.runtime.machine_preparation
            declared = SimpleNamespace(**{preparation: getattr(module, preparation)})
            control.setattr(
                vm,
                "interpreter_module",
                lambda _name, proxy=declared, **_options: proxy,
            )
            debug = make_debugger(name, source, stdin=stdin, seed=seed)
            for _ in range(1000):
                if debug.halted:
                    break
                debug.step()
            else:
                raise AssertionError(f"{name}: sample exceeded the source-step budget")
            assert debug.output == ""
            assert debug.observation.completion is None
            steps = debug.observation.steps
            assert "incidental_view" not in dict(debug.views)
            debug.step()
            result, snapshot = debug.observation, debug.snapshot()
            assert result == replace(native, steps=steps)
            debug.step()
            assert debug.observation == result
            assert debug.snapshot() == snapshot
            assert debug.run(limits=esolangs.ExecutionLimits(max_steps=0)) == "halted"
            assert debug.observation == result
            assert esolangs.run(name, source, stdin=stdin, seed=seed) == native
            control.setattr(
                module,
                language.runtime.completion_entrypoint,
                lambda *_args, **_options: HALTED_REPORT,
            )
            with pytest.raises(esolangs.InterpreterLimitError, match="declared policy"):
                esolangs.run(name, source, stdin=stdin, seed=seed)


def test_native_completion_sets_preserve_the_stepped_policy():
    from esolangs.runtime._capabilities import MachineCapabilities
    from esolangs.runtime._traits import traits

    for policy in Completion:
        fixed = MachineCapabilities(completion=policy)
        for kind in Completion:
            assert fixed.accepts_native(kind) == (kind is policy)
    dynamic = MachineCapabilities(
        native_completions=frozenset((Completion.HALTED, Completion.PERIODIC))
    )
    assert dynamic.accepts_native(Completion.HALTED)
    assert dynamic.accepts_native(Completion.PERIODIC)
    assert not dynamic.accepts_native(Completion.POST_HALT)
    assert dynamic.completion is Completion.HALTED
    assert traits(dynamic)["steppable_to_answer"]


@pytest.mark.medium
def test_declared_ordinary_factories_and_routes(monkeypatch):
    import base64

    from esolangs.runtime._lifecycle import POST_HALT_REPORT

    selected = {
        name: lang
        for name, lang in LANGUAGES.items()
        if lang.runtime.capabilities is not None
        and lang.runtime.capabilities.completion is Completion.HALTED
        and lang.runtime.capabilities.self_halts
    }
    assert selected
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import base64, json, sys
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES
from esolangs.vm import machine_traits, make_vm
samples = json.loads(sys.argv[1])
modules = {f'esolangs.languages.{LANGUAGES[name].id}.interpreter' for name in samples}
assert not modules.intersection(sys.modules)
for name in samples:
    traits = machine_traits(name)
    assert traits['self_halts'] and traits['steppable_to_answer']
    assert not traits['dumps_on_the_post_halt_step']
assert not modules.intersection(sys.modules)
for name, (source, stdin) in samples.items():
    if LANGUAGES[name].runtime.source_kind.value == 'raster':
        source = Raster.from_png(base64.b64decode(source))
    make_vm(name, source, stdin=stdin)
assert modules <= sys.modules.keys(), 'loading control did not fire'
""",
            json.dumps(
                {
                    name: (
                        base64.b64encode(SAMPLES[name][0].to_png()).decode("ascii")
                        if isinstance(SAMPLES[name][0], esolangs.Raster)
                        else SAMPLES[name][0],
                        SAMPLES[name][1],
                    )
                    for name in selected
                }
            ),
        ],
        check=True,
        timeout=10,
    )
    from concurrent.futures import ThreadPoolExecutor

    def isolated_result(name):
        source, stdin = SAMPLES[name]
        runtime = selected[name].runtime
        seed = runtime.reproducible_seed if runtime.random else None
        return esolangs.run(name, source, stdin=stdin, seed=seed, isolated=True)

    # Each disposable worker is independent; serial startup exceeded 18s at 104.
    with (
        guarded_worker(expected=len(selected)),
        ThreadPoolExecutor(max_workers=4) as workers,
    ):
        isolated = dict(
            zip(selected, workers.map(isolated_result, selected), strict=True)
        )
    for name, language in selected.items():
        caps = language.runtime.capabilities
        source, stdin = SAMPLES[name]
        seed = language.runtime.reproducible_seed if language.runtime.random else None
        native = esolangs.run(name, source, stdin=stdin, seed=seed)
        assert native.completion.kind is Completion.HALTED
        assert isolated[name] == native
        module = interpreter_module(name)
        with monkeypatch.context() as control:
            control.setattr(
                module._Machine, "completion", Completion.POST_HALT, raising=False
            )
            control.setattr(module._Machine, "ip_shape", "opaque", raising=False)
            control.setattr(
                module._Machine,
                "incidental_view",
                property(lambda _self: 99),
                raising=False,
            )
            control.setattr(
                module._Machine,
                "eof_is_a_value",
                not caps.eof_is_a_value,
                raising=False,
            )
            preparation = language.runtime.machine_preparation
            prepared = []

            actual_prepare = getattr(module, preparation)

            def bind(source, options, prepare=actual_prepare, saved=prepared):
                copied = dict(options)
                factory = prepare(source, copied)
                copied.clear()
                saved.append(factory)
                return factory

            declared = SimpleNamespace(**{preparation: bind})
            control.setattr(
                vm,
                "interpreter_module",
                lambda _name, proxy=declared, **_options: proxy,
            )
            make_debugger(name, source, stdin=stdin, seed=seed)
            from esolangs.runtime.io import ScriptedIO

            left = prepared[-1](ScriptedIO(stdin))
            right = prepared[-1](ScriptedIO(stdin))
            assert left is not right
            retained = right.snapshot()
            left.step()
            assert right.snapshot() == retained
            debug = make_debugger(name, source, stdin=stdin, seed=seed)
            assert debug.ip_shape == caps.debug.ip_shape
            assert debug.eof_is_a_value == caps.eof_is_a_value
            assert "incidental_view" not in dict(debug.views)
            assert (
                debug.run(limits=esolangs.ExecutionLimits(max_steps=1000)) == "halted"
            )
            result, snapshot = debug.observation, debug.snapshot()
            assert result == replace(native, steps=result.steps)
            debug.step()
            assert debug.observation == result
            assert debug.snapshot() == snapshot
            assert debug.run(limits=esolangs.ExecutionLimits(max_steps=0)) == "halted"
            assert debug.observation == result
            assert esolangs.run(name, source, stdin=stdin, seed=seed) == native
            control.setattr(
                module,
                language.runtime.completion_entrypoint,
                lambda *_args, **_options: POST_HALT_REPORT,
            )
            with pytest.raises(esolangs.InterpreterLimitError, match="declared policy"):
                esolangs.run(name, source, stdin=stdin, seed=seed)


def test_every_runtime_declares_preparation_and_capabilities():
    from dataclasses import replace

    from esolangs.registry._language import LanguageDeclaration
    from esolangs.runtime import _lifecycle
    from esolangs.runtime._definition import RuntimeSpec

    assert not hasattr(_lifecycle, "completion")
    with pytest.raises(TypeError, match="runtime"):
        LanguageDeclaration("undeclared")
    with pytest.raises(TypeError, match="required keyword-only"):
        RuntimeSpec("undeclared")
    for language in LANGUAGES.values():
        runtime = language.runtime
        source, _ = SAMPLES[language.name]
        assert esolangs.Language(language.name).prepare(source)._plan is not None
        assert runtime.machine_preparation
        assert runtime.completion_entrypoint
        assert runtime.capabilities is not None
        for obsolete in (
            "split",
            "path_like_source",
            "source_kind",
            "compressed_source",
            "source_loader",
            "file_newline",
        ):
            with pytest.raises(TypeError):
                replace(runtime, **{obsolete: True})
        with pytest.raises(ValueError, match="declared policy"):
            replace(runtime, source_policy="text")
        with pytest.raises(TypeError, match="capabilities must be declared"):
            replace(runtime, capabilities=None)
        with pytest.raises(TypeError, match="capabilities must be declared"):
            replace(language, runtime=replace(runtime, capabilities=object()))
        for field in ("machine_preparation", "completion_entrypoint"):
            with pytest.raises(ValueError, match="declared entry point"):
                replace(runtime, **{field: ""})
