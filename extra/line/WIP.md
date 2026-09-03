# Line: open questions and standing constraints

`render.py`, `extract.py`, `simulate.py`, and `verify.py` implement a
program renderer, a pixel-based extractor, and a runtime interpreter for
[Line](https://esolangs.org/wiki/Line), an esolang whose spec is entirely a
set of hand-drawn curve images with no text format and no reference
implementation (tagged `Unimplemented` on the wiki). The module docstrings
in `extract.py`/`render.py`/`simulate.py`/`lattice.py` carry the settled,
load-bearing reasoning for how each module works; this file records only
what future work must respect -- open questions, constraints a change could
violate without those constants themselves saying so, and decisions
deliberately not taken. `docs/streetcode.md` is the comparable file for
Streetcode, which still has real open questions of its own.

Test suites: `test_simulate.py`, `test_line_boolean.py`, `test_bf_to_line.py`,
`test_png.py`, `test_mask.py`. Run any of them with `uv run --with pytest
--with pytest-xdist pytest <file>` from this directory, or a bare `pytest`
from the repo root (they're under `testpaths`). CI's `line` job additionally
runs them under `--isolated --no-project` (only pytest installed), which is
the standing proof this subtree has no third-party dependencies -- the
in-project run cannot show that. `verify.py` is the separate, narrower
round-trip check for `extract()` alone. `test_simulate.py`'s hand-built
`Stroke` fixtures never exercise `render.py`'s loop-drawing geometry
(`_layout`/`_loop_return_legs`); only `test_bf_to_line.py` does.

## Still open

- Real (camera/scan) photographs with genuine anti-aliasing, as opposed to
  the clean nearest-neighbor-scaled synthetic input `normalize_scale` was
  tested against. Anti-aliased edges could make the exact-integer scale
  detection (`round(ink/skeleton_length)`) land less cleanly.
- `lattice.star`'s probe `length` is hardcoded to 15 pixels while
  `lattice.UNIT` is configurable; below a grid unit of ~20 the probe
  overruns its own segment. A future change supporting smaller units should
  derive the default from `UNIT` (something like `UNIT - 5`, preserving
  today's 20 -> 15 relationship) rather than adjusting `_UNIT_TOLERANCE`,
  which is not the limiting factor. Nothing in this tree renders below 20
  today.
- Boolean generation (`line_boolean.py`) is verified through n=7; n=8 and up
  is untested rather than known-bad (canvas roughly doubles in area per
  input), so the real limit is whatever canvas/extraction time a caller
  tolerates.
- `find_cursor`'s arrowhead ambiguity: it rejects a non-arrowhead-shaped
  candidate (fill-ratio bracket), but does not resolve genuine ambiguity
  between two equally arrowhead-shaped candidates -- picks the larger by
  design, unconditionally.
- Hand-drawn input at a substantially different scale is genuinely
  unverified -- distinct from the anti-aliasing item above: here stroke
  width and unit length could vary *independently* in a way none of this
  synthetic sweep (which scales both together) reproduces.

## Runtime simulation

The loop-back recovery mechanism, the zero/nonzero arm convention, and the
no-step-limit decision live in `simulate.py`'s module docstring and
`_compile`/`find_merge`'s own docstrings; the design history is in git.

## Constraints a future change must respect

- **`>`/`i` and `<`/`o` must not share identical geometry** -- confirmed by
  re-measurement against the wiki's reference images. `_OPS`'s per-opcode
  geometry is otherwise recorded in `render.py`'s module docstring and the
  comment above `_OPS`.
- **The coverage-check threshold in `extract()` is correctly calibrated and
  should not be loosened.** Measured across JPEG recompression at every
  quality level and stroke width 1x-4x: every failure is a genuine one
  (gaps of tens to hundreds of pixels against a threshold of 2), and the
  program that would come back if the check were permissive is wrong, not
  merely degraded. There is no marginal band where leniency would recover
  anything -- gaps are 0 or they are enormous. Redundancy at write time
  (thicker strokes, `render(scale=k)`) strictly beats leniency at read
  time, because it preserves the signal instead of guessing at it. A 1px
  stroke survives JPEG to quality 34; 2x+ survives to quality 15 and
  reconstructs *exactly* (gap 0) whenever it succeeds at all.
- **`_STEM_LEN` (10 units) has ~1 unit of measured slack** (9 and 8 both
  round-trip everything with flat corridors) but shrinking it is not worth
  taking: the gain is under 3% of area against the 17-44% the corridor
  change already bought, and the stem's length is what keeps the landing
  diagonal and `lattice.star`'s probe geometry comfortably apart. Slack
  here serves robustness, not waste.
- **`_UNIT` (20) has an untried compactness lever**: the pipeline is
  documented clean at 16-28 (floor set by `lattice.star`'s hardcoded 15px
  probe, see above), so dropping to 16 would shrink every rendered output
  another ~20% linear / ~36% area. Not done, because it rescales every
  drawing this repo produces -- a broader change than whatever prompted
  looking at it.
- **Parity with the wiki's own hand-drawn fixture size is not reachable,
  and is not a bug.** A constructed loop-back must travel out and around
  (cardinal-only, `_CLEARANCE`-separated from existing ink), where the
  wiki's hand drawing reconnects on a short diagonal flush against its own
  earlier ink -- legal for a human, but exactly what `_CLEARANCE` exists to
  forbid (`lattice._band_lit`'s +-1 lateral reach cannot tell a flush
  parallel stroke from a real junction). Do not chase this gap by loosening
  `_CLEARANCE`.
- **Reserve routing corridors during layout, not after.** Any future
  routing scheme for drawn loop-backs must not resurrect free-form
  search-based routing (the deleted A* router): nested `?`-loop detours are
  topologically nested, and a scheme that lets them compete for space
  globally will hit the same enclosure wall this one did, regardless of
  how good its routing heuristic is. See below for the measured mechanism.

### Why free-form loop-back routing does not scale with nesting depth

`render.py` and `test_bf_to_line.py` cite this pair of findings by name; it
is why `_loop_return_legs` constructs each loop-back deterministically from
measured geometry instead of searching for one.

**Why depth 4 fails: enclosure, not routing quality or padding.**
Instrumented on `+[>+[>+[>+[>+<-]<-]<-]<-]>>>>.`: the third of four
loop-backs reports 154 "no corridor exists at any padding" and 0 "route
folded back on itself" -- so routing quality is not involved. Padding
doubling to 256 cells against an ~80x66-cell drawing doesn't help, nor does
detour ordering, nor does a pixel-exact `step=1` A* (0 of 22 otherwise-viable
candidates route). A flood fill from the failing detour's own start, using
the router's own clearance rule, reaches only 15% of the canvas: the
detour's departure point is sealed into a pocket by fixed geometry plus the
two detours already routed. Detours are far bigger than the program they
serve (fixed geometry 215 cells; first two detours add 117 and 182 more),
each blocking a 3-cell-wide swath that cuts the drawing into disconnected
pockets while only 28% blocked overall.

**Depth 5 shows soft costs cannot fix it either.** The obvious escalation
-- extending soft `avoid` regions from doorstep blobs to each pending
detour's whole start-to-stem rectangle -- was measured and rejected: depth
4 renders identically and depth 5/6 still fail. A soft cost steers a route
among alternatives *that exist*, but when every route for a big outer
detour must cross an inner lane somewhere, it pays the toll and crosses,
cutting the lane exactly as thoroughly as a free crossing would. This is
why the fix had to be structural (rings constructed per nesting level, not
searched) rather than another costing tweak -- any future change to
loop-back layout should treat "make the router smarter" as a dead end
already measured twice, not an untried option.

## Deliberately out of scope

- **Not wired into the interpreter registry**: Line has no text format, so
  it doesn't fit the `run(code, io)` convention every other language in
  `src/esolangs/` uses. Stays a standalone `extra/` tool.
- **No non-PNG image formats.** JPEG, BMP, GIF and TIFF went with Pillow
  when the dependency was dropped (see `extract.py`'s module-level comment
  above the imports for the full per-library reasoning). A baseline JPEG
  decoder was written and verified working, then deliberately removed:
  it supported only baseline JPEG, and progressive JPEG (common on the web)
  would have needed another ~100-130 lines and a restructuring. 300 lines
  for partial format support was judged the least defensible of the three
  available positions (all of it, none of it, or an awkward unstated-
  contract middle). `render(scale=)` addresses the underlying need (drawings
  surviving a lossy round trip) in 20 lines regardless of who decodes them.
  A future need for JPEG input should reconsider full progressive support
  as a deliberate scope expansion, not resurrect the partial decoder.
- **No step limit or cycle-hang detection in `simulate.run`.** Matches
  every other interpreter in this repo (e.g. `brainfuck.py`'s `run` is a
  bare `while not machine.halted: machine.step()`); `src/esolangs/vm.py`'s
  cycle detection is an opt-in debugger wrapper no language's main run path
  uses. A non-halting Line program hangs, same as an infinite Brainfuck
  `[]` loop would. If a limit is ever wanted, real cycle detection matching
  `vm.py`'s convention is the right upgrade, not a step cap (rejected once
  already as a wrong-fit pattern carried over from other, now-changed
  interpreters).
- **Arbitrary-precision tape cells**, not wrapped/bounded width -- this
  module's own reading of the wiki's silence on the question, not something
  the wiki confirms either way. A future change assuming byte-width cells
  would be changing behavior, not fixing a bug.

## Hand-decoded ground truth (not derivable from any source file)

The confirmed merge pixel in `fixtures/multiplication.png`'s normalized
mask is `(194, 228)` (the `root.nonzero.nonzero` arm), hand-decoded end to
end by a human reading the actual drawing: branch right onto E, immediate
corner onto N, then `>`, `+`, `>`, `+`, `<`, `<`, `-`, then this merge
point, where the stroke's own NW diagonal run ends one step before a pixel
where a *different*, already-drawn stroke (the outer branch's own
horizontal bar, travelling W) is the only ink physically touching.
`lattice.py`'s module docstring cites this pixel as the worked example for
why its 8-direction star probe reads 3 lit directions there; keep this
paragraph in sync if that fixture or the probe's behavior on it ever
changes.
