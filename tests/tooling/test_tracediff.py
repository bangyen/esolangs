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
    assert "(acc + 1) % 256" in source
    broken = tmp_path / "mutant.py"
    broken.write_text(source.replace("(acc + 1) % 256", "(acc + 2) % 256"))
    mutant = tracediff._load(broken, "tracediff_mutant")  # noqa: SLF001
    assert tracediff.differences(same, mutant, programs)


def test_an_error_records_the_state_it_leaves() -> None:
    """A draft moving its pointer before a failing read passed an error-only diff."""
    module = tracediff._load(_INTERPRETER, "tracediff_error")  # noqa: SLF001
    *_, last = tracediff.trace(module, ("+,", ""), frozenset())
    assert last[:2] == ("error", "InputExhaustedError")
    assert last[-1][:2] == (1, 0)  # still on the ``,``, pointer unmoved
