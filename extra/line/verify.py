"""Round-trip verification for :mod:`extract` against the wiki's own images.

For each reference image, extraction produces a candidate path tree
(``extract.extract_tree``); this redraws that tree's pixels onto a blank
canvas the same size as the source and XORs it against the source image
(cursor blob removed, since extraction does not attempt to reproduce it).
A perfect extraction XORs to all zero; any nonzero pixel is either a real
extraction bug or one of the few pixels extraction deliberately never
walks (a branch's own pivot vertex, spent as the fork point rather than
being part of either arm -- see ``extract.py``'s module docstring) or a
cosmetic gap where the cursor-blob isolation is a pixel or two short of
the arrowhead's true silhouette.  ``_KNOWN_GAP`` bounds how many such
pixels are acceptable per image so a real regression (many mismatched
pixels, or ones outside this small margin) still fails loudly.

Usage:
    python extra/line/verify.py
"""

import sys
from pathlib import Path

import numpy as np
from extract import extract_tree, find_cursor, flatten, load_binary

FIXTURES = Path(__file__).parent / "fixtures"

# Both reference images have exactly 3 known-gap pixels: one branch pivot,
# plus (for the multiplication example, which has three branches) two more
# pivots, and 2 arrowhead-tip corners just outside the cursor-blob growth
# threshold (see extract.py's find_cursor docstring).  5 covers both with
# margin without hiding a real multi-pixel extraction failure.
_KNOWN_GAP = 5


def _redraw(paths: list[list[tuple[int, int]]], shape: tuple[int, int]) -> np.ndarray:
    """Draw walked pixel paths onto a blank boolean canvas of ``shape``."""
    canvas = np.zeros(shape, dtype=bool)
    for path in paths:
        for y, x in path:
            canvas[y, x] = True
    return canvas


def verify_roundtrip(path: Path) -> tuple[bool, int, int]:
    """Extract ``path``, redraw it, and XOR against the source.

    Returns ``(ok, mismatch_count, reference_ink_count)``.
    """
    mask = load_binary(str(path))
    cursor = find_cursor(mask)
    result = extract_tree(mask, cursor)
    paths = flatten(result)

    redrawn = _redraw(paths, mask.shape)
    reference = mask & ~cursor.blob
    mismatch = int((redrawn ^ reference).sum())
    return mismatch <= _KNOWN_GAP, mismatch, int(reference.sum())


def main() -> int:
    """Verify round-trip extraction against every fixture, reporting failures."""
    failures = 0
    for image in sorted(FIXTURES.glob("*.png")):
        ok, mismatch, total = verify_roundtrip(image)
        failures += not ok
        status = "ok" if ok else "FAIL"
        print(f"{image.name}: {status} -- {mismatch}/{total} mismatched px")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
