"""The refactor trace diff: silent on an identical copy, loud on a mutant."""

import importlib
import os
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import esolangs
from esolangs.registry import INTERPRETERS, LANGUAGES
from esolangs.runtime._lifecycle import Completion
from tests.support.reference import REFERENCE
from tests.tooling.script_support import REPO_ROOT, load

tracediff = load(REPO_ROOT / "scripts" / "tracediff.py")
_SOURCE = REPO_ROOT / "src/esolangs/languages" / LANGUAGES[REFERENCE].id
_INTERPRETER = _SOURCE / "interpreter.py"
_RUNTIME = LANGUAGES[REFERENCE].runtime


def _runtime(policy=Completion.HALTED, *, random=False):
    return replace(
        _RUNTIME,
        random=random,
        capabilities=replace(_RUNTIME.capabilities, completion=policy),
    )


@pytest.mark.medium
@pytest.mark.usefixtures("retired_source_adapters")
def test_generated_corpora_retain_artifacts_without_the_facade():
    for name, language in LANGUAGES.items():
        if language.backend is None:
            continue
        programs = tracediff.corpus(name, 0, max_n=1)
        records = [
            code for code, _ in programs if isinstance(code, esolangs.ProgramArtifact)
        ]
        assert len(records) == 16, name
        assert all(record.language == name for record in records)


def test_random_corpus_reads_artifact_alphabets_and_numeric_tokens():
    raw = [("12 -7", "1\n"), ("<+>", "0\n")]
    records = [
        (esolangs.ProgramArtifact(code, REFERENCE), stdin) for code, stdin in raw
    ]
    random = tracediff._random_programs(records, 50)
    assert random == tracediff._random_programs(raw, 50)
    assert any(
        "-" in code and code.split()[0].lstrip("-").isdigit() for code, _ in random
    )
    assert any("<" in code or ">" in code for code, _ in random)


@pytest.mark.medium
def test_artifact_and_source_traces_match_for_split_grids():
    name = next(
        name
        for name, language in LANGUAGES.items()
        if language.runtime.split
        and language.runtime.capabilities is not None
        and language.runtime.capabilities.completion is Completion.POST_HALT
    )
    declaration = LANGUAGES[name].runtime
    module = importlib.import_module(INTERPRETERS[name])
    program, stdin = next(
        (code, stdin)
        for code, stdin in tracediff.corpus(name, 0, max_n=1)
        if isinstance(code, esolangs.ProgramArtifact)
    )
    options = {
        "runtime": declaration,
    }
    events = tracediff.trace(module, (program, stdin), frozenset(), **options)
    assert tracediff._halts(events)
    assert events == tracediff.trace(
        module, (program.source, stdin), frozenset(), **options
    )

    name = next(name for name, lang in LANGUAGES.items() if lang.runtime.dialect_schema)
    runtime = LANGUAGES[name].runtime
    key, values = next(iter(runtime.dialect_schema.choices.items()))
    choice = next(
        value for value in values if value != runtime.dialect_schema.defaults[key]
    )
    settings = esolangs.Language(name).settings(**{key: choice})
    record = esolangs.ProgramArtifact("source", name, settings=settings)
    runtime = replace(runtime, machine_preparation="bind_probe")
    capture = SimpleNamespace(
        bind_probe=lambda source, bound: lambda _io: (source, bound)
    )
    body, bound = tracediff._machine(
        capture, record, tracediff.ScriptedIO(), runtime=runtime
    )
    assert body == (record.source.splitlines() if runtime.split else record.source)
    assert bound == settings.options()


