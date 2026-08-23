# Line: implementation record

`render.py`, `extract.py`, `simulate.py`, and `verify.py` implement a
program renderer, a pixel-based extractor, and a runtime interpreter for
[Line](https://esolangs.org/wiki/Line), an esolang whose spec is entirely a
set of hand-drawn curve images with no text format and no reference
implementation (tagged `Unimplemented` on the wiki). This file tracks
what's settled and tested, what's deliberately out of scope, and what
was resolved along the way -- the module docstrings in
`extract.py`/`render.py`/`simulate.py` carry the settled, load-bearing
reasoning, and this file records how it was arrived at.  Only one item is
genuinely open (see "Still open"); `docs/streetcode-wip.md` is the
comparable file for Streetcode, which still has real open questions.

`test_simulate.py` is a real `pytest` suite covering `simulate.py`
(opcode basics, the zero/nonzero swap, both wiki fixtures across several
real inputs, and the synthetic loop-back mechanism, including a hang
check); `test_line_boolean.py` covers `line_boolean.py`'s generated
decision trees end-to-end (render -> extract -> simulate) for n = 1-3 plus
5-input parity, across every input combination; `test_bf_to_line.py` covers
`bf_to_line.py` through the same full pipeline, and is the only suite that
exercises `render.py`'s loop-drawing geometry (`_layout`/
`_loop_return_legs`) at all -- see the nested-loop entry below for why that
distinction matters. Run any of them with `uv run --with pillow --with
numpy --with scipy --with scikit-image --with pytest --with pytest-xdist
pytest test_simulate.py` (or `test_line_boolean.py`, or
`test_bf_to_line.py`) from this directory (none is under the repo root's
`tests/` `testpaths`, so a bare `pytest` from the repo root will not find
them). `verify.py` remains the separate, narrower round-trip check for
`extract()` alone.

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
- **Extraction**: `extract.py` walks the path/branch structure of both wiki
  reference images by delegating to `lattice.py`'s 8-direction vertex-star
  walker (see below), with near-complete pixel accounting (verified via
  `verify.py`'s XOR round-trip, now also run automatically inside
  `extract()` itself).  `extract.py` itself now owns only image
  normalization (`load_binary`/`crop_to_content`/`normalize_scale`), cursor
  isolation (`find_cursor`), and the layers built on top of a walked tree
  (`classify_ops`, `coverage_gap`) -- the walk itself, including branch
  detection, is entirely `lattice.py`'s responsibility.  The previous
  region-adjacency walker (`build_region_map`/`_walk`/`_walk_tree`) has been
  removed outright, not kept alongside as a fallback.
- **Opcode classification**: `extract.py`'s `classify_ops` identifies which
  instruction produced each kink in a walked stroke's vertices, matching
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
  - **Partly resolved: the pipeline holds at grid units 16-28, and the
    limiting factor is not `_UNIT_TOLERANCE`.** Tested by rendering five
    programs (straight-line, pointer movement, a single loop, a transfer
    loop, and the two-level nested loop) at `render._UNIT` values of 12,
    16, 20, 28 and 32, each run all the way through
    extract -> classify -> simulate and checked against its expected
    output. 16, 20 and 28 are clean across all five. 12 fails every
    program, and 32 fails only the nested case.

    The 12 failure is not a tolerance problem at all: `lattice.star`'s
    probe `length` is hardcoded to 15 pixels while `lattice.UNIT` is
    configurable, so once a grid unit is shorter than the probe, every
    star reading overruns its own segment into whatever follows. Anything
    wanting to support smaller units should derive that default from
    `UNIT` (something like `UNIT - 5`, preserving today's 20 -> 15
    relationship) rather than adjusting `_UNIT_TOLERANCE`. Left as-is for
    now since nothing in this tree renders below 20.

    Still genuinely unverified: non-`render.py` *hand-drawn* input at a
    substantially different scale, where stroke width and unit length vary
    independently in a way none of this synthetic sweep reproduces.
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

