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
closed, zero-paint dance back to the output.

## The star

The atom of the construction is the **two-layer star** painted around a
center cell (the output leaf): the eight **ring cells** at distance 1 and
the four **axis cells** at distance 2 are painted white:

```
  W
 WWW
WW?WW      ? = the center (the leaf, black or white per the table)
 WWW
  W
```

The star's white cells are what make the cycle-2 dance possible: every
lowercase move from a ring cell is **blocked** (its target is white), and
every uppercase move fires onto the ring.  The four "safe" moves from a
ring cell are exactly the directions the star covers with white:

- from the **top-middle** cell (north of the center), north/west/east are
  blocked (the N-axis cell and the ring's top row) — only **south** points
  back at the output;
- from the **middle-left** cell (west of the center), north/south/west are
  blocked (the ring's left column and the W-axis cell) — only **east**
  points back at the output.

A move that points back at the output **splits the ants**: the black-output
ant moves onto the leaf while the white-output ant stays on the ring.  So
the dance never moves leafward from the top-middle or the middle-left —
except for the one `Ssn` synchronizer, which is designed for exactly that
case (see below).

## The n = 2 construction (shipped)

The shipped generator is
`esolangs.tools.booleans.parameterized.a_painter_ant`.  It builds a template:

```
Wnnww{f(1,1)}Nsseessee{f(0,0)}Ennnn{f(1,0)}Esswwssww{f(0,1)}WnneeSsn
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

**n == 1** uses a two-leaf head with the same star body and the same
final-input routing:

```
Nww{f(1)}Weee{f(0)}EwwSsn
                          {X0}
NwPnPwnPEsPwPswPWWePsPesPSSnPePeePNNsePSSnPePnePEEwPnPwnPNNsPwPsPwPS
```

All four one-input tables are exact and cycle-stable.

### The flow

1. **Head** — paints the leaves (one per input combination, `P` for a one
   entry, space for a zero) and returns to the origin.
2. **`{X0}`** — routes the ant north (`nn`) or south (`ss`) to the output
   row, at the canonical point `(0,-2)` or `(0,2)`.
3. **Body** — paints the two stars and returns the ant to `(0,±2)`.
4. **`{X1}`** — routes east or west onto the output leaf.

### The two-star body (generated)

The body (`_body()`) paints **two stars**: one around the output leaf and
one around its **y-mirror**, so the final input never has to be re-embedded
— it only routes to whichever star is already painted.  The two stars share
the cell at `(0,±2)` (the right axis cell of the west star and the left
axis cell of the east star), which is also the canonical point the body
starts and ends on.

Each star is walked as a **clockwise spiral** of `P` paints: the east ring
cell first, then the ring steps and L-shaped detours out to the axis cells,
with blocked-uppercase returns from the axis cells (the `E`/`WW`/`SS` no-ops
are the anchors of the cycle-2 dance).  The two spirals are connected by
the **black gap** between the stars' rings: the star centers are four cells
apart and each ring reaches one cell toward the other, so the gap is
`4 - 2` east moves on the row above.  The west star's spiral ends on its
south-east diagonal, the gap runs east, and the east star's spiral (its
mirror) ends on the shared cell.

### The cycle-2 dance

On cycle 2 the ant starts at the output leaf, inside its star.  The head's
uppercase prefixes fire it onto the ring and the legs are no-ops (every
target is a white star cell), so the whole head+body+routing re-run is a
closed walk that returns to the leaf painting nothing new.  For n == 2 the
dance circuit is:

```
leaf -W-> middle-left -N-> NW diag -E-> top-middle -E-> NE diag
     -W-> top-middle -S/s-> leaf
```

The n == 1 circuit is `leaf -N-> top -W-> west diag -E-> top -S/s-> leaf`.
The circuits deliberately use **both** the top-middle (horizontal flow) and
the middle-left (vertical flow): a leg dancing on the top-middle (`nnnn`,
`nnee`) never moves south, and a leg dancing on the middle-left (`nnww`)
never moves east — the two leafward directions that would split the ants.

The **`Ssn` synchronizer** is the one leafward move, and it works because
it is a *dual*: `S` fires a white output onto the leaf, while a black
output blocks it and then `s` moves onto the leaf.  Either way the ant
returns to the output, and the `n` is a no-op.  The same dual appears in
the `{X1}` routing's final move.

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

The **single-row construction** is built by `_head`/`_body`: eight leaves
on one row at `y = -2`, `x = ±2 ±4 ±8` in `{-14,-10,-6,-2,2,6,10,14}` —
four cells apart (so adjacent stars share their axis cells) and
**symmetric across the y-axis** (so the star body's mirror trick works).
The head walks the row west painting the leaves, detours north to the
clean row `y = -3`, crosses east, walks the row west again, and returns to
the origin.  Every input routes east/west by its weight (2, 4, 8) on the
body-painted routing row `y = -1` with uppercase moves (they fire on the
painted cells), and the **landing trick** reads the leaf: paint the
routing cell `P`, then `n` — a black leaf lets the `n` move onto it
(read 0), a white leaf blocks it so the ant rests on the painted cell
(read 1).

This is **exact for cycle 1 for all 256 tables x 8 inputs (2048/2048)** on
the interpreter semantics, but **not yet cycle-stable** (0/2048) — cycle 2
diverges because the head is origin-relative and the ant starts cycle 2 at
the output leaf, not the origin.

**The blocker:** a leg can only be a cycle-2 no-op if every one of its
targets is white, and the leaves bound the white runs: the head's legs
between leaves are four moves long, but the longest run of white cells on
a row is three (the leaves themselves break the runs).  So the dance
cannot simply re-run the head.  The intended fix is the n == 2 star
mechanism: pre-painted stars plus a closed zero-paint dance, with only the
`S/s`-style dual allowed to move leafward.  The body currently paints only
the routing row (not the full stars); painting the full stars and the
connecting white runs, and designing the legs so they are no-ops from the
ring cells, is the open work.

### Open questions

- Can the n == 3 dance be made closed for all 8 leaves x 256 tables?  The
  n == 2 circuits were tuned per geometry; the n == 3 layout has four
  mirror pairs of leaves, four cells apart.
- The cycle-2 legs would run from the ring cells of the output's star;
  their targets must be white.  Does the y-axis symmetry let the legs'
  targets use the *mirror* star's cells (painted by the body) so the legs
  can be longer than the output star alone allows?

## Design principles (reusable summary)

1. **Monotone painting** — use only `P`; represent a zero leaf as a space
   (unpainted), never `p`.  Non-monotone `p` reverts cells and breaks
   stability.
2. **Pre-painted two-layer stars** — paint the ring (distance 1) and axis
   (distance 2) cells around each output in the body; stability is a
   *closed, zero-paint dance* on the star, so a runtime-painted star is not
   usable.
3. **Paint one star per final-input value, not per leaf** — the final input
   just routes to a pre-painted star; it never re-embeds or re-paints.
4. **The ring rule** — from the top-middle, only north/west/east follow
   safely; from the middle-left, only north/south/west.  A leafward move
   (south from the top-middle, east from the middle-left) splits the ants:
   the black-output ant returns to the leaf while the white-output ant
   stays on the ring.  Use both ring cells so the flow direction always
   matches, and let only an `S/s`-style dual move leafward.
5. **Gap calculation** — the black moves between two stars are the center
   distance minus 2 (each ring reaches one cell toward the other).
6. **Return through the origin** — head paths back to the origin must avoid
   re-crossing painted cells (which block lowercase moves).
7. **Superincreasing weights** — give input `i` weight `2**i` on an
   alternating axis for a collision-free leaf layout.
8. **Make the last input east/west** — north routing for the final input is
   awkward; put it on the east/west axis.
