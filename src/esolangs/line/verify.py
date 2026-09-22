"""Round-trip verification for :mod:`extract` against the wiki's own images.

``extract()`` itself now runs a coverage check before returning (see its
docstring, and ``coverage_gap``'s, for what counts as an acceptable gap vs.
a real extraction failure) and raises ``ValueError`` when it fails.  This
script just calls it over every fixture and reports pass/fail, so
regressions in either ``render.py`` or ``extract.py`` show up as a nonzero
exit code without needing to reach for a debugger or a one-off script.

Usage:
    python -m esolangs.line.verify
"""

import sys
from pathlib import Path

from .extract import extract

# The old ``__file__.parent / "fixtures"`` did not exist.
FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "line"


def main(fixtures: Path = FIXTURES) -> int:
    """Verify round-trip extraction against every fixture, reporting failures."""
    images = sorted(fixtures.glob("*.png"))
    if not images:
        # A positive control: an empty sweep is not a pass.
        print(f"no fixtures under {fixtures}", file=sys.stderr)
        return 1
    failures = 0
    for image in images:
        try:
            extract(str(image))
            print(f"{image.name}: ok")
        except ValueError as exc:
            failures += 1
            print(f"{image.name}: FAIL -- {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
