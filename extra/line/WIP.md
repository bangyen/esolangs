# Line: settled vs. still open

`render.py`, `extract.py`, and `verify.py` implement a program renderer and
a pixel-based extractor for [Line](https://esolangs.org/wiki/Line), an
esolang whose spec is entirely a set of hand-drawn curve images with no
text format and no reference implementation (tagged `Unimplemented` on the
wiki). This file tracks what's settled and tested vs. what's deliberately
out of scope or unverified, the way `docs/streetcode-wip.md` does for
Streetcode -- the module docstrings in `extract.py`/`render.py` carry the
settled, load-bearing reasoning; this file is for what isn't decided yet.

## Settled and tested

- **Rendering**: opcode sequences lay out correctly as images matching the
  wiki's own visual style, including the conditional-turn's T-branch.
- **Extraction**: 8-direction pixel walking plus region-adjacency flood-fill
  recovers the path/branch structure of both wiki reference images with
  near-complete pixel accounting (verified via `verify.py`'s XOR round-trip,
  now also run automatically inside `extract()` itself).
- **Robustness, each confirmed against real or adversarial synthetic
  input, not just reasoned about**:
  - JPEG recompression: bit-identical results down to quality 34; a sharp
    cliff at quality 32 and below (block quantization erases pixels
    directly out of a 1px stroke) is now caught by `extract()`'s coverage
    check rather than failing silently.
  - Cursor misidentification: `find_cursor` rejects a winning candidate
    that isn't arrowhead-shaped (fill-ratio bracket), confirmed against a
    solid-square false positive. Does *not* resolve genuine ambiguity
    between two equally arrowhead-shaped candidates -- still picks the
    larger by design.
  - Huge blank borders: `crop_to_content`'s quadtree search stays fast
    independent of canvas size (confirmed ~9x faster than a plain
    `np.nonzero` scan on a sparse ~4600x4600 canvas).
  - Oversized/upscaled drawings: `normalize_scale` detects and corrects
    for a drawing rendered at 2x-4x its native 1px stroke width (confirmed
    on both fixtures at each scale) -- the pipeline fails outright without
    this, since the same "3+ neighbors means arrowhead" rule that isolates
    the cursor at native scale also matches ordinary multi-pixel-wide
    stroke pixels.

## Deliberately out of scope

- **Opcode classification**: `extract.py` recovers *where* the path goes
  and *where* it branches, but never identifies *which* instruction
  (`+`/`-`/`<`/`>`/input/output) produced a given kink. A run-length /
  direction-run template-matching approach was prototyped early on
  (angle signatures measured directly from the wiki's reference images)
  and looked promising, but was never wired into `extract.py`.
- **Runtime simulation**: even with opcodes classified, nothing executes
  a program. `extract_tree` does a one-time structural trace; a real
  interpreter would need to walk the same drawn graph repeatedly, since a
  loop revisits the same branch pixel many times, taking a different arm
  each time depending on tape state -- a different problem from what's
  built here.
- **Not wired into the interpreter registry**: deliberate, per an earlier
  discussion -- Line has no text format, so it doesn't fit the
  `run(code, io)` convention every other language in `src/esolangs/` uses.
  Stays a standalone `extra/` tool.

## Unverified / lower priority

- Real (camera/scan) photographs with genuine anti-aliasing, as opposed to
  the clean nearest-neighbor-scaled synthetic input `normalize_scale` was
  tested against. Anti-aliased edges could make the exact-integer scale
  detection (`round(ink/skeleton_length)`) land less cleanly.
- The compression-cliff and oversized-scale failure modes were tested
  independently; a large *and* heavily compressed image (both problems
  compounding) hasn't been tried.
- Dependency footprint: 4 undeclared deps (Pillow, numpy, scipy,
  scikit-image), informal by design matching how `extra/` keeps other
  subtrees' toolchains out of `pyproject.toml`. A ranked, tested plan for
  which would be easiest to replace with hand-rolled numpy is recorded as
  a comment block in `extract.py` just above the imports, if this is ever
  worth revisiting.
