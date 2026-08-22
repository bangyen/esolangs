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
  `_OPS`'s per-opcode geometry was re-measured pixel-by-pixel against every
  relevant wiki reference image (`Lineanim4/5/6/7/8/10/11.png`) rather than
  assumed: `>`/`<`/`i`/`o` each have their own distinct kink shape (a
  previous version of `_OPS` gave `>`/`i` and `<`/`o` identical geometry,
  which was simply wrong), and `+`/`-` are the only opcodes whose
  consecutive repeats merge into one stretched diagonal rather than drawing
  separately (confirmed against `Lineanim6.png`'s `+++`).
- **Extraction**: 8-direction pixel walking plus region-adjacency flood-fill
  recovers the path/branch structure of both wiki reference images with
  near-complete pixel accounting (verified via `verify.py`'s XOR round-trip,
  now also run automatically inside `extract()` itself).
- **Opcode classification**: `extract.py`'s `classify_ops` identifies which
  instruction produced each kink in a walked path, matching
  `(relative_turn, unit_length)`-run signatures against a *dynamic* heading
  that updates at ordinary corners rather than staying fixed at the path's
  own start (needed for branch arms, whose first real opcode is often
  preceded by a corner turn that isn't itself part of any kink -- e.g. a
  T-branch arm that turns again onto a new heading before its first
  opcode).  `+`/`-` recover their repeat count from the merged diagonal's
  unit length (`Lineanim6.png`'s `+++` confirms the rule).  Verified two
  ways:
  - Every opcode individually, several mixed/repeated-opcode sequences, and
    back-to-back repeats of the same non-mergeable opcode, all through
    `render.py`'s own generated images (exact round-trip match).
  - Against the wiki's own hand-drawn `addition.png`/`multiplication.png`
    fixtures, with several individual branch arms hand-decoded by a human
    reading the actual drawing and compared pixel-for-pixel against
    `classify_ops`'s output -- exact match once two real bugs this
    cross-check surfaced were fixed: `_OPS["o"]`'s middle diagonal leg was
    1 unit short (measured against `Lineanim11.png` in isolation, where the
    arrowhead obscures its true length), and a walked path that gets cut
    short entering a merge into another, unrelated stroke (confirmed by
    hand against two different `multiplication.png` branch arms) was
    misread as ending with one extra spurious `+`/`-` call -- now dropped
    via a check that a real opcode's kink is never the walked path's
    literal last run with nothing following it.
  - Not yet re-verified: whether `_UNIT_TOLERANCE`'s rounding tolerance and
    the noise-run-skipping logic hold up against a *third* fixture/program
    beyond these two, or against non-`render.py` hand-drawn input at a
    substantially different scale than the wiki's own ~20px unit.
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

- Pre-existing (not introduced by the opcode-classification or `_OPS`
  geometry work): a program with a conditional turn (`?`) followed by
  further opcodes in either branch fails `extract()`'s coverage check
  (confirmed on `main` before any of these changes, so it's a `render.py`
  branch-layout or `_walk_tree` issue, not a `classify_ops` one) -- e.g.
  `Node("?", zero=chain("+","+"), nonzero=chain("-",">"))` renders but
  doesn't round-trip. Not investigated further here since it's orthogonal
  to opcode classification, which only needed *some* branch-free rendered
  path to verify against.
- Newly understood (via hand-decoding real fixture arms while verifying
  `classify_ops`), not yet acted on anywhere except that one `classify_ops`
  check: the wiki's own drawings use a "cursor merges into another line"
  convention (matching Lineanim3.4/11.1/11.2's documented rule) where two
  independently-drawn strokes can physically touch with no separating
  background at all -- confirmed on two `multiplication.png` branch arms,
  each ending at a plain corner turn that walks straight onto a different
  stroke's ink rather than a real halt. `_walk`/`_walk_tree`'s own branch-vs-
  corner logic (`_is_branch_pivot`) doesn't detect this as anything special
  -- the walker just keeps walking onto the other stroke's line, since
  there is no region-adjacency signal marking a merge apart from an
  ordinary corner *at the pixel the walker arrives at* (the merge only
  becomes a junction one step later, after a forced turn with no
  straight-ahead ink).  `classify_ops` works around this at its own layer
  (dropping a trailing call that turns out to be the path's literal last
  run), but `_walk_tree` itself still doesn't know it crossed into
  unrelated ink -- e.g. `flatten()`'s returned path still includes those
  extra pixels, and nothing stops a future caller from walking *further*
  along the merged-into stroke by mistake if `_walk`'s greedy continuation
  ever had a reason to keep going past where these fixtures happened to
  stop.
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
