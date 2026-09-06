# Line renderer and extractor: design history

Why `extra/line/` runs on the standard library alone, and why its layout
constants hold the values they do.  The code in `extra/line/render.py` and
`extra/line/extract.py` is authoritative and not restated here; this file
keeps the arguments and measurements a future change would otherwise have to
re-derive.

## The four dependencies, and why each one went

`extract.py` started on four undeclared third-party libraries (Pillow, numpy,
scipy, scikit-image) and now has none.  The recurring lesson, in all four
cases, was that the call did not need the library's actual algorithm.

**scipy.** `ndimage.distance_transform_edt` was previously called "the one
hard piece to replace" -- a brute-force replacement is O(ink x background)
and took 2.6s on a 500x500 fixture.  But `find_cursor` never wanted a
distance transform: its only use was the threshold `dist > 1.5`.  No pixel
with a non-ink 8-neighbor can exceed sqrt(2) ~ 1.414, so that test is "all 8
neighbors are ink" -- a 3x3 binary erosion (`_erode`).  Confirmed
bit-identical to the scipy threshold on every fixture, cropped and
normalized.  `label`/`sum`/`center_of_mass` were the easy remainder: a BFS
(`_largest_thick_region`) and a plain coordinate mean.

**scikit-image.** `skeletonize()` only ever fed a scalar length into
`detect_scale()`'s ink/skeleton-length ratio, a ~5%-accurate estimate of the
stroke width.  `normalize_scale`'s docstring already stated the real
invariant -- input is "an integer pixel-replication blow-up of a 1px-wide
drawing, not a resampled photograph" -- so `detect_scale` now tests that
invariant directly (block uniformity), which is exact rather than
approximate.  Verified to agree with the old ratio on both fixtures at 1x-5x.

**Pillow.** Expected to be the hard one, since `Image.open` is real codec
work.  But the only images passing through here are PNGs this repo's own
`render.py` wrote or the wiki reference drawings in `fixtures/`, and PNG's
container is length-tagged chunks over zlib, both in the standard library --
so `png.py` decodes them outright, matching Pillow byte-for-byte on all five
fixtures.  `Image.resize(NEAREST)` was a strided slice, with one wrinkle
about grid alignment recorded in `normalize_scale`.  Every PNG is readable,
including interlaced and 16-bit, since a drawing that has been through an
image editor comes back in whatever that editor preferred and is still the
same drawing.

**numpy.** Looked like the one with a real cost, since the masks reach 9Mpx
and pure-Python per-pixel loops over that would be minutes.  The answer was
to stop storing pixels individually: `mask.py` keeps one Python int per row
and lets CPython's bigints do whole-row bitwise work, *faster* than the numpy
it replaced on the operations that matter here (see that module's docstring
for the measurements).  It also retired the quadtree `extract.py` used for
bounding boxes, which existed only to work around numpy's whole-canvas
`nonzero()` scan.

**The narrowing that stands: only PNG.**  A baseline JPEG decoder was written
-- it worked, and is recorded in `extra/line/WIP.md` -- and then deliberately
dropped, because 300 lines for *partial* JPEG support was the least
defensible of the three available positions (all of it, none of it, or an
awkward middle).  `render(scale=)` solves the underlying problem in 20 lines
by making drawings survive lossy pipelines whoever decodes them.

## Why `_CLEARANCE` is 1, not 0

Non-overlap alone is not enough for the extractor to read a drawing
correctly.  Two strokes running through directly *abutting* grid cells share
no cell at all, but rasterize into a contiguous 2-cell-wide ribbon of ink --
and `lattice._band_lit` deliberately probes the exact ray *plus one pixel to
each side*, to absorb hand-drawn stroke slop, so it reads the neighbor as a
real lit direction.  An extra lit direction at an ordinary point turns it
into a spurious 3-lit `"fork"`, which `simulate` then executes as a
conditional turn.