- **Merge detection, via `lattice.py`'s vertex-star walker, now wired in as
  `extract.py`'s only walker**: the previous region-adjacency walker had
  one confirmed structural gap -- a merge, where one stroke's last leg runs
  straight into a *different*, already-drawn stroke's ink with no
  separating background pixel, which a pixel-adjacency walk cannot tell
  apart from an ordinary continuation.  Three local-pixel-geometry fixes
  were tried directly on that walker and reverted (each broke on a new
  bend the previous fixture check didn't cover; see "Resolved" below for
  the full history).  `lattice.py` resolves it instead with a from-scratch
  walker built around a single idea: at every vertex, probe all 8 compass
  directions for a real segment leaving that point (`star()`), and count
  how many are lit.  2 means an ordinary bend; 3 means a real
  conditional-turn fork *or* an incidental merge (the two are told apart by
  whether the extra two directions are the pair perpendicular to the
  arrival heading, matching the wiki's T-branch shape -- if not, it's a
  merge); 4 means an incidental crossing the cursor passes straight
  through.  A merge naturally reads as "3 lit directions" the same way a
  real fork does, so the walker stops there without needing a dedicated
  merge signal at all -- confirmed directly against the hand-decoded
  `(194, 228)` merge pixel from the reverted attempts, which reads exactly
  3.

  The probe itself checks a 3-pixel-wide band (the exact ray plus one
  pixel to each side, perpendicular to the ray's own direction), not a
  single 1px-wide ray -- a single-ray probe was tried first and broke
  twice more: hand-drawn curves don't sit at one exact pixel width, so an
  exact-length ray can miss a real segment that measures a pixel short of
  the nominal grid unit (confirmed: real segments on both fixtures measure
  19-20px against a 20px nominal unit), and a walked path's own recorded
  stopping pixel can be a row/column off the true geometric vertex
  (confirmed at `fixtures/addition.png`'s real T-junction, whose bar sits
  one row above where the incoming stem's own path data ends).  The band
  absorbs both failure modes in one check.  A separate `_snap` step
  additionally re-centers onto a chosen direction's true centerline
  before walking it (needed because the vertex a stroke's own walk lands
  on can be a pixel off a *different* leg's true row/column -- e.g. the
  V-shaped notch in `fixtures/addition.png`), requiring several pixels of
  confirmed ink (not just one) to avoid a *different* leg's ink brushing
  past for a single pixel being mistaken for the true centerline.

  A second, related off-by-one was found and fixed while wiring this
  walker into `extract()`'s real pipeline (not caught by the earlier
  per-vertex `star()` audit, which checked reachable vertices but not
  whether every real vertex was actually being reached): `_walk_segment`
  can also stop one pixel short of a real corner *laterally*, i.e. the
  same true-vertex-is-a-pixel-off problem `_snap` handles for continuing a
  stroke, but for the pixel a segment stops walking at in the first place
  -- confirmed on `fixtures/multiplication.png`, where a walked S segment
  stopped at `(72, 267)` (`star` reads only `{N}`, looking like a genuine
  dead end) one column short of the true NE-turning corner at `(72, 268)`
  (`star` reads `{N, NE}`), silently truncating an entire ~460px
  downstream branch with no error of any kind -- caught only by comparing
  this walker's full-tree coverage against the (still present at the time)
  region-adjacency walker's on the same fixture, not by the per-vertex
  audit alone.  Fixed by `_resnap_dead_end`: whenever a landed vertex's
  `star()` reading looks like a dead end (nothing but the arrival
  direction lit), re-probe both of its immediate perpendicular-to-heading
  neighbors before trusting that reading, the same `k in (-1, 1)` offset
  `_snap` already uses elsewhere.  Confirmed this cannot misfire on a
  genuine dead end (both wiki fixtures' real stroke endpoints still read
  as dead ends at every perpendicular offset checked).

  Verified: every direction-change vertex in both wiki fixtures (~90
  total) reads exactly 2 (ordinary bend), 3 (fork or merge), or 1 (a
  genuine stroke dead end) with no ambiguous or wrong readings; full tree
  reconstruction on both fixtures recovers the same pivot counts this file
  already established (1 for addition, 3 for multiplication) with the
  exact same set of classified opcodes per arm as the old region-adjacency
  walker (confirmed by diffing both walkers' full opcode trees, modulo the
  arbitrary zero/nonzero right/left labeling, which can differ between two
  independently-designed walkers); and -- unlike the old walker -- correctly
  round-trips the previously-broken "`?` followed by more opcodes in both
  branches" case with no coverage-check workaround needed.
  `coverage_gap`/`classify_ops` were ported to work directly off
  `lattice.py`'s sparse vertex/heading data rather than a dense pixel path:
  `classify_ops`'s run-length scan reads runs straight off consecutive
  vertices (each already a maximal same-heading run, so no merging step is
  needed), and `coverage_gap`'s redraw re-walks each leg pixel-by-pixel
  from its start vertex (mirroring `_walk_segment` exactly) rather than
  assuming a straight line the Chebyshev distance to the next vertex --
  confirmed necessary since `_snap`'s perpendicular correction can land a
  vertex a pixel off the pure heading line, which a straight-line
  reconstruction undercounts by a pixel at exactly that bend (found via
  the same `fixtures/addition.png` bend noted above).  Net result: both
  wiki fixtures now gap by exactly 2 pixels (the constant arrowhead-tip
  gap, see `_ARROWHEAD_TIP_GAP`) regardless of branch-pivot count, an
  improvement over the old walker's gap, which also grew by one pixel per
  pivot.

- **Runtime simulation**: `simulate.py` executes a walked `Stroke` tree
  against a Brainfuck-style tape (unbounded ints, `defaultdict`-backed,
  pointer starts at cell 0) -- `+`/`-` increment/decrement, `<`/`>` move
  the pointer, `i`/`o` read/print the current cell as a number, `?`
  branches on it, all per the wiki's own (loosely) documented wording (see
  `simulate.py`'s module docstring for exact quotes and every place the
  wiki leaves a detail unspecified).  Verified against every synthetic
  `render.py`-generated program used to test `classify_ops` (straight-line
  op sequences, pointer movement across cells, both arms of a real `?`)
  and against both wiki fixtures (`addition.png`/`multiplication.png` run
  to completion with no error).

  Two real, previously-unknown bugs surfaced building this, neither in
  `simulate.py`'s own first draft's design assumptions but in what the
  existing walked tree actually means:
  - **The `zero`/`nonzero` field-name swap `coverage_gap`'s own verification
    (above) dismissed as a cosmetic labeling difference is not cosmetic for
    execution.** `lattice._classify` computes its fork `right`/`left`
    options relative to `back` (the direction arrived *from*);
    `render.py`'s `_turn_right`/`_turn_left` rotate relative to `heading`
    (arrived *in*, `back`'s opposite) -- two rotations 180 degrees apart.
    Confirmed concretely with a synthetic program whose `render.py`-drawn
    `zero` arm (which `render.py` draws turning right, matching the wiki's
    "turn right if 0") round-trips through `extract()` into the walked
    tree's `nonzero` field, and vice versa.  Neither `lattice.py` nor
    `extract.py` needed to know which physical arm was "actually" zero vs.
    nonzero before now, since a one-time structural trace only needed *a*
    consistent label, not the *correct* one -- this only mattered once
    something needed to execute the branch correctly.

    **Since fixed at the source, rather than compensated for.**  `run`
    originally took the walked `nonzero` child on a zero cell (and vice
    versa) to correct for the inverted labels -- correct, but a
    compensating bug in a second place rather than one fix.
    `lattice._classify` now rotates its `right`/`left` off the *heading*
    (`_opposite(back)`), the same frame `render.py` uses and the frame the
    wiki's own "turn right if the current cell is 0" is written in, so the
    field names mean what they say and `run` reads plainly (`zero` on a
    zero cell).  The change is behavior-neutral end to end: every test that
    goes through the real render -> extract -> simulate pipeline passed
    unchanged across it, and both wiki fixtures still compute correct
    results on every input pair (addition `(3,2)->5`, `(0,0)->0`,
    `(7,3)->10`, `(10,10)->20`; multiplication `(3,2)->6`, `(4,4)->16`,
    `(0,5)->0`).  Only `test_simulate.py`'s hand-built `Stroke` fixtures
    needed updating, since they encoded the old inverted convention
    directly -- their loop body is now the `nonzero` arm, which is what a
    loop repeating "while nonzero" should always have been.
  - **A drawn loop-back has no representation in the walked tree at all.**
    `lattice.walk_tree` stops a stroke the instant it revisits any already-
    `visited` vertex, recording only that vertex's coordinates with no link
    back to the earlier node they match -- fine for a one-time trace, but a
    real loop-back (the only way Line can express repetition, since `?` is
    the only control-flow opcode) needs exactly that link to execute.
    `simulate.py` recovers it itself, without changing `lattice.py`/
    `extract.py`: every leaf's final vertex is tested against every other
    stroke's geometry (both exact matches on a stroke's own final vertex --
    a real fork or dead end -- and a point landing strictly *inside* one of
    a stroke's straight legs, since a real merge can land mid-segment, not
    only on a recorded vertex -- see the "real drawn loop" entry above for
    why the mid-segment case turned out to matter on a real fixture), and a
    match becomes a jump that resumes execution from exactly that point,
    running only the ops that had not yet run there (via
    `extract.OpCall`'s own `index`) and skipping the ops that already ran
    the first time that point was reached (see `_Compiled.goto`'s
    docstring).  Getting this right took three failed attempts on a
    synthetic decrementing loop before the real fixture even entered the
    picture: indexing every node by its *entry* coordinate let a fork's own
    child -- which always starts exactly where the fork ends -- shadow the
    fork itself; indexing by a stroke's own final vertex only fixed that
    but missed the mid-segment case entirely (silently reporting both real
    fixtures as loop-free, the wrong claim corrected above); and once
    mid-segment matching was added, testing "does this point equal any
    vertex of any stroke" (not just a stroke's own final one) matched an
    unrelated, never-taken sibling branch instead of the real ancestor
    fork, since both happen to start at the same shared fork coordinate by
    construction -- fixed by only ever matching a vertex exactly when it is
    a stroke's own *final* vertex, and requiring strict interior
    containment (not touching either endpoint) for everything else.

  **Both wiki fixtures do contain a real drawn loop** -- an earlier claim
  in this file said otherwise, and was wrong.  That claim rested on
  checking whether any stroke's end coordinates *exactly* matched another
  stroke's own recorded vertex; `coverage_gap` reporting only the baseline
  2-pixel arrowhead gap on `addition.png` was taken as confirmation.
  Caught by looking at the actual rendered image directly (the wiki names
  these examples "Addition"/"Multiplication", and both algorithms
  genuinely need repetition to work for general inputs -- `addition.png`'s
  `?` arms are exactly Brainfuck's `,>,[-<+>]<.`) rather than trusting the
  coordinate check's silence: `addition.png`'s loop-body arm's walked path
  does reconnect, but to a point strictly *inside* the incoming stem's own
  straight run -- `(42, 159)` in the normalized mask, sitting exactly
  between two of that stem's own vertices, `(62, 159)` and `(22, 159)` --
  not onto any recorded vertex at all, which is exactly why the earlier
  exact-vertex check found nothing.  (The 2-pixel coverage gap was never
  contradictory evidence either way: `coverage_gap` only measures whether
  every walked pixel was accounted for, which a merge satisfies regardless
  of whether the merge is later recognized as a loop.)

  `_compile` now finds this kind of match too: every leaf's final vertex is
  tested against every other stroke's *segments*, not just their vertex
  lists, via an exact integer collinearity + strict-betweenness check (a
  Line segment always runs along one of 8 compass directions, so this is
  exact, not a tolerance-based approximation).  Landing exactly on some
  other stroke's own *final* vertex (a real fork or dead end) is also
  accepted, matching the original fork-only mechanism -- but landing on any
  *other* vertex is deliberately rejected even when the coordinates match
  exactly: every fork's two children start at exactly the fork's own end
  coordinate by construction, so a plain "does this point equal some
  stroke's own starting vertex" test matches *every* sibling arm sharing
  that corner, not just a real continuation -- confirmed to misfire this
  way on a synthetic loop test (a decrementing loop matched an unrelated,
  never-taken sibling branch instead of the real ancestor fork, because
  both happened to start at the same pixel).  Requiring strict interior
  containment for anything short of a stroke's own final vertex is what
  actually distinguishes a genuine merge from that coincidence.

  At the time this was written, `render.py`'s own `Node`/`_layout` could not
  produce a loop to test the mechanism against directly, since `Node` was a
  plain recursively-walked tree with no cycle support (confirmed: a
  hand-built cyclic `Node` graph hit Python's recursion limit rather than
  rendering) -- so the mechanism was additionally covered by a synthetic
  test that builds a looping `lattice.Stroke` tree directly by hand, checked
  two ways: a decrementing loop that terminates at exactly 0, and a
  genuinely non-halting loop confirmed to actually hang (not silently
  produce a wrong answer).  `render.py` has since gained real loop/cycle
  support (`Node.goto`, see "Real loop/cycle support in render.py, and a
  bf-to-Line compiler" below) -- but the real fixtures were, and remain,
  the stronger check regardless: `addition.png` computes the correct sum
  for every input pair tried (`(3,2)->5`, `(0,0)->0`, `(7,3)->10`,
  `(10,10)->20`), and `multiplication.png` the correct product (`(3,2)->6`,
  `(4,4)->16`, `(0,5)->0`).

  `run` deliberately has no step limit or cycle-hang detection: checked
  against how every other interpreter in this repo handles it, a plain
  `run(code, io)` never caps execution (e.g. `brainfuck.py`'s own `run` is
  a bare `while not machine.halted: machine.step()`) -- cycle detection
  (`src/esolangs/vm.py`'s `run_until_halt_or_cycle`, Brent's algorithm over
  a machine's full state) exists only as an opt-in debugger wrapper no
  language's main run path uses.  `simulate.py` matches that: a
  non-halting Line program hangs, the same as an infinite Brainfuck `[]`
  loop would.  (An earlier draft of this module added an arbitrary
  1,000,000-step cap by reaching for `oisc_cli.py`'s pattern instead --
  wrong fit, since that exists specifically because Decleq/AddSubJump
  self-modify their memory and provably cannot use cycle detection; Line's
  state is ordinary and revisitable, so if a limit is ever wanted here, real
  cycle detection matching `vm.py`'s convention would be the right upgrade,
  not a step cap.)  Arbitrary-precision tape cells (vs. some wrapped/bounded
  width) are similarly this module's own reading of the wiki's silence on
  the question, not something the wiki confirms either way.

- **Direct Line boolean-function generator**: `line_boolean.py` builds a
  `render.py` `Node` decision tree straight from a truth table, with no
  brainfuck intermediate at all -- unlike
  `esolangs.tools.boolean.tape.brainfuck`, whose `+48`/`+49` output only
  exists because brainfuck's own `,`/`.` are byte-oriented.  Line's `i`/`o`
  are already integer-valued (read/write a whole number, not a byte -- see
  `simulate.py`'s module docstring), so a 0/1 input or result needs no
  ASCII encoding to strip: the fix for "Line would print 48/49, not 0/1"
  was to never introduce brainfuck's byte convention in the first place,
  not to post-process it out.  Verified end-to-end (render -> extract ->
  simulate) across every input combination: identity, NOT, AND, XOR,
  3-input majority, and 5-input parity (pinned at 5 rather than the n=7
  that also passes, for suite runtime -- see the test's own docstring).

  **The n<=4 practical ceiling this entry used to record is gone**, and was
  an artifact of `_fork_depth`'s spacing, not anything about decision trees.
  It previously read: n=4 extracts slowly (~16s) at a canvas large enough to
  trip Pillow's decompression-bomb warning, n=5 would be impractical at
  roughly 35000x17000px.  Re-measured after extent-based spacing landed (see
  the nesting entry below), every one of these round-trips correctly with
  every input combination checked against its truth table: n=4 at 2000x2260
  (0.4s to extract), n=5 at 4000x2620 (1.0s), n=6 at 4160x4000 (1.5s), n=7 at
  8160x4340 (4.0s, 128/128 combinations correct).  So n=5 is ~57x smaller
  than the projection that called it impractical, and n=7 -- three levels
  past the old ceiling -- extracts in four seconds.

  Above n=6 the canvas exceeds Pillow's default decompression-bomb threshold,
  so reading one back needs `Image.MAX_IMAGE_PIXELS` raised; that is a Pillow
  default, not a limit of this generator.  n=8 upward is untested rather than
  known-bad (roughly 2x area per input), so the real limit is now whatever
  canvas and extraction time a caller tolerates.  Covered by
  `test_line_boolean.py`.

- **Real loop/cycle support in `render.py`, and a bf-to-Line compiler**:
  `Node` gained a `goto` field marking a real drawn loop-back -- after a
  node's own op runs, `_layout` closes a detour (`_close_loop`/
  `_route_legs`, collision-aware A*, 4-directional only, never diagonal)
  back to a point strictly *inside* the stem leading into an earlier `?`
  fork, not the fork's own vertex (forcing the detour onto the fork's own
  vertex with its own arrival heading always retraces the stem itself,
  since two straight approaches from the same heading onto the same point
  are the same line).  A mid-stem reconnection is exactly the shape
  `simulate.py`'s `find_merge` already handles as its primary real-world
  case (see "Runtime simulation" above).  `bf_to_line.py` uses this to
  compile a brainfuck program to Line, mapping `[...]` to a `?` fork whose
  `nonzero` arm is the loop body ending in a node whose `goto` points back
  at the fork.

  Getting `_layout`'s branch spacing right for a *wide* decision tree (not
  just a single loop) took a real, confirmed-wrong first attempt: spacing
  between sibling fork arms was originally sized by
  `_BRANCH_SPACING * (depth + 1)`, growing *outward* with absolute nesting
  depth on the assumption that deeper subtrees need more room. That is
  backwards for a layout where every fork turns its children 90 degrees
  from its own heading: a grandchild fork's own children turn back toward
  the *original* heading, and if that arm is longer than the distance back
  to the grandparent's own axis, it overshoots and crosses it. Confirmed
  concretely on a 3-level boolean-decision-tree generator (2**3 = 8 leaves,
  the first case with enough nesting to reconverge): the drawing crossed
  itself and `extract()` failed with hundreds of unaccounted pixels, and
  scaling the spacing constant up by 10x reproduced the *exact same*
  failure, since growing (not the absolute scale) was the bug -- every
  level still overshot its ancestors by the same ratio. Fixed by scaling
  *down* with remaining depth instead (`_BRANCH_SPACING * 2**remaining`,
  an H-tree layout: each 90-degree turn needs roughly half its parent's arm
  length, not more), via a new `_fork_depth` helper.

  **Resolved: the nested-loop regression.** Nested brainfuck loops (2+
  levels of real `[...]`) compiled via `bf_to_line.py` used to produce a
  silently truncated result -- confirmed on `++[>++[>+<-]<-]>>.`, which
  computed the right tape (cell 2 ends at 4, the correct product) but never
  reached the final `.` to print it, halting at a leaf with no `goto` and
  no further ops. It now prints `4`. The earlier guess recorded here (the
  exit path running *collinear* with the detour, i.e. the router choosing an
  overlapping route) was wrong on both counts: there was no overlap
  anywhere, and there were two independent causes, neither of which is a
  routing-quality problem.

  - **A rendered loop-back merge was structurally indistinguishable from a
    real `?` fork.** `_route_legs` is cardinal-only by design (a diagonal
    detour leg risks being misread as a `+`/`-` kink), and the stem it lands
    on is itself cardinal, so the detour's final approach was necessarily
    *perpendicular* to the stem. A perpendicular touch-down on a straight
    run lights exactly the arrival direction plus the stem's own two --
    which is the arrived-from direction plus the pair perpendicular to it,
    i.e. precisely the T-branch signature `lattice._classify` calls
    `"fork"`. The extractor therefore read every rendered loop-back as a
    conditional turn. The wiki's own fixtures reconnect *diagonally*
    (hand-drawn), which is why `"merge"` classification always worked there
    and why this only ever broke on rendered output. Fixed by
    `render._approach_points`: route cardinally to an approach point offset
    diagonally from the stem, then take one explicit diagonal leg onto it,
    so the merge reads 3-lit-but-not-perpendicular -> `"merge"` -> a leaf
    `simulate._compile`'s `find_merge` rescues into a `goto`, by design
    rather than by luck. The diagonal must be *longer* than `lattice.star`'s
    own 15px probe, not shorter, so the probe finds a full band segment
    along it. `classify_ops` does not misread this diagonal as a phantom
    `+`/`-`, because it already drops a candidate whose final leg is the
    walked path's literal last run -- exactly where this diagonal sits.

    This also means **single-level loops only ever worked by accident**:
    their merge point classified as the same spurious `"fork"`, and survived
    only because both bogus arms' `_walk_segment` happened to land on
    already-`visited` vertices, degrading the stroke back to a leaf. Nested
    loops broke the moment one arm reached somewhere unvisited.

  - **A detour could run flush alongside *itself*.** A route is planned
    against `occupied` as it stood before the route existed, and A* never
    adds its own in-progress cells to that set -- so nothing stopped a
    detour from doubling back and running adjacent to a leg it had laid down
    earlier in the same route. Rasterized, that is a contiguous 2px-wide
    ribbon, which `lattice._band_lit`'s deliberate ±1 lateral reach reads as
    an extra lit direction, manufacturing another spurious fork. Confirmed
    by per-stroke attribution (rendering each stroke in isolation and
    diffing in normalized-mask space): all three arms of the junction that
    broke `++[>++[>+<-]<-]>>.` belonged to *one* stroke, the inner loop's
    own 530-cell detour. Fixed by `_self_approaches`, which rejects a routed
    path that comes within `_CLEARANCE` of its own earlier self (ignoring a
    small window along the route, since consecutive cells and ordinary
    90-degree corners are adjacent by construction) and tries the next
    candidate target/approach instead.

    Ruled out along the way, so a future reader doesn't re-derive it: this
    is *not* a draw-order problem. Instrumenting `_close_loop`/`finish`
    showed the outer detour is routed last, against 814 already-occupied
    cells, so it had full knowledge of every fixed stroke.

  Both fixes are independently load-bearing, checked by reverting each in
  isolation: without the diagonal approach 6 of `test_bf_to_line.py`'s
  tests fail, without the self-approach rejection 2 do.

  `_CLEARANCE` (between-stroke clearance, as opposed to the self-approach
  check that reuses it) is pinned separately, by
  `TestStrokeSeparation`. This took a dedicated test to establish: setting
  it to 0 left every *output*-asserting test passing, since a drawing can
  rasterize a flush 2px ribbon and still happen to extract and execute
  correctly. Measuring stroke separation directly instead -- capturing
  `_layout`'s own stroke list and counting cells of one stroke sitting
  adjacent to a different stroke it shares no cell with -- shows the
  constant is load-bearing after all: at 0 every program checked develops
  adjacency (up to 76 consecutive abutting cells on
  `++[>++[>+<-]<-]>>+++.`), at 1 none does. An earlier version of this file
  recorded `_CLEARANCE` as reasoned-but-unpinned; that was accurate when
  written and is now superseded.

  **Resolved, and it was `_BRANCH_SPACING` being oversized all along: three
  levels of loop nesting now render.** This entry previously recorded a hard
  "loop nesting stops at two levels" limit -- `+[>+[>+[>+<-]<-]<-]` did not
  render at all, `_close_loop` exhausting every stem offset and approach at
  maximum padding and raising, with the failing outer loop-back's 154 routing
  attempts splitting 77 "no corridor exists at any padding" and 77 "the only
  available route folds back on itself". That measurement was accurate; the
  conclusion drawn from it ("a genuine lack of drawn space ... not something
  the router could solve") was half right. There genuinely was no room to
  route through -- but the reason was that `_BRANCH_SPACING`'s own arms had
  consumed it, not that the program needs more space than a drawing can
  provide.

  Lowering `_BRANCH_SPACING` from 20 to 5 (see its comment in `render.py` for
  the sweep behind that number) makes `+[>+[>+[>+<-]<-]<-]>>>.` render,
  extract cleanly, and print the correct `1`. `TestNestingDepthLimit` was
  rewritten accordingly, exactly as its own docstring instructed a future
  session to do ("if a future layout change makes three levels work, this
  test should be replaced by a real round-trip assertion, not deleted").

  **`_fork_depth` is now gone, and with it the last of the nesting limit.**
  The entry above was written when the *heavy* depth-3 body
  (`++[>++[>++[>+<-]<-]<-]>>>.`, same shape with doubled `+` runs) still
  exhausted the router, and concluded the honest boundary was "arm weight, not
  nesting count". That was still measuring the symptom. Both causes have since
  been fixed at the source, and the heavy body now round-trips too:

  - **Spacing is measured, not inferred from branching structure.**
    `_fork_depth` counted how many nested `?` forks an arm still had to fit
    and fed `_BRANCH_SPACING * 2**remaining`. That is blind to how much ink a
    subtree actually draws: the light and heavy depth-3 bodies got *identical*
    spacing at every fork (40/20/10 units) despite different op counts in
    every arm, and a fork's two arms got the same length even when one held 4
    ops and the other 14. `_subtree_extent` now dry-runs the real `_layout`
    against a scratch cursor and measures the bounding box, and `_arm_spacing`
    sizes each arm from how far its own subtree reaches back toward the trunk.
    This subsumes the H-tree halving rather than discarding it -- "how far does
    this subtree reach back" is exactly the quantity `2**remaining` was
    approximating.
  - **Detours route in a second phase, against the finished drawing.** This
    was the bigger one, and it was an *ordering* bug rather than a spacing
    bug: `_close_loop` used to run the instant a `goto` was reached during
    layout, so a detour could only avoid ink that already existed at that
    moment, and every stroke drawn afterwards was free to march straight
    through the corridor it had just taken. Nothing ever checked. No amount of
    extra arm spacing can fix that, because the collision is with geometry
    that did not exist when the route was chosen. `_layout` now records each
    loop-back as a `_Pending` entry and `_route_pending` routes them all after
    layout completes, outermost fork first -- the two-phase layout this file
    proposed as a guess and which turned out to be the actual fix.

  A wrong turn worth recording, since it looked plausible and cost a cycle:
  sizing arms additionally by their subtree's *lateral* span, on the theory
  that sibling arms collide sideways. They do not -- the two arms leave a fork
  in opposite directions, so `reach_back` alone already puts each subtree's
  whole bounding box on its own side of the trunk, and the lateral spans
  spread along the perpendicular axis where the boxes cannot meet. Adding the
  term anyway double-counted it into both arms and amplified geometrically
  with depth (each fork's measured span contained its children's
  already-inflated spacing): a depth-3 program's outer arm measured 149 units
  laterally and rendered at 7760x3800, against ~1500x1260 once the term was
  removed.

  The drawable boundary is now depth 5 (see the depth-4 entry below for how
  depth 4 fell), and the invariant that survives is the
  original one, unchanged in substance: when the layout genuinely runs out of
  room it fails loudly at render time rather than misdrawing. That remains
  load-bearing for the reason it always was -- with `_self_approaches`
  disabled, an undrawable program renders happily and then fails `extract()`
  with ~21000 unaccounted pixels, i.e. it draws self-crossing garbage.
  `TestNestingDepthLimit` pins that invariant directly now, with
  `_MAX_PADDING_DOUBLINGS` throttled to 0 so exhaustion is reached in under a
  second: the assertion is about *what happens when the router gives up*, not
  how long it searches first. That change alone took the three suites from
  ~141s to ~4s, since the old test spent 2.5 minutes reaching its raise.

  **Why depth 4 fails, measured rather than assumed.** Every previous version
  of this entry described its own nesting ceiling as "a genuine lack of drawn
  space", and was wrong about that twice running (depth 3 fell to measured
  spacing plus two-phase routing, neither of which this file predicted). So
  depth 4 was instrumented before being characterised, on
  `+[>+[>+[>+[>+<-]<-]<-]<-]>>>>.`:

  - The failure is uniform, not marginal: the third of four loop-backs
    reports 154 "no corridor exists at any padding" and **0** "route folded
    back on itself", so `_self_approaches` and routing quality are not
    involved at all.
  - It is not a padding limit. Padding doubles to 256 cells against a drawing
    whose entire bounding box is ~80x66 cells, so the search area covers the
    drawing many times over long before it gives up.
  - It is not detour ordering. Outermost-first, innermost-first and plain
    layout order all fail at the same detour.
  - It is not the coarse pass's granularity, which was the leading hypothesis
    (`_route_legs`'s first pass steps a whole `_UNIT` = 20 cells, and can
    therefore only turn ~4 times across a drawing this size). Re-running the
    failing detour with a *pixel-exact* `step=1` A* over the whole bounding
    box routes **0 of its 22 otherwise-viable candidates**, so the coarse
    lattice is not what blocks it.
  - It is genuine enclosure. A flood fill from the failing detour's own
    start, using the router's own clearance rule, reaches only **1219 of 7872
    cells (15%)** -- and only 2096 even with clearance ignored entirely, so
    this is not `_CLEARANCE` being too strict either. The detour's departure
    point is sealed into a pocket by fixed geometry plus the two detours
    already routed.

  The mechanism is that **detours are far bigger than the program they
  serve**: fixed geometry for this program is 215 cells, and the first two
  detours add 117 and 182 more, nearly tripling the ink before the third is
  attempted. Each threads through the middle of the drawing and blocks a
  3-cell-wide swath (its own width plus `_CLEARANCE` either side), so the
  drawing is only 28% blocked overall while still being cut into disconnected
  pockets.

  That makes this a *layout* problem rather than a router problem, and the
  fix is to stop detours needing to cross the drawing at all -- reserve
  routing corridors for `goto`-carrying arms during layout, sized from
  measurement now that `_subtree_extent` exists (an unmeasured `_GOTO_CHANNEL`
  constant was tried during the depth-3 work and removed as a guess; the
  numbers above are what it lacked). Note this was the first time the ceiling
  had a measured mechanism rather than an assumption, so it was also the
  first time the next step was pointed at something specific.

  **Depth 4 fell to that fix -- plus two more the corridors uncovered.** The
  diagnosis above was right about the layout half and incomplete about the
  rest: reserving corridors turned the enclosure into two successive
  route-vs-route failures that only became measurable once routes existed at
  all. Each was instrumented the same way before being touched, and each fix
  is sized from the router's own rules rather than chosen:

  - *Corridors* (`_arm_spacing`): each arm now reserves one
    `_GOTO_CORRIDOR = 1 + 2*_CLEARANCE` = 3 cells per `goto` beneath it (the
    dead `_has_goto` helper became `_count_gotos`), the exact swath a routed
    detour blocks. The floor-of-5 arms above became 8/11/21/28 on this
    program, and the failing detour's flood-fill reach went from **5% to
    92%** -- enclosure gone, fixed geometry 215 -> 263 cells. A goto-free arm
    gets exactly `+0`, so loop-free programs render pixel-identically.
  - *Coarse-candidate misselection* (`_route_legs`): with routes now
    existing, every offset still failed -- as "route folded back onto
    itself". The coarse pass stops at whichever of its 5 candidate endpoints
    is cheapest *from the start*, and the start's own column happened to
    align with the candidate one coarse step left of the target: 40 cells
    straight up, on the wrong side of a wall, and the fine pass came back
    down through the coarse leg's own cells (one cell visited twice). Two
    recoveries, neither touching the success path: exclude the reached
    candidate and re-run the coarse pass (rescues long hauls cheaply), and
    when no candidate yields a clean route, a pixel-exact A* over the same
    padded bounds -- a 3-cell corridor holds exactly one clear line, which a
    20-cell coarse edge anchored to the start's lattice threads only by
    alignment luck, and the pixel pass threads by construction (measured:
    ~0.05s where the split failed outright).
  - *Doorstep sealing* (`_route_pending`): the depth-3 detour then routed
    fine -- and its pixel route, hugging ink at exactly `_CLEARANCE`, parked
    across the first depth-4 detour's departure point, boxing it into an
    **8-cell pocket** out of a ~28000-cell canvas (attribution: that one
    route alone). Reserving a `_GOTO_CORRIDOR`-radius block around each
    unrouted detour's start as *hard* occupancy failed one detour later --
    the two depth-4 doorsteps sit a column apart and one's only lane runs
    through the other's ring (152 reachable cells hard vs 1086 without). So
    the blocks are *costed* instead (`_AVOID_PENALTY` = `_UNIT` per
    trespassed cell): doorsteps stay clear whenever an alternative exists,
    and the unavoidable crossing happens on the shortest chord. Measured on
    the shipped path: all four detours route (+138/+173/+115/+32 cells),
    three of them trespassing zero avoid cells, and the boxed-in one paying
    exactly a 7-cell chord past the last doorstep at distance 3 -- on a side
    the sealed-in detour's own route never needs.

  Ordering experiments confirmed outermost-first still holds: innermost-first
  let a depth-4 detour's 55-cell westward sweep seal the depth-3 doorstep
  (629-cell pocket), the mirror image of the failure it was meant to avoid.

  Depth 4 now renders in ~1s and round-trips to `[1]`, pinned as a real
  round-trip in `TestNestingDepthLimit` exactly as its docstring prescribed;
  the exhaustion raise is repinned on depth 5, which still exhausts at *full*
  padding -- in ~5s, where the corridors-only intermediate state (layout
  fixed, router untouched) ground for ~7 minutes before raising and the
  committed pre-fix baseline took ~2.5 minutes, since the pixel fallback
  proves a pocket empty quickly instead of letting the coarse pass thrash.
  Depth 1-3 grew modestly and linearly (900x740 -> 960x740, 1020x840 ->
  1140x960, 1500x1260 -> 1800x1100), so the corridor term is not compounding
  through nested extents. The ceiling moved, and the invariant survives
  unchanged: when the layout genuinely runs out of room it says so at render
  time.

  **Why depth 5 fails, and why the next soft-cost patch does not fix it.**
  Instrumented the same way on `+[>+[>+[>+[>+[>+<-]<-]<-]<-]<-]>>>>>.`
  (fixed geometry 368 cells, ~86x135-cell canvas, 5 detours): the first two
  detours route (+179, +228 cells), and the third -- the same
  depth-4-targeting detour that used to fail one program earlier -- is
  sealed by the depth-3 detour's 228-cell route alone: its reachability is
  96% against fixed ink, 91% after the first route, **5%** after the
  second, with all 22 of its viable landing points unreachable. Same
  disease as before, one level up: doorstep costs protect a departure
  *point*, but nothing protects the *lane* between a pending detour's start
  and its stem, and an earlier route can cut that lane anywhere along its
  length.

  The obvious escalation was measured and rejected: extending the soft
  `avoid` regions from doorstep blobs to each pending detour's whole
  start-to-stem rectangle (inflated by `_GOTO_CORRIDOR`) leaves depth 4
  rendering identically and depth 5 and 6 still failing. Mechanically that
  is expected in hindsight -- a soft cost steers a route among alternatives
  *that exist*, but when every route for a big outer detour must cross the
  inner lane somewhere, it pays the toll and crosses, and a paid crossing
  cuts the lane exactly as thoroughly as a free one. Costing has hit its
  structural limit: the failure is that routes are free-form at all.

  The structural way out: nested loop-backs are topologically nested, so
  loop `k`'s detour can run as a ring just outside loop `k`'s own subtree
  and inside loop `k-1`'s ring, never crossing by construction -- the
  lateral space `_arm_spacing`'s corridor term reserves is exactly the
  annulus such a ring occupies. That is what landed, as a *constraint* on
  the existing A* rather than a replacement for it, and every piece of the
  picture was measured before being built (the depth-4 record above having
  shown unmeasured geometric intuition here wrong twice):

  - *Departure*: every detour's start sits exactly on its own subtree's
    bounding-box perimeter -- measured `start->edge=0` for all detours at
    depths 3-7, so a route fenced out of the box interior can leave at all.
    The boxes themselves are recorded during the real layout from the
    strokes actually laid (`_layout`'s new `boxes` dict), not reconstructed
    geometrically, for the same anti-drift reason `_subtree_extent`
    dry-runs the real layout.
  - *Landing*: the target stem sits 17-29 cells *inside* the box (arm
    content reaches back around it), so a pure annulus reaches 0 of its
    approach points. But an ASCII dump of the strip along the stem's own
    line showed it empty except the trunk -- the clearance `_arm_spacing`
    already guarantees around the trunk axis -- so the fence keeps a
    stem-aligned landing strip open (`_STRIP_HALF_WIDTH` =
    `_DIAGONAL_APPROACH + _CLEARANCE + 1`, sized so an approach point's own
    clearance never touches the fence). One measurement mid-way here was
    wrong twice over an inverted direction map in the experiment itself --
    the "0/30 approaches reachable for outer detours" runs were the bug,
    not geometry, which the strip dump exposed.
  - *Stacking*: inner and outer boxes share edges, and whichever ring
    routes the shared band first starves the other -- measured in both
    orders (outermost-first starved the inner ring at depth 5,
    innermost-first starved the outer one even at depth 3). Soft shell
    costs resolve it: each ring pays `_AVOID_PENALTY` within
    `_GOTO_CORRIDOR` of its own box per *deeper* pending detour, so shallow
    rings ride out and deep rings hug, onion-style.
  - *Fallback*: a detour whose constrained attempt fails routes free, as
    before -- the fence is capacity, not correctness, and the innermost
    detour of a deep program (nothing deeper left to seal, tiny free
    route) uses exactly that path.

  Depths 5 and 6 now render and round-trip to `[1]` (~1.6s and ~10s; depth
  5 is pinned in the test suite, depth 6 left unpinned only for suite
  runtime). The ring-constrained router's own ceiling was depth 7, where
  the third (depth-4) detour exhausted both its constrained attempt and its
  free fallback -- congestion in the middle of the onion.

  **Arbitrary depth, by removing the search.** The depth-3 -> 4 -> 5 -> 7
  progression was itself the finding: every routing fix bought a level or
  two and exposed the next congestion, because *search-based* routes
  compete for space globally. The scheme that ends the series
  (`_loop_return_legs`) constructs each loop-back deterministically from
  measured geometry instead of searching for it, resting on two facts:

  - A compiled brainfuck `goto` always ends its own fork's body chain
    (`bf_to_line`'s `_control_tail` guarantees it), so at the `goto` the
    fork's stem, arm and measured body extent are all known, and the return
    path is a pure function of them: step off the body's end (measured to
    sit on its box perimeter at every depth tried), ring the body's
    bounding box at `_RING_OFFSET`, ride the bay that `_arm_spacing`'s
    floor-plus-corridor term already guarantees is >= 8 wide, and land
    mid-stem with the same diagonal the router used. The ring always enters
    the bay via the rear corner because the arm stroke pierces the bay line
    at the arm's own axis -- crossing it would draw a spurious 4-way
    junction.
  - The construction is drawn in `_subtree_extent`'s dry runs too (a dry
    run knows every *nested* fork's geometry; only the subtree's own
    outermost return belongs to the caller's frame, which is exactly where
    the extent semantics want it). So every parent's measured extent
    *contains* its children's return paths, and the same recursion that
    reserves room for child content reserves room for child rings -- at
    every depth, with nothing left to collide. This is the piece no routed
    scheme could have: a route found after layout can never be seen by the
    measurements that decide the layout.

  Depths 1 through 12 render and round-trip to `[1]` (verified against an
  independent brainfuck interpreter on nested, sequential-sibling,
  tail-after-inner-loop and input-driven loop shapes as well). Rendering is
  ~10ms at *any* depth -- the search-based versions took 1.6-10s for depths
  5-6 -- and image sizes grow linearly. Depth 8 is pinned in the suite as
  the deep representative.

  **The router is deleted, not retired.** It briefly survived as a fallback
  for hand-built graphs outside the compiled invariants, but a fallback
  that no compiled program can reach is ~800 lines of dead weight with its
  own constants, caches and failure modes to keep coherent -- so the whole
  search stack (`_astar`, `_route_legs`, `_close_loop`, `_route_pending`,
  `_self_approaches`, clearance-checked edge search, padding doublings,
  soft costs, ring fences, subtree `boxes`) is gone. A `goto` whose return
  path cannot be constructed now raises immediately at `_layout` time --
  the "fails loudly rather than misdraws" invariant, preserved as a direct
  raise instead of a router exhaustion, and pinned by forcing the
  construction to decline in the test. The drift guard (an overlap check of
  the constructed legs against real ink) is what backs the raise for
  hand-built graphs that pass the geometric premises but collide anyway.
  What survives of the routing era: `_CLEARANCE` (the stroke-separation
  invariant, still pinned by `TestStrokeSeparation`), `_GOTO_CORRIDOR` (now
  the bay-width guarantee in `_arm_spacing`), `_DIAGONAL_APPROACH` (the
  merge-vs-fork landing rule, rationale moved onto the constant), and
  `_leg_cells` (the guard's cell walker).

- **Output compactness vs. the wiki's own drawings, and what is irreducible.**
  Prompted by a direct comparison: `bf_to_line.py` on the wiki's own addition
  algorithm (`,>,[-<+>]<.`, exactly what `fixtures/addition.png` draws by
  hand) produced a 2300x980 image against the fixture's 300x300 -- ~25x the
  area for the same program.

  Most of that was one oversized constant. `_BRANCH_SPACING` was 20, and
  every fork's arms are `_BRANCH_SPACING * 2**remaining` grid units of pure
  connective spacing before any content is laid out; because the loop-back
  detour then has to route *around* those arms, the detour scales with them
  too. Sweeping 20/8/5/3/2/1 with every program in all three suites
  re-rendered and re-executed at each value showed all of them still correct
  at every value tried -- including the n=2/n=3 boolean decision trees the
  constant's own comment credited with pinning it, which turn out not to pin
  it at all. At 5: addition goes 2300x980 -> 1100x980 (~2.1x less area) and
  the n=3 majority decision tree 9180x3920 -> 3180x1740 (~6.5x), for
  identical program output (the drawings differ, of course -- what is
  unchanged is what they compute).

  5 rather than lower because the floor was, at that point, set by *which
  failure mode* you get rather than by whether tested programs still work: at
  3 and below, an undrawable three-level program stopped raising at render
  time and instead misdrew, caught only downstream by `extract()`'s coverage
  check (~3200 unaccounted pixels) -- strictly worse than a loud refusal.

  **That constant is no longer what does the work**, and lowering it was only
  ever the cheap half of the answer -- worth being explicit about, since
  "shrink everything uniformly" is not a layout improvement, it is a scale
  change. Replacing `_fork_depth`'s `2**remaining` with measured extents and
  moving detour routing to a second phase (see the nesting entry above) is the
  real fix, and it is separable from the constant: re-rendering at the
  *original* `_BRANCH_SPACING = 20`, extent-based layout alone still beats the
  old fork-counting layout on every program tried -- addition 2300x980 ->
  1500x980, and the n=3 majority tree 9180x3920 -> 3620x1740 (~5.7x less
  area). With both changes at 5, addition is 900x980 and the majority tree
  1820x1440. `_BRANCH_SPACING` is now a floor and margin, not a scaling law.

  **Parity with the hand-drawn fixture is not reachable, and not a bug.**
  After this change the remaining bulk of the addition drawing is the
  loop-back's rectangle, which is structural: a return path is
  cardinal-only (a diagonal leg risks being misread as a `+`/`-` kink)
  and `_CLEARANCE` mandates a gap from every existing stroke, so a loop-back
  must travel out and around. The wiki's hand drawing reconnects on a short
  immediate diagonal that passes directly alongside its own earlier ink --
  legal for a human drawing it, but exactly what `_CLEARANCE` exists to
  forbid, since `lattice._band_lit`'s ±1 lateral reach cannot tell a flush
  parallel stroke from a real junction. The other fixed costs are
  `_STEM_LEN` (10 units into every fork), `_DIAGONAL_APPROACH` (6 units, and
  pinned *above* `lattice.star`'s 15px probe, so not shrinkable much), and
  each opcode kink's own ~5-unit footprint; together these are why the
  addition drawing's *height* (980) barely moves with `_BRANCH_SPACING` at
  all, unlike its width.

  Untried second lever, deliberately left alone: `_UNIT` is 20 and the
  pipeline is documented clean at 16-28 (the floor being `lattice.star`'s
  hardcoded 15px probe -- see the grid-units entry above), so 16 would shrink
  every rendered output another ~20% linear / ~36% area. Not done here
  because it rescales every drawing this repo produces, which is a broader
  change than the compactness question that prompted this.

  **The constructed-loop-back dividend: the per-goto corridor multiplier is
  gone.** `_arm_spacing` reserved `_GOTO_CORRIDOR * count_of_gotos` per arm
  -- sized for the routing era, when `n` free-form detours could all cross
  one gap and each blocked a corridor of it. Constructed returns never
  share a gap that way: every nested loop-back rides its *own* fork's bay,
  and parents reserve room for it through the measured extent. Measured
  with the multiplier dropped to a flat `_GOTO_CORRIDOR` for any
  goto-carrying arm: every program on the depth ladder (2-10), the wiki
  addition program, 8x8 multiply and the heavy depth-3 case still
  round-trip; flat-loop drawings are pixel-identical; and nested areas
  shrink 17% at depth 4 to 44% at depth 10, the multiplier having
  compounded through nested extents exactly like the removal's savings do.
  The flat corridor is also the *minimum*, not a tuned value: the bay must
  fit the landing lane at `_DIAGONAL_APPROACH` = 6 plus `_CLEARANCE` on
  both sides = 8 = `_BRANCH_SPACING + _GOTO_CORRIDOR` exactly.
  (`_count_gotos` reverted to the `_has_goto` boolean it once was, the
  count having served only the multiplier.)

  Also measured, and deliberately not taken: `_STEM_LEN` has real slack
  (9 and 8 both round-trip everything with flat corridors), but the gain is
  under 3% of area against the corridor change's 17-44%, and the stem's
  length is part of what keeps the landing diagonal and `lattice.star`'s
  probe geometry comfortably apart -- slack serving robustness, not waste.

  **Now covered by `test_bf_to_line.py`**, the `bf_to_line.py`-driven suite
  through the real render -> extract -> simulate pipeline that WIP.md
  previously noted was missing: straight-line programs, single-level loops
  (kept as cover for the accident above becoming real behavior), the two
  nested cases (asserting on printed *output*, not just the final tape --
  asserting the tape alone would not have caught this regression at all),
  and `bf_to_line`'s own compile-time rejections. `test_simulate.py`'s
  hand-built cyclic `Stroke` trees still never exercise `render.py`'s
  loop-drawing geometry, which is why this separate suite is needed.

  **Reviewed and closed: the remaining hand-built fixtures are all
  load-bearing, and none should be deleted.** This entry previously flagged
  `test_simulate.py`'s hand-built `Stroke` fixtures as possible cleanup, on
  the grounds that `test_bf_to_line.py` now covers the loop-back mechanism
  through real drawings and some of them might only duplicate it at lower
  fidelity. Checked directly: whatever was genuinely redundant is already
  gone, and the two that remain each cover something a rendered drawing
  structurally cannot.

  - `_build_growing_loop` is a genuinely non-halting loop, asserted to
    actually hang (via `SIGALRM`, with a 1s timer) rather than silently
    returning a wrong tape. There is no way to route this through the render
    pipeline: it would require `[+]` or similar to render *and* a test that
    deliberately never terminates, which a round-trip assertion cannot
    express.
  - `_build_decrement_loop` covers `find_merge`'s *other* match branch. Its
    loop arm's final vertex lands exactly on the fork's own final vertex,
    whereas `addition.png`'s real merge -- and every merge `render.py` draws,
    via `_approach_points` -- lands strictly *inside* a segment. Those are two
    distinct code paths in `_compile`, and no real drawing reaches the first.
    It also carries the sibling-branch false-match regression (a bare vertex
    match once matched an untaken sibling arm, since every fork's children
    start exactly where the fork ends).

  The maintenance cost that motivated the flag was real but is not recurring:
  three fixtures needed updating when `lattice._classify`'s arm labeling was
  fixed, because they encoded the old inverted convention as literal
  geometry. That bug is now fixed at its source (see the fork-arm entry
  above), so the churn it caused was one-time. At ~20 lines each with
  docstrings stating why they exist, these are worth keeping as they are.

## Still open

- Real (camera/scan) photographs with genuine anti-aliasing, as opposed to
  the clean nearest-neighbor-scaled synthetic input `normalize_scale` was
  tested against. Anti-aliased edges could make the exact-integer scale
  detection (`round(ink/skeleton_length)`) land less cleanly.

## Deliberately out of scope

- **Not wired into the interpreter registry**: deliberate, per an earlier
  discussion -- Line has no text format, so it doesn't fit the
  `run(code, io)` convention every other language in `src/esolangs/` uses.
  Stays a standalone `extra/` tool.

- Dependency footprint: 4 undeclared deps (Pillow, numpy, scipy,
  scikit-image), informal by design matching how `extra/` keeps other
  subtrees' toolchains out of `pyproject.toml`. A ranked, tested plan for
  which would be easiest to replace with hand-rolled numpy is recorded as
  a comment block in `extract.py` just above the imports, if this is ever
  worth revisiting.

## Resolved

Kept for the reasoning trail: what the problem was, and what fixed it.
The three reverted `_walk_tree` attempts under the last entry are recorded
in detail so a future attempt does not re-derive or re-break them.

- **Resolved**: a program with a conditional turn (`?`) followed by further
  opcodes in either branch used to fail `extract()`'s coverage check under
  the old region-adjacency walker (confirmed on `main` before any of this
  session's changes) -- e.g.
  `Node("?", zero=chain("+","+"), nonzero=chain("-",">"))` renders but
  didn't round-trip via `extract()`'s old pixel-walker pipeline.  Now that
  `lattice.py`'s walker is wired into `extract()` in its place, this round-
  trips cleanly (confirmed: the old pipeline fails this exact case with 220
  unaccounted pixels; the new one succeeds and recovers `[+2]`/`[-, >]` on
  the two arms, matching the source `Node` exactly).

- **Resolved: the compression cliff and oversized scale do not compound --
  they counteract.** Tested directly on `fixtures/addition.png` across the
  cross product of 1x/2x/3x nearest-neighbour upscaling and JPEG quality
  95 down to 5, checking both that `extract()` succeeds and that the
  extracted program still computes `(3,2) -> 5`. At 1x the documented
  cliff reproduces exactly (clean through quality 34, fails at 32). At 2x
  it survives every quality tried, down to 5. At 3x it survives to quality
  10 and fails at 7. The reason is that the two failure modes pull in
  opposite directions: the cliff is JPEG block quantization erasing pixels
  out of a 1px-wide stroke, and upscaling widens the stroke enough that
  the same quantization can no longer erase it entirely. So the compound
  case is *easier* than the 1px case, not harder -- the opposite of what
  this entry assumed when it flagged the gap.

- **Historical, describes the now-removed region-adjacency walker** (kept
  for the reasoning trail; `lattice.py`'s walker, now `extract.py`'s only
  walker, does not have this gap): the wiki's own drawings use a "cursor
  merges into another line" convention (matching Lineanim3.4/11.1/11.2's
  documented rule) where two independently-drawn strokes can physically
  touch with no separating background at all -- confirmed on two
  `multiplication.png` branch arms, each ending at a plain corner turn
  that walks straight onto a different stroke's ink rather than a real
  halt. `_walk`/`_walk_tree`'s own branch-vs-corner logic
  (`_is_branch_pivot`) didn't detect this as anything special -- the
  walker just kept walking onto the other stroke's line, since there was
  no region-adjacency signal marking a merge apart from an ordinary corner
  *at the pixel the walker arrives at* (the merge only became a junction
  one step later, after a forced turn with no straight-ahead ink).
  `classify_ops` worked around this at its own layer (dropping a trailing
  call that turns out to be the path's literal last run), but
  `_walk_tree` itself never knew it had crossed into unrelated ink -- e.g.
  its returned path still included those extra pixels, and nothing
  stopped a caller from walking *further* along the merged-into stroke by
  mistake if `_walk`'s greedy continuation ever had a reason to keep going
  past where these fixtures happened to stop.  (`lattice.py` does not have
  this gap -- see "Settled and tested" above.)

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

  **Resolved in a later session, via a different approach than any of the
  three reverted attempts above**: rather than patching the greedy
  pixel-by-pixel walker with another local geometry signal, or the
  grid-template-matching approach originally proposed here (compute each
  opcode's exact expected pixel footprint at the current position/heading
  and check it against the image), the actual fix built and verified was
  simpler than either -- an 8-directions-per-vertex probe, with no per-
  opcode template shapes involved at all.  See "Settled and tested" above
  (`lattice.py`) for the full writeup: at every vertex, count how many of
  the 8 compass directions have a real segment leaving it (2 = ordinary
  bend, 3 = fork or merge, 4 = crossing), using a 3-pixel-wide band probe
  rather than a single exact-length ray to absorb both hand-drawn length
  slop and vertex-position imprecision in one check.  Verified clean
  against every vertex in both wiki fixtures, and against the
  previously-broken "`?` followed by more opcodes" synthetic case.  Now
  wired into `extract()`'s actual pipeline as its only walker (see
  "Settled and tested" above for the wiring details and the one additional
  bug -- `_resnap_dead_end` -- found and fixed in the process).
