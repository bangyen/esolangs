"""The leak sweep's cache must forget a language whose interpreter changed.

The cache key is a hash of the files a sweep reads.  A path that does not
exist would hash as nothing, and a sweep would then be remembered as clean
for an interpreter it never read -- which is how the first cut of the key
built the interpreter path one directory too high and skipped all 65.
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