def test_a_copy_matches_and_a_mutant_is_caught(tmp_path: Path) -> None:
    programs = tracediff.corpus(REFERENCE, 200, max_n=1)
    same = tracediff._load(_INTERPRETER, "tracediff_same")
    new = tracediff._load(_INTERPRETER, "tracediff_new")
    assert tracediff.differences(same, new, programs, runtime=_runtime()) == []
    source = _INTERPRETER.read_text(encoding="utf-8")
    assert "(tape[ptr] + 1) % 256" in source
    broken = tmp_path / "mutant.py"
    broken.write_text(source.replace("(tape[ptr] + 1) % 256", "(tape[ptr] + 2) % 256"))
    mutant = tracediff._load(broken, "tracediff_mutant")
    assert tracediff.differences(same, mutant, programs, runtime=_runtime())

    # Independent NaNs compare by bits; altered values remain detectable.
    nan_source = _DRAWING.replace("return self.drawn", "return self.drawn, NAN")
    nan_source += '\nNAN = float("nan")\n'
    nan_path = tmp_path / "nan.py"
    nan_path.write_text(nan_source)
    before = tracediff._load(nan_path, "nan_before")
    after = tracediff._load(nan_path, "nan_after")
    assert (
        tracediff.differences(before, after, [("", "")], runtime=_runtime(random=True))
        == []
    )
    nan_path.write_text(nan_source.replace('NAN = float("nan")', "NAN = 0"))
    changed = tracediff._load(nan_path, "nan_changed")
    assert tracediff.differences(
        before, changed, [("", "")], runtime=_runtime(random=True)
    )
    assert tracediff._plain(float("nan"), {}) != tracediff._plain(-float("nan"), {})

    legacy = SimpleNamespace(__name__="legacy", _Machine=lambda *_: None)
    for invoke in (
        lambda: tracediff.trace(legacy, ("", ""), frozenset(), runtime=_runtime()),
        lambda: tracediff.differences(legacy, legacy, [("", "")], runtime=_runtime()),
        lambda: tracediff.speeds(legacy, same, [("", "")], runtime=_runtime()),
    ):
        with pytest.raises(TypeError, match="declared preparation"):
            invoke()


@pytest.mark.medium  # warmed/sized laps and two rounds take 1.06s alone
def test_speed_sees_a_slowed_copy(tmp_path: Path) -> None:
    """Deadfish's rewrite lost a third of its step rate and nothing said so."""
    programs = tracediff.corpus(REFERENCE, 50, max_n=1)
    same = tracediff._load(_INTERPRETER, "tracediff_fast")
    slowed = tmp_path / "slowed.py"
    slowed.write_text(
        _INTERPRETER.read_text(encoding="utf-8")
        + "\n_step = _Machine.step\n\n\ndef _slow(self):\n"
        + "    sum(range(2000))\n    _step(self)\n\n\n_Machine.step = _slow\n"
    )
    slow = tracediff._load(slowed, "tracediff_slow")
    before, after = tracediff.speeds(same, slow, programs, rounds=2, runtime=_runtime())
    assert after < before / 2


_DRAWING = """
from esolangs.runtime.randomness import draw


class _Machine:
    def __init__(self, code, io, stream):
        self.rng, self.halted, self.drawn = stream, False, ()

    def snapshot(self):
        return self.drawn

    def step(self):
        self.drawn += (draw(self.rng, 1 << 30),)
        self.halted = len(self.drawn) == 5


def prepare_machine(code, options):
    stream = options['rng']
    return lambda io: _Machine(code, io, stream)
"""


def test_a_machine_that_draws_traces_the_same_every_time(tmp_path: Path) -> None:
    """Unseeded, draws come from secrets: one %50 program traced 20 ways in 20."""
    path = tmp_path / "drawing.py"
    path.write_text(_DRAWING)
    module = tracediff._load(path, "tracediff_drawing")
    traces = {
        repr(
            tracediff.trace(
                module, ("", ""), frozenset(), runtime=_runtime(random=True)
            )
        )
        for _ in range(5)
    }
    assert len(traces) == 1
    events = tracediff.trace(
        module, ("", ""), frozenset(), runtime=_runtime(random=True)
    )
    assert tracediff._halts(events)
    assert len(events) == 6
    assert len(events[-1][1]) == 5


def test_an_error_records_the_state_it_leaves() -> None:
    """A draft moving its pointer before a failing read passed an error-only diff."""
    module = tracediff._load(_INTERPRETER, "tracediff_error")
    *_, last = tracediff.trace(module, ("+,", ""), frozenset(), runtime=_runtime())
    assert last[:2] == ("error", "InputExhaustedError")
    assert last[-1][:2] == (1, 0)  # still on the ``,``, pointer unmoved


def test_views_include_inherited_properties_and_respect_overrides():
    class Parent:
        @property
        def ip(self):
            return 3

    class Child(Parent):
        pass

    class Mutant(Parent):
        @property
        def ip(self):
            return 4

    class Hidden(Parent):
        ip = 5

    assert tracediff._views(Child(), frozenset()) == (("ip", "3"),)
    assert tracediff._views(Mutant(), frozenset()) == (("ip", "4"),)
    assert tracediff._views(Child(), frozenset({"ip"})) == ()
    assert tracediff._views(Hidden(), frozenset()) == ()


