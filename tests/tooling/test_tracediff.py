"""The refactor trace diff: silent on an identical copy, loud on a mutant."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from esolangs.registry import INTERPRETERS, LANGUAGES
from esolangs.runtime._lifecycle import Completion
from tests.support.reference import REFERENCE
from tests.tooling.script_support import REPO_ROOT, load

tracediff = load(REPO_ROOT / "scripts" / "tracediff.py")
_SOURCE = REPO_ROOT / "src/esolangs/languages" / LANGUAGES[REFERENCE].id
_INTERPRETER = _SOURCE / "interpreter.py"


def test_the_reference_is_a_single_file_interpreter() -> None:
    assert INTERPRETERS[REFERENCE].endswith(".interpreter")
    assert _INTERPRETER.is_file()


def test_a_copy_matches_and_a_mutant_is_caught(tmp_path: Path) -> None:
    programs = tracediff.corpus(REFERENCE, 200, max_n=1)
    same = tracediff._load(_INTERPRETER, "tracediff_same")
    new = tracediff._load(_INTERPRETER, "tracediff_new")
    assert tracediff.differences(same, new, programs, policy=Completion.HALTED) == []
    source = _INTERPRETER.read_text(encoding="utf-8")
    assert "(tape[ptr] + 1) % 256" in source
    broken = tmp_path / "mutant.py"
    broken.write_text(source.replace("(tape[ptr] + 1) % 256", "(tape[ptr] + 2) % 256"))
    mutant = tracediff._load(broken, "tracediff_mutant")
    assert tracediff.differences(same, mutant, programs, policy=Completion.HALTED)

    # Independent NaNs compare by bits; altered values remain detectable.
    nan_source = _DRAWING.replace("return self.drawn", "return self.drawn, NAN")
    nan_source += '\nNAN = float("nan")\n'
    nan_path = tmp_path / "nan.py"
    nan_path.write_text(nan_source)
    before = tracediff._load(nan_path, "nan_before")
    after = tracediff._load(nan_path, "nan_after")
    assert (
        tracediff.differences(before, after, [("", "")], policy=Completion.HALTED) == []
    )
    nan_path.write_text(nan_source.replace('NAN = float("nan")', "NAN = 0"))
    changed = tracediff._load(nan_path, "nan_changed")
    assert tracediff.differences(before, changed, [("", "")], policy=Completion.HALTED)
    assert tracediff._plain(float("nan"), {}) != tracediff._plain(-float("nan"), {})


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
    before, after = tracediff.speeds(
        same, slow, programs, rounds=2, policy=Completion.HALTED
    )
    assert after < before / 2


_DRAWING = """
from esolangs.runtime.randomness import draw


class _Machine:
    def __init__(self, code, io, rng=None):
        self.rng, self.halted, self.drawn = rng, False, ()

    def snapshot(self):
        return self.drawn

    def step(self):
        self.drawn += (draw(self.rng, 1 << 30),)
        self.halted = len(self.drawn) == 5
"""


def test_a_machine_that_draws_traces_the_same_every_time(tmp_path: Path) -> None:
    """Unseeded, draws come from secrets: one %50 program traced 20 ways in 20."""
    path = tmp_path / "drawing.py"
    path.write_text(_DRAWING)
    module = tracediff._load(path, "tracediff_drawing")
    traces = {
        repr(tracediff.trace(module, ("", ""), frozenset(), policy=Completion.HALTED))
        for _ in range(5)
    }
    assert len(traces) == 1


def test_an_error_records_the_state_it_leaves() -> None:
    """A draft moving its pointer before a failing read passed an error-only diff."""
    module = tracediff._load(_INTERPRETER, "tracediff_error")
    *_, last = tracediff.trace(
        module, ("+,", ""), frozenset(), policy=Completion.HALTED
    )
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
"""


def test_declared_completion_finalizes_and_keeps_the_final_state(tmp_path):
    path = tmp_path / "post_halt.py"
    path.write_text(_POST_HALT)
    timestamp = path.stat().st_mtime_ns
    explicit = tracediff._load(path, "declared_completion")
    program = ("", "")
    events = tracediff.trace(
        explicit, program, frozenset(), policy=Completion.POST_HALT
    )
    assert events[-1] == ("dumped", (), (True, True, 1), "done")
    assert tracediff._halts(events)
    with pytest.raises(TypeError, match="Completion policy"):
        tracediff.trace(explicit, program, frozenset(), policy="post_halt")
    path.write_text(_POST_HALT.replace("self.finalized += 1", "self.finalized += 2"))
    os.utime(path, ns=(timestamp, timestamp))
    mutant = tracediff._load(path, "bad_final_state")
    assert tracediff.differences(
        explicit, mutant, [program], policy=Completion.POST_HALT
    )
    for flag in ('completion = "invalid"', "dumps_on_the_post_halt_step = True"):
        path.write_text(
            _POST_HALT.replace("class _Machine:", "class _Machine:\n    " + flag)
        )
        flagged = tracediff._load(path, "ignored_legacy_flag")
        assert (
            tracediff.differences(
                explicit, flagged, [program], policy=Completion.HALTED
            )
            == []
        )
        assert (
            tracediff.trace(flagged, program, frozenset(), policy=Completion.HALTED)[
                -1
            ][-1]
            == ""
        )


def test_cli_uses_declared_post_halt_policy_for_mutant_controls(
    tmp_path, monkeypatch, capsys
):
    import importlib

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
        before, after, programs, rounds=2, policy=Completion.HALTED
    )
    assert new_rate == pytest.approx(old_rate)
