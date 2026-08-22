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

  **A `_walk_tree`-level fix was attempted and reverted three times** --
  recorded here in detail so a future attempt doesn't re-derive or re-break
  the same things:
  - The confirmed merge pixel is `(194, 228)` in
    `fixtures/multiplication.png`'s normalized mask (the `root.nonzero.nonzero`
    arm), hand-decoded end to end as: branch right onto E, immediate corner
    onto N, then `>`, `+`, `>`, `+`, `<`, `<`, `-`, then this merge point,
    where the stroke's own NW diagonal run ends one step before a pixel
    where a *different*, already-drawn stroke (the outer branch's own
    horizontal bar, itself travelling W) is the only ink physically
    touching -- confirmed by a human reading the actual drawing, not
    inferred from pixel data alone.
  - `region_map.junctions` (the existing region-adjacency check
    `_is_branch_pivot` already uses) does mark `(194, 228)` as a junction,
    but the *next* pixel toward "true tip" behavior never resolves the way
    it does for a real T-junction, because the true 3-way meeting pixel,
    `(193, 228)`, sits exactly on the transition between two *differently*-
    labeled junction segments (`(2, 4)` on one side, `(1, 2)` on the other)
    -- `build_region_map` only counts a pixel as a junction when 2+ of its
    4-connected neighbors are *background*, and `(193, 228)` has only one
    background neighbor (the other three are ink from the converging
    strokes), so it fails that test outright.  This is a structural gap,
    not a tunable threshold: the existing junction detection is built
    entirely around "this ink separates two background regions" (a stem
    meeting a bar), which a 3-ink-strokes-converging point never matches.
  - A same-rotational-direction turn-delta rule (two consecutive 45-degree
    leg-to-leg turns with the same sign) was tried first and looked exactly
    right when checked only against the confirmed merge point, but the
    walker's own recorded path there is actually N-then-NW-then-N (turning
    back, opposite signs), not N-then-NW-then-W (continuing the same way)
    as the drawing's true geometry would suggest -- `W` is never reachable
    in a single step from the pixel in question, so the walker is forced
    onto the "wrong" direction regardless, and this rule never fires on the
    walker's actual path at all.
  - A punched-hole connected-components signal (`_ink_component_count`:
    remove a small disk of ink around a candidate pixel, count surviving
    connected pieces in the surrounding window) reliably reads exactly 2 for
    every real opcode's own turn point across both fixtures and every
    `render.py`-generated opcode, and 3 for both the confirmed merge point
    and a real T-junction -- correctly separating "ordinary bend" from
    "something unusual here" in every case checked *at the time it was
    checked*.  Wiring it into `_walk`/`_walk_tree` as a second candidate-
    pivot trigger (alongside the existing region-adjacency one), with a
    genuinely new third code path for "candidate pivot, not a real fork
    (only one viable arm), and the ink-component signal is what flagged it"
    to stop the walk instead of folding back into a continued walk, passed
    every synthetic `render.py` round-trip test -- but broke real-fixture
    round-tripping via a *different* false positive: `fixtures/addition.png`
    has a genuine, ordinary bend at `(44, 159)` (the documented "bar bends
    into a diagonal" corner, not a branch or merge) that this signal also
    reads as 3 pieces, for reasons not diagnosed further before reverting.
  - Takeaway: a purely local pixel-geometry signal has broken on a new,
    previously-unchecked bend every time one has been tried so far,
    suggesting the real distinguishing fact may not be visible from local
    geometry around the candidate pixel at all -- e.g. it may require
    knowing which stroke a piece of ink "belongs to" (tracked across the
    whole drawing, not derivable from one point), which none of these
    attempts had access to.  `classify_ops`'s own workaround (reject a
    trailing opcode call that consumes the walked path's literal last run)
    remains the only verified fix, and stands on its own regardless of
    whether `_walk_tree` is ever fixed at this deeper level.
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
