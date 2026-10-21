"""The refactor trace diff: silent on an identical copy, loud on a mutant."""

from pathlib import Path

from esolangs.registry import INTERPRETERS, LANGUAGES
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
    same = tracediff._load(_INTERPRETER, "tracediff_same")  # noqa: SLF001
    new = tracediff._load(_INTERPRETER, "tracediff_new")  # noqa: SLF001
    assert tracediff.differences(same, new, programs) == []
    source = _INTERPRETER.read_text(encoding="utf-8")
    assert "(tape[ptr] + 1) % 256" in source
    broken = tmp_path / "mutant.py"
    broken.write_text(source.replace("(tape[ptr] + 1) % 256", "(tape[ptr] + 2) % 256"))
    mutant = tracediff._load(broken, "tracediff_mutant")  # noqa: SLF001
    assert tracediff.differences(same, mutant, programs)


def test_speed_sees_a_slowed_copy(tmp_path: Path) -> None:
    """Deadfish's rewrite lost a third of its step rate and nothing said so."""
    programs = tracediff.corpus(REFERENCE, 50, max_n=1)
    same = tracediff._load(_INTERPRETER, "tracediff_fast")  # noqa: SLF001
    slowed = tmp_path / "slowed.py"
    slowed.write_text(
        _INTERPRETER.read_text(encoding="utf-8")
        + "\n_step = _Machine.step\n\n\ndef _slow(self):\n"
        + "    sum(range(2000))\n    _step(self)\n\n\n_Machine.step = _slow\n"
    )
    slow = tracediff._load(slowed, "tracediff_slow")  # noqa: SLF001
    before, after = tracediff.speeds(same, slow, programs, rounds=2)
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
    module = tracediff._load(path, "tracediff_drawing")  # noqa: SLF001
    traces = {repr(tracediff.trace(module, ("", ""), frozenset())) for _ in range(5)}
    assert len(traces) == 1


def test_an_error_records_the_state_it_leaves() -> None:
    """A draft moving its pointer before a failing read passed an error-only diff."""
    module = tracediff._load(_INTERPRETER, "tracediff_error")  # noqa: SLF001
    *_, last = tracediff.trace(module, ("+,", ""), frozenset())
    assert last[:2] == ("error", "InputExhaustedError")
    assert last[-1][:2] == (1, 0)  # still on the ``,``, pointer unmoved
