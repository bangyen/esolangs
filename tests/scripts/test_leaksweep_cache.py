"""The leak sweep's cache must forget a language whose interpreter changed.

The cache key is a hash of the files a sweep reads.  A path that does not
exist would hash as nothing, and a sweep would then be remembered as clean
for an interpreter it never read -- which is how the first cut of the key
built the interpreter path one directory too high and skipped every one.
"""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "verify_no_exception_leaks.py"


def load_script() -> object:
    """Import the sweep as a module (it prepends ``scripts/`` for ``_scope``)."""
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("verify_no_exception_leaks", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_hashed_source_exists() -> None:
    """Every path the key reads is a real file, for every registered interpreter."""
    from esolangs.registry import RUNNERS

    sweep = load_script()
    for name, (module, _) in RUNNERS.items():
        for path in sweep._sources(module):  # type: ignore[attr-defined]  # noqa: SLF001
            assert path.is_file(), (name, path)


def test_the_key_reads_the_interpreter_and_the_examples() -> None:
    """Two interpreters differ only in their module file; two corpora in text."""
    from esolangs.registry import RUNNERS

    sweep = load_script()
    fingerprint = sweep._fingerprint  # type: ignore[attr-defined]  # noqa: SLF001
    bf, brainif = RUNNERS["brainfuck"][0], RUNNERS["BrainIf"][0]
    assert fingerprint(bf, ["+"]) != fingerprint(brainif, ["+"])
    assert fingerprint(bf, ["+"]) != fingerprint(bf, ["-"])
    assert fingerprint(bf, ["+"]) == fingerprint(bf, ["+"])


def test_the_sweep_loads_the_packaged_examples() -> None:
    """The old ``examples/boolean`` path disappeared with the package move."""
    sweep = load_script()
    examples = sweep._examples_by_slug()  # type: ignore[attr-defined]  # noqa: SLF001
    assert "brainfuck" in examples
    assert examples["brainfuck"]


def test_factor_corpus_caps_the_total_operand_not_each_line() -> None:
    """Factor concatenates every digit before factoring the resulting integer."""
    sweep = load_script()
    capped = sweep._cap_numeric_runs("1234567890\n1234567890")  # type: ignore[attr-defined]  # noqa: SLF001
    assert capped == "1234567890\n12"


def test_every_language_resolves_its_example() -> None:
    """The sweep's corpus reaches every language's shipped example program.

    Example filenames are dash-separated display names (``a-painter-ant``)
    while every lookup in the sweep is the underscored slug
    (``a_painter_ant``).  Keying the map on the filename stem therefore
    matched neither, and sixteen of the sixty-two languages were swept on
    generic fragments alone -- no example, and none of the mutations of one,
    which the module docstring calls the half that finds the interesting
    cases.  It reported the shortfall as "languages without example
    programs: 16" and passed anyway.

    ``test_the_sweep_loads_the_packaged_examples`` above did not catch it:
    it asks about brainfuck, one of the languages whose stem and slug are
    the same string.
    """
    from esolangs.registry import RUNNERS, canonical_id

    module = load_script()
    by_slug = module._examples_by_slug()  # type: ignore[attr-defined]  # noqa: SLF001
    missing = sorted(name for name in RUNNERS if not by_slug.get(canonical_id(name)))
    assert missing == []


def test_the_lookup_is_keyed_the_way_the_sweep_reads_it() -> None:
    """The positive control: a dash-stemmed key would not be found.

    Every language resolving is the expected result, so the assertion above
    proves nothing unless a wrong key can be seen to fail.
    """
    module = load_script()
    by_slug = module._examples_by_slug()  # type: ignore[attr-defined]  # noqa: SLF001
    assert "a_painter_ant" in by_slug
    assert "a-painter-ant" not in by_slug
