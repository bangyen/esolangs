# A Painter Ant boolean generator: design history

Why the construction is cycle-stable for **every input count**, the
constraint that drove every design decision here.  Shipped generator:
`esolangs.tools.boolean.a_painter_ant.a_painter_ant`.

Language mechanics (conditional moves, paints, implicit loop) are in the
interpreter module's docstring, authoritative and not restated here.  Two
consequences matter throughout:

- The interpreter's output is the **bounding box of visited cells** (`#`
  white / `.` black, ant's cell as `@` or `o`), which carries no
  coordinates, so the generator reads its answer from a *semantic grid
  model* (the ant's actual position and cell colours) instead.
- Whitespace is a no-op that still occupies a position in the source —
  which is what lets a zero leaf be represented by leaving it unpainted.

The answer is the **colour of the cell the ant lands on** at the end of a
cycle (white is one, black is zero).

## Why cycle-stability matters

A valid generator must produce programs whose behaviour is independent of
how many whole cycles run: the interpreter's bounding-box output must be
identical for `limit = len(prog)` and `limit = 10 * len(prog)`.  Every
instantiated program must be a **cycle-stable fixed point**.

The hard part: a program is origin-relative — its moves and paints are
tuned to run from the origin on a black grid — but the ant *ends* a cycle
at its output leaf.  On cycle 2 the ant starts at the output, and the
origin-relative setup commands misfire, unless the cycle-2 run is a
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
every uppercase move fires onto the ring.  A move that points back at the
output **splits the ants**: the black-output ant moves onto the leaf while
the white-output ant stays on the ring — so the dance never moves leafward
except through the one `Ssn` synchronizer (see below).  The ring rule
(principle 4) gives the safe directions from each cell.

## The n = 2 construction (shipped)

The generator builds a template for any arity; for n == 2 (XOR):

```
N WSssssNEwwPeeWSnnnnNEWSnnnnNEeePwwWSssssNE Ssn
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

### The two-star body (generated)

`_body()` paints **two stars** — one around the output leaf and one around
its y-mirror — so the final input never has to be re-embedded; it only
routes to whichever star is already painted.  The stars share the cell at
`(0,±2)`, which is the canonical point the body starts and ends on.  The
spiral order and the anchor no-ops are in the code; the rule worth keeping
is the **gap**: the black moves between two stars are the center distance
minus 2, because each ring reaches one cell toward the other.

### The cycle-2 dance

On cycle 2 the ant starts at the output leaf, inside its star.  The head's
`WS`/`NE` uppercase anchors fire it onto the ring and the weighted legs are
no-ops (every target is a white star cell), so the whole head+body+routing
re-run is a closed walk that returns to the leaf painting nothing new — safe
by the ring rule (principle 4 below).  The anchors and the `Ssn` ending are
chosen so a leafward move only ever comes from the `S/s` dual.

The **`Ssn` synchronizer** is the one leafward move, and it works because
it is a *dual*: `S` fires a white output onto the leaf, while a black
output blocks it and then `s` moves onto the leaf.  Either way the ant
returns to the output, and the `n` is a no-op.  The same dual appears in
the `{Xn-1}` routing's final move.

A head that merely visits each leaf and returns to origin does not work:
after painting a leaf white, a later lowercase move onto that white cell is
blocked (principle 6).  The working head returns through the origin and
never re-crosses a painted leaf.

## The general construction (any n)

The piecewise head generalizes the n == 2 construction to every arity, and
every instantiated program is a cycle-stable fixed point.

### The piecewise head

The head walks each white leaf out and back **piecewise**, one weighted
move per input bit, most-significant first (`_bit_move`); the routing walks
the same moves, so head and read-back always agree on where each leaf is.
Two invariants make it work, and both are easy to break when editing:

- The outbound path never crosses a previously painted leaf — the
  intermediate cells are never leaf positions, so only the final cell is
  painted.
- After `P` the head retraces the same path back (`_reverse_moves`), so it
  never re-enters a painted cell.

For `n >= 2` each segment carries an uppercase **anchor** (`WS` before an
n/s segment, `NE` before a w/e segment).  These are the cycle-2 launchers:
blocked no-ops on the empty first cycle, and from cycle 2 on they fire the
ant off the leaf onto the painted ring, turning the re-run into a closed
zero-paint dance.

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

Exhaustive for ``n <= 3`` (256 tables x 8 inputs = 2048 cases, cycle-stable
and exact on the real interpreter); ``n == 4`` and ``n == 5`` spot-checked
against a handful of tables, every input, via `tests/tools/a_painter_ant_trace.py`;
``n == 6`` and ``n == 7`` build and check out on ad hoc tables but have no
checked-in test.  The semantic-grid model reports no divergence anywhere:
every cycle-2 move stays in the cycle-1 box, no paint changes a cell's
colour, the landing colour is stable, and cycles 2 and 3 are identical.

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
