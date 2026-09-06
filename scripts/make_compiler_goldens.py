"""Regenerate the pinned compiler output in ``tests/fixtures/compiler_goldens``.

``tests/compilers/test_assembly_compilers.py`` pins what every RISC-V
backend emits for its sample program, because the assertion it replaced --
that the output contained ``.global _start`` and did not echo its source --
passed for nearly any wrong compiler.  A mutation run measured 71% of
``myscript``'s mutants surviving it, and a ``jaune`` mutant emitting
assembly of the same length and different content passed the whole suite.

Pinning output means a deliberate codegen change fails those tests by
design.  That is the point: the diff is the review.  This script is how the
pin is moved once the change is intended.

Two forms, because three backends are too large for the first.  Under
``_TEXT_LIMIT`` characters a golden is written as readable assembly *and*
covered by a digest; above it, only the digest is kept -- ``addsubjump``,
``decleq`` and ``sbleq`` each emit ~276KB for their sample program, which is
neither reviewable in a diff nor worth committing.  Every backend appears in
``checksums.json`` either way, and a test derived from the registry fails if
one is ever missing.

The sample programs are read from the test module rather than duplicated
here, so the goldens cannot be regenerated against inputs the suite does not
use.

Usage:
    python scripts/make_compiler_goldens.py
    python scripts/make_compiler_goldens.py --check   # exit 1 if stale
"""

import argparse
import hashlib
import importlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Above this many characters the golden stops being reviewable in a diff and
# starts being a quarter-megabyte of committed machine output, so only its
# digest is kept.  Three of the sixteen backends are over it.
_TEXT_LIMIT = 20000

_GOLDENS = ROOT / "tests" / "fixtures" / "compiler_goldens"
_TEST_MODULE = ROOT / "tests" / "compilers" / "test_assembly_compilers.py"


def _programs() -> dict[str, str]:
    """Return the sample program per compiler, read from the test module.

    Imported rather than copied: a golden regenerated against a different
    input than the suite compiles would pin something no test checks, and
    the mismatch would not surface until someone read both files.
    """
    spec = importlib.util.spec_from_file_location("_tac", _TEST_MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(module._PROGRAMS)  # noqa: SLF001


def _emit(module: str, program: str) -> str:
    """Return what one compiler emits for its sample program."""
    comp = importlib.import_module(f"esolangs.compilers.{module}").comp
    return str(comp(program))


def main() -> int:
    """Write the goldens, or report that they are stale."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit nonzero if any golden is out of date",
    )
    args = parser.parse_args()

    outputs = {
        module: _emit(module, program)
        for module, program in sorted(_programs().items())
    }
    checksums = {
        module: {
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "chars": len(text),
        }
        for module, text in outputs.items()
    }

    if args.check:
        with open(_GOLDENS / "checksums.json") as handle:
            stale = [m for m, v in json.load(handle).items() if checksums.get(m) != v]
        for module in sorted(stale):
            print(f"{module}: golden is out of date")
        if stale:
            print("\nrun scripts/make_compiler_goldens.py to update them")
        return 1 if stale else 0

    _GOLDENS.mkdir(parents=True, exist_ok=True)
    # Clear first, so a backend that is renamed or deleted does not leave its
    # golden behind to be compared against nothing.
    for previous in _GOLDENS.glob("*.s"):
        previous.unlink()

    for module, text in outputs.items():
        if len(text) <= _TEXT_LIMIT:
            (_GOLDENS / f"{module}.s").write_text(text)
        kept = "text + digest" if len(text) <= _TEXT_LIMIT else "digest only"
        print(f"{module}: {len(text)} chars ({kept})")

    with open(_GOLDENS / "checksums.json", "w") as handle:
        json.dump(checksums, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
