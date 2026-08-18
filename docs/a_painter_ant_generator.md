# A Painter Ant boolean generator: construction notes

A working document capturing how the A Painter Ant boolean generator is
built, why it is cycle-stable, and the open plan for generalizing it past
two inputs.  This is meant to be read cold: it records everything we learned
so that the construction can be picked up again fresh.

## Language mechanics

A Painter Ant is a single ant on an infinite grid of black or white cells
(all black to start).  The commands are:

- `n`/`e`/`s`/`w` — move one cell in that direction **only if the
  destination is black**.
- `N`/`E`/`S`/`W` — move one cell in that direction **only if the
  destination is white**.
- `p` — paint the current cell black; `P` — paint the current cell white.

The program runs in an **implicit loop**: after the last instruction the
pointer returns to the first.  So a program's state (the ant's position and
the whole grid) is re-evaluated every cycle.

The wiki defines no I/O.  The interpreter's real output is the **bounding
box of visited cells** (a `#`/`.` raster), which carries no coordinates.
The boolean generator therefore reads its answer from a *semantic grid
model* (the ant's actual position and cell colours) rather than the
interpreter's box.

The interpreter ignores whitespace, so a **space** in a program is a no-op
that still occupies a position in the source.

## The answer convention

For the shipped generator, the answer is the **colour of the cell the ant
lands on** at the end of a cycle (white is one, black is zero).  This
differs from the older (removed) generator, which used the origin's colour.

## Why cycle-stability matters

Because the program runs in a loop, a valid generator must produce programs
whose behaviour is independent of how many whole cycles you run: the
interpreter's bounding-box output must be identical for `limit = len(prog)`
and `limit = 10 * len(prog)`.  Every instantiated program must be a
**cycle-stable fixed point**.

The hard part of A Painter Ant generator design is that a program is
origin-relative: its moves and paints are tuned to run from the origin on a
black grid.  But the ant *ends* a cycle at its output leaf, not the origin.
On cycle 2 the ant starts at the output, and the origin-relative setup
commands misfire — unless the program is designed so the cycle-2 run is a
no-op.

## The n = 2 construction (shipped)

The shipped generator is
`esolangs.tools.booleans.a_painter_ant`.  It builds a template:

```
Nnnww{f(1,1)}Wsseessee{f(0,0)}Ennwwnnee{f(1,0)}Esswwssww{f(0,1)}WnneeSsn
                                  {X0}
NwPnPwnPEsPwPswPWWePsPesPSSnPePeePNNsePSSnPePnePEEwPnPwnPNNsPwPsPwPS
                                  {X1}
```

where:

- `{f(a,b)}` is `P` for a one table entry and a **space** (left unpainted)
  for a zero.
- `{X0}` is `nn` for input bit 0 = 1, `ss` for input bit 0 = 0.
- `{X1}` is `WWwWWEEe` for input bit 1 = 1, `NENEESWw` for input bit 1 = 0
  (an 8-character east/west complement pair).

It supports **all sixteen two-input tables**, exact and cycle-stable
(verified on the interpreter, 1 vs 20 cycles, for all 64 instantiations).

**n == 1** is supported by fixing the padded least-significant input to
zero: the one-input table is padded to `[f(0), f(0), f(1), f(1)]` and the
n == 2 construction runs with `b1 == 0` (see `docs/walls.md`).  All four
one-input tables are exact and cycle-stable.

### The flow

1. **Head** — paints the four leaves (one per input combination, `P` for a
   one entry, space for a zero) at the corners of a 4x4 square, and returns
   to the origin.  The head also paints the two **crosses** that trap the
   cycle-2 ant (see below).
2. **`{X0}`** — routes the ant north (`nn`) or south (`ss`).
3. **Body** — a fixed 68-character funnel that re-paints the ring and
   funnels the ant to a canonical pre-`{X1}` routing point (for the north
   row this is `(0,-2)`).
4. **`{X1}`** — routes east or west onto the output leaf.

### Why it is cycle-stable: the cross trap

The crucial mechanism is a white **cross** painted around each output cell
(the actual 5x5 pattern, verified on the interpreter; `?` = the output
cell, `.` = white, `#` = black):

```
##.##
#...#
..#..
#...#
##.##
```

The four **orthogonal neighbours** of the output are white (the diagonals
are black).  On cycle 2 the ant sits at the output.  Every lowercase move
(`n`/`s`/`w`/`e`), which requires a **black** target, is **blocked** by a
white neighbour, so the ant cannot walk away.  This is what makes the ant
"settle at the output".

But stability is not just a static trap.  The program's first command is an
uppercase move, which *does* fire on the white cross, so the cycle-2 ant
performs a short **closed dance** out along the cross and back — traced
instruction by instruction, it returns to the output cell and **paints
nothing new** (all `P`s it executes re-confirm cycle-1 cells).  So the
bounding box is identical for every whole number of cycles.  (The earlier
note called this a "two-layer star" with a diamond shape and white
diagonals; the shipped construction is actually the cross above.)

### The "paint two crosses, don't re-embed the second input" insight

The construction does **not** paint one cross at every leaf.  It paints
**two** crosses — one for each possible value of the final input — so that
the final input does not need to be re-embedded or trigger any painting.
The final input just routes the ant to whichever cross is already painted.

In the n=2 grid (north row), the two crosses are centred at `(-2,-2)` and
`(2,-2)`: the `{X1}` input routes the ant to the left cross's output or the
right cross's output.  Both crosses are pre-painted, so `{X1}` only
*selects*.

### Monotone painting

The generator uses only `P` (paint white) — it never uses `p` (paint
black).  Zero leaves are left unpainted (a space).  This makes the white
cells monotone increasing: cycle 1 establishes them and every later cycle
only re-confirms a subset, which also helps stability.  (The earlier
attempt used `p` for zero leaves, which *reverted* cells to black non-
monotonically and broke stability — replacing `p` with a space was the fix.)

### The naive head fails — return paths must avoid painted cells

A first attempt at a head that just visits each leaf and returns to origin
fails: after painting a leaf white, a later lowercase move onto that white
cell is blocked, so the ant's actual path diverges from the intended one.
The working head returns through the origin (the black centre) and never
re-crosses a painted leaf.

## Work in progress: generalizing to n = 3

The **single-line leaf-paint draft below has been reconstructed and
verified**: it is **exact for cycle 1 for all 256 n == 3 tables x 8 inputs
(2048/2048)** on the interpreter semantics, but **not yet cycle-stable** —
cycle 2 diverges because the head is origin-relative and the ant starts
cycle 2 at the output leaf, not the origin (0/2048 cycle-stable).  The fix
under investigation is the n == 2 cross mechanism (see `docs/walls.md`,
which also records a separate search-found *box-height* method reaching
196/256 n == 3 tables).

The architecture to try:

### The flow (per the designer)

1. **Head** — paint the tree (8 leaves) and return to the origin.
2. **Route with the first n-1 inputs** (for n=3, `b0` and `b1`) to the
   output leaf.
3. **Paint the star** around that output.
4. **Route with the last input** (`b2`) to enter the star.

Note the difference from n=2: in n=3 the star is painted *at runtime* (after
the first two inputs route to the output), not pre-painted in the head.
**This runtime-star variant is now in doubt** — the n == 2 stability
mechanism (a pre-painted cross + closed zero-paint dance) requires the
cross to already exist on cycle 2, so a runtime-painted cross cannot trap
the re-run head (see "Cycle 2 is the blocker" below).  The leading
candidate is instead the single-line layout with **pre-painted** crosses.

### Axis assignment — make the last input east/west

Going north for the last input looked hard, so prefer to assign axes so the
**last input is always `w`/`e`**.  For n=2 the last input (`{X1}`) is
already east/west.  For n=3, assign:

```
b0 = n/s (weight 1)
b1 = w/e (weight 2)
b2 = w/e (weight 4)     <- last input is east/west
```

(One of several layouts; the superincreasing weights `1, 2, 4` guarantee
distinct leaves on each axis.  All of
`n/s,w/e,n/s` and `n/s,w/e,w/e` and `w/e,n/s,n/s` and `w/e,n/s,w/e` give 8
distinct leaves.)

### The "superincreasing weights" trick

To lay out 2^n leaves collision-free on a 2D grid, give input `i` weight
`2**i` on an alternating axis (`n/s` for even `i`, `w/e` for odd `i`).  The
net displacement is then a unique weighted sum — no two input combinations
share a leaf.  (The earlier `[n, n-1, ...]` weights collide at n >= 6;
powers of two do not.)

### The n = 3 head (verified working on cycle 1)

A head that visits the 8 leaves and returns to the origin is achievable.
Using the two-square layout (leaves at `(±2,±2)` and `(±6,±6)`), a head that
travels out to each leaf along the `x=0` column, paints it, and returns
through the origin works on cycle 1 (ends at `(0,0)`, all 8 leaves painted).

### Current draft: a single-line leaf-paint layout

The in-progress draft (see the "Work in progress" note above) uses a single
horizontal line of eight leaves at `(x, -2)`, `x` in
`{-28,-20,-12,-4,4,12,20,28}`.  Bit `i` contributes a signed east/west
move of weight `4*2**i` (`eeee`/`wwww`, `eeeeeeee`/`wwwwwwww`,
`eeeeeeeeeeeeeeee`/`wwwwwwwwwwwwwwww`), so the displacement is a unique
weighted sum and the ant reaches a distinct leaf per input combination.

The head paints the leaves monotonically (`P` for a one, a space for a
zero) and returns through the origin, crossing no painted cell: it paints
the negative leaves going west on `y = -2`, steps north to `y = -3` (the
clean return row), crosses east, paints the positive leaves going west
(including `+28` on arrival), then returns to the origin via `y = -3`.
This head was reconstructed and verified: it ends at `(0,0)` with all eight
leaves painted exactly per the table.

**Landing trick that makes cycle 1 exact for all tables (verified):** route
on the clean row `y = -1`, paint the ant's current cell `P`, then `n` —
the leaf at `(x, -2)` is one step *north* of the routing row.  If the leaf
is black (table 0) the lowercase `n` moves onto it and reads 0; if the
leaf is white (table 1) the `n` is blocked and the ant rests on the white
cell it painted, reading 1.  Either way the landing cell's colour equals
the table entry.  (An earlier note said "then `s`"; with the leaves at
`y = -2` that is direction-flipped — `s` would move away from the leaf.
The `s` variant works only if the routing row is the clean return row
`y = -3`, *above* the leaves.  Both verified combinations give 2048/2048
cycle-1 exactness.)

**Cycle 2 is the blocker:** the ant ends cycle 1 at the output leaf, not
the origin, so re-running the origin-relative head on cycle 2 diverges and
the bounding box changes (0/2048 cycle-stable).  The intended fix is the
n == 2 cross mechanism — but the cross must be **pre-painted** in the head,
because the n == 2 stability rests on the cycle-2 ant executing a *closed,
zero-paint dance* along the pre-painted cross back to the output (see the
cross-trap note above).  Pre-painting eight crosses and routing to the
right one is large, and the docs' "paint the star at runtime" variant is
unproven: a runtime-painted cross is not there when the cycle-2 head
re-runs, so the head would clobber or escape it.

### Open questions

- **The leading candidate**: pre-paint eight crosses (one per leaf) in the
  head, route with all three inputs to the correct leaf, and read the
  landing cell.  The single-line layout's leaves are 8 cells apart, so each
  cross's orthogonal arms (1-2 cells long) fit without overlapping.  How
  does the routing reach the leaf *through* the pre-painted crosses without
  being blocked (lowercase moves need black targets, but the crosses are
  white)?
- How exactly do `b0` and `b1` route to the output before the star is
  painted (if the runtime-star variant is pursued)?
- Does the "paint one cross per final-input value, not per leaf" insight
  (2 crosses for n=2) scale to n=3 — e.g. pre-painting 2 crosses and
  routing the first two inputs to the right one?
- Can the whole n=3 program be made cycle-stable for all 8 leaves × 256
  tables?

## Design principles (reusable summary)

1. **Monotone painting** — use only `P`; represent a zero leaf as a space
   (unpainted), never `p`.  Non-monotone `p` reverts cells and breaks
   stability.
2. **Cross containment, pre-painted** — paint a white cross (4 orthogonal
   neighbours white, diagonals black) around an output **in the head** so
   the cycle-2 ant (which uses black-requiring lowercase moves) is blocked
   from walking away.  The cross must pre-exist for cycle 2: stability is a
   *closed, zero-paint dance* along it, so a runtime-painted cross is not
   usable.
3. **Paint one cross per final-input value, not per leaf** — the final input
   just routes to a pre-painted cross; it never re-embeds or re-paints.
4. **Return through the origin** — head paths back to the origin must avoid
   re-crossing painted cells (which block lowercase moves).
5. **Superincreasing weights** — give input `i` weight `2**i` on an
   alternating axis for a collision-free leaf layout.
6. **Make the last input east/west** — north routing for the final input is
   awkward; put it on the east/west axis.
