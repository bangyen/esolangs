# A Painter Ant boolean generator: design history

Why the A Painter Ant boolean generator is built the way it is, and what
was tried and rejected along the way — including why the construction is
cycle-stable for **every input count**, which is the constraint that drove
every design decision here.  The shipped generator is
`esolangs.tools.boolean.a_painter_ant.a_painter_ant`.

For the language's mechanics (the conditional moves, the paints, and the
implicit loop), read the interpreter module's docstring; it is
authoritative and this document does not restate it.  Two consequences of
those mechanics matter throughout:

- The wiki defines no I/O, and the interpreter's output is the **bounding
  box of visited cells** (a `#`/`.` raster), which carries no coordinates.
  The generator therefore reads its answer from a *semantic grid model*
  (the ant's actual position and cell colours) rather than the box.
- The interpreter ignores whitespace, so a **space** is a no-op that still
  occupies a position in the source — which is what lets a zero leaf be
  represented by leaving it unpainted.

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

The generator builds a template for any arity; for n == 2 (XOR):

```
N WSssssNEwwPeeWSnnnnNE WSnnnnNEeePwwWSssssNE Ssn
                                                  {X0}
NwPnPwnPEsPwPswPWWePsPesPSSnPePeePNNsePSSnPePnePEEwPnPwnPNNsPwPsPwPS
                                                  {X1}
```

where:

- Each `WS{vert}NE{horiz}P{back}` block is the head walking **piecewise**
  to that leaf by its input bits: `WS`/`NE` are the cycle-2 anchors, the
  weighted n/s and w/e moves reach the leaf, `P` paints it white for a one
  entry (a **space**, left unpainted, for a zero), and the reversed path
  returns to the origin.
- `{X0}` is the first input's weighted move (`ssss`/`nnnn` for n == 2), `{X1}`
  is the final input's `WWwWWEEe`/`NENEESWw` landing dance.

It supports **all sixteen two-input tables**, exact and cycle-stable
(verified on the interpreter, 1 vs 20 cycles, for all 64 instantiations).

**n == 1** uses the same construction with a single bit; **n >= 3** uses the
same piecewise head with more bits, and every arity is exact and
cycle-stable (see "The general construction" below).

### The flow

1. **Head** — walks out to each white leaf by its bits, paints it (`P` for a
   one entry, space for a zero), and returns to the origin.
2. **`{X0}..{Xn-2}`** — the first `n-1` inputs each route the ant by their
   weight (`2 ** (n-i)` cells along the index-parity axis, west/north for a
   one bit, east/south for a zero) to the canonical point beside the output
   leaf's star.
3. **Body** — paints the two stars around the ant's position and returns it
   to the shared cell.
4. **`{Xn-1}`** — the final input's `WWwWWEEe`/`NENEESWw` dance closes the
   walk onto the output leaf.

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
`WS`/`NE` uppercase anchors fire it onto the ring and the weighted legs are
no-ops (every target is a white star cell), so the whole head+body+routing
re-run is a closed walk that returns to the leaf painting nothing new.  The
rule that makes the anchors safe is the **ring rule**: from the top-middle
cell only north/west/east follow safely (south points back at the leaf and
would split the ants), and from the middle-left only north/south/west
(east points back at the leaf).  The anchors and the `Ssn` ending are
chosen so a leafward move only ever comes from the `S/s` dual.

The **`Ssn` synchronizer** is the one leafward move, and it works because
it is a *dual*: `S` fires a white output onto the leaf, while a black
output blocks it and then `s` moves onto the leaf.  Either way the ant
returns to the output, and the `n` is a no-op.  The same dual appears in
the `{Xn-1}` routing's final move.

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

## The general construction (any n)

The piecewise head generalizes the n == 2 construction to every arity, and
every instantiated program is a cycle-stable fixed point.

### The piecewise head

The head walks each white leaf out and back **piecewise** — one weighted
move per input bit, most-significant first.  Bit ``k`` contributes
``2 ** (n-k)`` cells on the axis chosen by index parity (``k % 2 != n % 2``
-> horizontal, else vertical); a set bit moves west/north, a cleared bit
east/south (``_bit_move``).  The routing walks the same moves, so the head
and the read-back always agree on where each leaf is.

- The outbound path never crosses a previously painted leaf: the
  intermediate cells (the partial-bit prefixes of each path) are never
  leaf positions, so only the final cell — the leaf itself — is painted.
- After ``P`` the head retraces the exact same path back to the origin
  (``_reverse_moves``), so it returns cleanly without re-entering any
  painted cell.

For ``n >= 2`` each move segment carries an uppercase **anchor** — ``WS``
before an n/s segment, ``NE`` before a w/e segment — plus a move-less
leading ``WS`` when ``n`` is odd.  These are the cycle-2 launchers: on the
empty first cycle they are blocked (no-ops), and from cycle 2 on they fire
the ant off the leaf onto the painted ring, turning the whole re-run into
a closed zero-paint dance back to the leaf.

### The flow (any n)

1. **Head** — walks out to each white leaf by its bits, paints it, and
   returns to the origin.
2. **``{X0}..{Xn-2}``** — the first ``n-1`` inputs each route by their
   weight (``2 ** (n-i)`` cells, west/north for a one bit, east/south for
   a zero) to the canonical point beside the output leaf's star.
3. **Body** — paints the two stars around the ant's position and returns
   it to the shared cell.
4. **``{Xn-1}``** — the final input's ``WWwWWEEe``/``NENEESWw`` dance
   closes the walk onto the output leaf.

### Verification

The construction is verified cycle-stable and exact: every ``n <= 3``
table exhaustively (all 256 three-input tables x 8 inputs), and ``n == 4``
through ``n == 7`` sampled plus structured and constant edge tables.  The
semantic-grid model (the test suite's ``a_painter_ant_trace`` helper)
reports no divergence anywhere: every cycle-2 move stays in the cycle-1
box, no paint changes a cell's colour, the landing colour is stable, and
cycles 2 and 3 are identical.

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
9. **The landing dual must run from a ring cell, never the leaf** — the
   leaf's neighbours are white ring cells, so any uppercase move in the
   text that runs from the leaf on cycle 2 fires.  End the body dance on a
   ring cell and let a fixed mixed-case `Ssn`-style closing walk (n == 2's
   `{X1}`) carry the ant onto the leaf, on every cycle.
10. **Keep cycle-2 starts unique** — a colour-dependent landing (leaf for a
    zero, a ring cell for a one) gives the head two different cycle-2
    starts and no single dance works from both.  The ant must land on the
    leaf for both colours.
11. **Route on the clean rows** — lowercasing the routing is the only way
    to keep it a cycle-2 no-op from the leaf, so it must fire on black
    cells: route north/south or east/west on rows the body never paints
    (`y = -3`, `y = -4`) rather than on the white routing row.
