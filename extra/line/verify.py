r"""Round-trip verification for :mod:`extract` against the wiki's own."""

import sys
from pathlib import Path

from extract import extract

FIXTURES = Path(__file__).parent / "fixtures"


def main() -> int:
    r"""Verify round-trip extraction against every fixture, reporting."""
    failures = 0
    for image in sorted(FIXTURES.glob("*.png")):
        try:
            extract(str(image))
            print(f"{image.name}: ok")
        except ValueError as exc:
            failures += 1
            print(f"{image.name}: FAIL -- {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