_POST_HALT = """
class _Machine:
    def __init__(self, code, io):
        self.io = io
        self.halted = False
        self.printed = False
        self.finalized = 0

    def step(self):
        if self.halted and not self.printed:
            self.io.print_str("done")
            self.printed = True
            self.finalized += 1
        else:
            self.halted = True

    def snapshot(self):
        return self.halted, self.printed, self.finalized


def prepare_machine(code, options):
    return lambda io: _Machine(code, io)
"""


def test_declared_completion_finalizes_and_keeps_the_final_state(tmp_path):
    path = tmp_path / "post_halt.py"
    path.write_text(_POST_HALT)
    timestamp = path.stat().st_mtime_ns
    explicit = tracediff._load(path, "declared_completion")
    program = ("", "")
    events = tracediff.trace(
        explicit, program, frozenset(), runtime=_runtime(Completion.POST_HALT)
    )
    assert events[-1] == ("dumped", (), (True, True, 1), "done")
    assert tracediff._halts(events)
    with pytest.raises(TypeError, match="Completion policy"):
        tracediff.trace(explicit, program, frozenset(), runtime=_runtime("post_halt"))
    path.write_text(_POST_HALT.replace("self.finalized += 1", "self.finalized += 2"))
    os.utime(path, ns=(timestamp, timestamp))
    mutant = tracediff._load(path, "bad_final_state")
    assert tracediff.differences(
        explicit, mutant, [program], runtime=_runtime(Completion.POST_HALT)
    )
    for flag in ('completion = "invalid"', "dumps_on_the_post_halt_step = True"):
        path.write_text(
            _POST_HALT.replace("class _Machine:", "class _Machine:\n    " + flag)
        )
        flagged = tracediff._load(path, "ignored_legacy_flag")
        assert (
            tracediff.differences(explicit, flagged, [program], runtime=_runtime())
            == []
        )
        assert (
            tracediff.trace(flagged, program, frozenset(), runtime=_runtime())[-1][-1]
            == ""
        )


def test_cli_uses_declared_post_halt_policy_for_mutant_controls(
    tmp_path, monkeypatch, capsys
):
    name = next(
        name
        for name, lang in LANGUAGES.items()
        if lang.backend is not None
        and lang.runtime.capabilities is not None
        and lang.runtime.capabilities.completion is Completion.POST_HALT
        and lang.contract.answer_mode != "termination"
    )
    module = importlib.import_module(INTERPRETERS[name])
    monkeypatch.delattr(module._Machine, "completion", raising=False)
    source = Path(module.__file__).read_text()
    path = tmp_path / "missing_dump.py"
    path.write_text(
        source + "\n_original_step = _Machine.step\n"
        "def _missing_dump(self):\n"
        "    if not self.halted: _original_step(self)\n"
        "_Machine.step = _missing_dump\n"
    )
    corpus = tracediff.corpus(name, 0, max_n=1)
    monkeypatch.setattr(tracediff, "corpus", lambda *_: corpus)
    assert tracediff.main([name, "--random", "0", "--mutant", str(path)]) == 0
    output = capsys.readouterr().out
    assert "0 differ from main" in output
    control = next(line for line in output.splitlines() if line.startswith("control:"))
    assert int(control.rsplit(" ", 1)[-1]) > 0


def test_speed_does_not_reward_an_inherited_warm_cache(tmp_path, monkeypatch):
    source = tmp_path / "cached.py"
    source.write_text(
        """
from functools import lru_cache

_clock = None

@lru_cache(maxsize=8)
def _compiled(code):
    _clock.elapsed += 1
    return code

class _Machine:
    def __init__(self, code, io):
        _compiled(code)
        self.halted = False

    def snapshot(self):
        return self.halted

    def step(self):
        _clock.elapsed += 0.01
        self.halted = True


def prepare_machine(code, options):
    return lambda io: _Machine(code, io)
"""
    )
    before = tracediff._load(source, "cached_before")
    after = tracediff._load(source, "cached_after")
    clock = SimpleNamespace(elapsed=0.0)
    before._clock = after._clock = clock
    monkeypatch.setattr(
        tracediff, "time", SimpleNamespace(perf_counter=lambda: clock.elapsed)
    )
    programs = [(str(i), "") for i in range(16)]
    for code, _stdin in programs[:8]:
        before._compiled(code)
    old_rate, new_rate = tracediff.speeds(
        before, after, programs, rounds=2, runtime=_runtime()
    )
    assert new_rate == pytest.approx(old_rate)
