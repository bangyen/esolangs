"""Round-trip verification for Line's ``extract`` against the wiki's own images.

``extract()`` raises ``ValueError`` when its coverage check fails (see its
docstring and ``coverage_gap``'s). This script reports that result for every
fixture, so ``render.py`` and ``extract.py`` regressions produce a nonzero exit.
"""

import sys
from pathlib import Path

from esolangs.interpreters.tape_based.line.extract import extract

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "line"


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
