# Line: settled vs. still open

`render.py`, `extract.py`, `simulate.py`, and `verify.py` implement a
program renderer, a pixel-based extractor, and a runtime interpreter for
[Line](https://esolangs.org/wiki/Line), an esolang whose spec is entirely a
set of hand-drawn curve images with no text format and no reference
implementation (tagged `Unimplemented` on the wiki). This file tracks
what's settled and tested vs. what's deliberately out of scope or
unverified, the way `docs/streetcode-wip.md` does for Streetcode -- the
module docstrings in `extract.py`/`render.py`/`simulate.py` carry the
settled, load-bearing reasoning; this file is for what isn't decided yet.

`test_simulate.py` is a real `pytest` suite covering `simulate.py`
(opcode basics, the zero/nonzero swap, both wiki fixtures across several
real inputs, and the synthetic loop-back mechanism, including a hang
check); `test_line_boolean.py` covers `line_boolean.py`'s generated
decision trees end-to-end (render -> extract -> simulate) for n=1 through
n=3 across every input combination; `test_bf_to_line.py` covers
`bf_to_line.py` through the same full pipeline, and is the only suite that
exercises `render.py`'s loop-drawing geometry (`_layout`/`_close_loop`/
`_route_legs`) at all -- see the nested-loop entry below for why that
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
    tree's `nonzero` field, and vice versa.  `simulate.py`'s `run` takes
    the walked `nonzero` child on a zero cell and `zero` on a nonzero cell
    to correct for this -- deliberately, not a typo (see `run`'s
    docstring).  Neither `lattice.py` nor `extract.py` needed to know
    which physical arm was "actually" zero vs. nonzero before now, since a
    one-time structural trace only needed *a* consistent label, not the
    *correct* one -- this only mattered once something needed to execute
    the branch correctly.
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
  simulate) for n=1 through n=4 across every input combination (identity,
  NOT, AND, XOR, 3-input majority, 4-input parity).  n=4 renders/extracts
  correctly but is slow (~16s to extract) with a canvas large enough to
  trip Pillow's decompression-bomb warning; n=5 would be impractical
  (roughly 35000x17000px), so practical use stops around n<=4 -- matching
  `esolangs.tools.boolean.tape.six_five`'s own documented n<=5 cap for an
  unrelated geometric reason, the same shape of problem.  Covered by
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
  isolation: without the diagonal approach 6 of `test_bf_to_line.py`'s 15
  tests fail, without the self-approach rejection 2 do. `_CLEARANCE`
  (between-stroke clearance, as opposed to the self-approach check that
  reuses it) is deliberately *not* claimed as pinned by a failing case --
  setting it to 0 currently leaves every test passing; see its own comment
  in `render.py` for why it is kept at 1 anyway.

  **Now covered by `test_bf_to_line.py`**, the `bf_to_line.py`-driven suite
  through the real render -> extract -> simulate pipeline that WIP.md
  previously noted was missing: straight-line programs, single-level loops
  (kept as cover for the accident above becoming real behavior), the two
  nested cases (asserting on printed *output*, not just the final tape --
  asserting the tape alone would not have caught this regression at all),
  and `bf_to_line`'s own compile-time rejections. `test_simulate.py`'s
  hand-built cyclic `Stroke` trees still never exercise `render.py`'s
  loop-drawing geometry, which is why this separate suite is needed.

## Deliberately out of scope

- **Not wired into the interpreter registry**: deliberate, per an earlier
  discussion -- Line has no text format, so it doesn't fit the
  `run(code, io)` convention every other language in `src/esolangs/` uses.
  Stays a standalone `extra/` tool.

## Unverified / lower priority

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