Historically the *nested-loop regression itself* was a searched route
touching *itself* -- per-stroke attribution on `++[>++[>+<-]<-]>>.` showed
all three arms of the spurious junction belonging to one single 530-cell
detour.  Constructed loop-backs cannot fold back on themselves, so only the
between-stroke case remains live.

The constant is pinned independently by `test_bf_to_line.py`'s
`TestStrokeSeparation`: at 0, every program it checks develops between-stroke
adjacency (up to 76 consecutive abutting cells on `++[>++[>+<-]<-]>>+++.`),
at 1 none does.  That test exists because the ordinary suites do *not* catch
this -- they assert on program output, and a drawing can rasterize a 2px
ribbon while still extracting and executing correctly.  Setting this to 0
left every other test passing, which is why stroke separation had to be
measured directly to pin it.

## Arm spacing: from fork-count to measured extent

Arms were once sized `_BRANCH_SPACING * 2 ** remaining_depth` from a
`_fork_depth` helper that counted how many more nested `?` forks an arm still
had to fit.  That geometric halving encoded a real insight -- every fork
turns its children 90 degrees, so a *grand*child turns back toward the
original heading and overshoots its grandparent's axis if its arm is longer
than the distance back to it, which is why arms must shrink with depth rather
than grow (an earlier version grew them, and scaling it up 10x reproduced the
identical "extraction left N pixels unaccounted for" failure, since growing
rather than the absolute scale was the bug).

But counting forks is a poor proxy: it is blind to how much ink a subtree
lays down.  Measured directly, the two depth-3 programs
`+[>+[>+[>+<-]<-]<-]>>>.` and `++[>++[>++[>+<-]<-]<-]>>>.` produce *identical*
spacing at every fork (40/20/10 units) despite carrying different op counts
in every arm, and the heavier one is exactly the case that exhausted the
since-removed search-based router under fork-count spacing.  A fork's two
arms were sized identically for the same reason, even when wildly asymmetric
(4 ops on one arm and 14 on the other).  `_arm_spacing` now measures each
subtree's real extent instead, which subsumes the H-tree insight: "how far
does this subtree reach back toward the trunk" is the quantity the halving
was approximating.

**No sibling-separation term.**  An intermediate version had one and it was
actively harmful.  The two arms leave the fork in opposite directions along
one axis, and `reach_back` already puts each subtree's *entire* bounding box
strictly on its own side of the trunk, so the two boxes are separated by at
least twice the margin automatically.  The arms' lateral spans spread along
the perpendicular axis, where the boxes cannot meet at all.  Adding a lateral
term regardless double-counted it into both arms and, because each fork's
measured span then contained its children's already-inflated spacing,
amplified geometrically with depth: a depth-3 program's outermost arm
measured 149 units laterally and rendered at 7760x3800 (vs ~1600 with the
term removed).

**One corridor, not one per `goto`.**  The per-goto multiplier dated from the
search-routing era, when `n` free-form detours could all cross one gap and
each blocked a corridor of it; constructed returns never share a gap that way
-- every nested loop-back rides its *own* fork's bay, and parents reserve
room for it through the measured extent.  Measured on the depth ladder when
the multiplier was dropped: every program still round-trips, flat-loop
drawings are pixel-identical, and nested areas shrink 17% at depth 4 to 44%
at depth 10 (the multiplier compounded through nested extents, so its cost
grew with depth just as its removal's savings do).

## Why the extent cache is per-render

Measuring is a full dry-run `_layout` of the subtree, and every fork asks
about subtrees that themselves contain forks -- so without memoization the
work is exponential in nesting depth, not merely repeated.  An unmemoized
version stalled outright on a depth-3 program (no output at all after two
minutes, where the memoized one finishes in well under a second).

The cache is cleared at the start of every `render()` rather than living as a
permanent global, because `id()` is only unique among *live* objects: a
`Node` freed between two renders can have its address reused by an unrelated
node in the next one, which a persistent cache would answer with the dead
node's extent.
