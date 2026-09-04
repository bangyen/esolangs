# A Painter Ant generator: correctness uniform in the input count

**Claim.**  For every arity `n` and every truth table of length `2**n`, the
generator `esolangs.tools.boolean.a_painter_ant.a_painter_ant` emits a
template whose instantiation, for every input vector, (a) lands the ant on a
cell whose colour is the table entry, and (b) is a *cycle-stable fixed
point*: the whole machine state after two cycles equals the state after one,
so every later cycle repeats it exactly.

The point of this document is that the claim is established without sweeping
the tables.  A boolean-generator sweep runs `2**(2**n)` tables, so the
exhaustive route stops at `n <= 4` (65536 tables, about a minute) and is
already ~407 CPU-days at `n == 5` — the pricing recorded in
[`docs/walls.md`](walls.md).  The argument below replaces the sweep for
`n >= 5` with four lemmas, three of them arithmetic and one a finite check
over a state set that does not grow with `n`.

The machine checks live in `tests/tools/apa_uniform_proof_check.py`; run
them with `uv run python tests/tools/apa_uniform_proof_check.py`.  They are
a *standing* check rather than a one-time recorded run: a change to the
head, body, or routing invalidates the motif table below, and re-running
this is how that is caught.  It is deliberately not named `test_*`, so
pytest does not collect it — it takes minutes.  Each lemma that can be
executed is executed, and the output is quoted here.

## What the construction does

`_head` paints one decision-tree leaf per input combination and returns to
the origin; a one entry is painted `P` (white) and a zero is left unpainted.
`_body` paints two two-layer stars — one around the output leaf and one
around its y-mirror — and the routing walks the ant to the leaf named by its
inputs.  Bit `k` (most-significant first) contributes a run of
`2 ** (n - k)` moves on the axis chosen by index parity: west/north for a
one bit, east/south for a zero.  Only `P` is ever emitted, so paint is
**monotone**: white cells only accumulate.

Two consequences used throughout.  The transition of a whole cycle depends
only on `(grid, position)`, and the grid never loses a white cell; so if the
state after cycle 2 equals the state after cycle 1, every subsequent cycle
reproduces it — a *state fixed point* is a proof of stability, not a sample
of it.  That is the observation that made the `n <= 4` sweep cheap, and it
is reused here as the stability criterion.

## L1 — leaves are distinct and at least four apart

Leaf coordinates are signed sums of distinct powers of two: bit `k` adds
`±2 ** (n - k)` to one axis.  The weights on each axis are superincreasing,
so distinct input vectors give distinct coordinates, and the smallest weight
in play is `2 ** 1 = 2`.  Flipping the lowest-weight bit therefore displaces
a leaf by `2 * 2 = 4`, and no two leaves are closer than that in the
Chebyshev metric.

Executed for `n` of 1..12 — 2 leaves up to 4096 — minimum separation exactly
4 at every arity, no collisions.

The number 4 is what the rest of the argument spends: a leaf's two-layer
star reaches distance 2, so **stars around distinct leaves never overlap**,
and a radius-2 neighbourhood of any leaf contains that leaf's own star and
nothing else.

## L2 — a head walk never targets another leaf

During head execution the only white cells are leaves painted earlier in the
same head.  A lowercase move is blocked exactly when its target is white, so
the head's trajectory could in principle depend on the table.  It does not:
walking the weighted runs from the origin, every intermediate *move target*
is at Chebyshev distance at least 1 from every foreign leaf, and none is
ever *on* one.  The reason is again superincreasingness — along the outbound
walk the weights not yet spent dominate the difference to any other leaf's
coordinate, so a partial sum cannot coincide with one.

Executed for `n` of 1..9: move targets landing on a foreign leaf, **0** at
every arity; minimum distance 1.

So the head paints exactly the one-leaves, in a trajectory that is the same
for every table with the same shape, and the outbound path never crosses a
previously painted leaf — which is what lets the reverse path retrace it.

## L3 — magnitude collapse

A move that is blocked leaves the ant where it stands.  The next identical
character is therefore evaluated from the same cell against the same target
and is blocked too.  By induction, **a run of identical characters that is
blocked on its first character is a no-op of any length**.

Executed for each of `N`, `S`, `E`, `W` at run lengths 1, 2, 4, 8, 16, 64,
256 and 1024 from a state where the move is blocked: 0 moves fired, position
unchanged, at every length.

This is the lemma that removes `n` from the behavioural argument.  The runs
`_bit_move` emits have length `2 ** (n - k)`, which is where program size
grows (a `n == 7` XOR program is 34788 characters), but a blocked run's
*effect* is independent of its length.  What remains of a unit's behaviour
is its first character and its anchors — a vocabulary that does not depend
on the arity.

## L4 — the cycle-2 dance is a bounded, paint-free fixed point

On cycle 2 the ant begins on its output leaf, inside the star the body
painted.  Measured relative to that landing cell, across `n` of 3..8 and an
adversarial table corpus (all-zeros, all-ones, single-one, single-zero, XOR,
alternating, plus random tables):

- every cycle-2 position lies within Chebyshev radius 2 of the landing, and
  for `n >= 5` within radius 1 — the offset set is exactly the 3x3 block
  `{-1,0,1}²`, identical at `n` of 5, 6, 7 and 8;
- at every head leaf-block boundary the ant rests at offset `(0, -1)`,
  one cell north of its leaf, for every block and every arity;
- cycle 2 changes **no** cell's colour (the closed zero-paint dance the
  design requires);
- cycle 2 ends where cycle 1 ended, so the state is a fixed point.

Executed: `n == 3` exhaustively (all 256 tables x 8 inputs) and `n` of 4..8
over the adversarial corpus — **0 failures** on all four properties and on
the landing-colour check.

### Why the block count does not matter

Cycle 2 executes the whole program text, which contains one head block per
one-entry — so the number of blocks grows with both `n` and the table.  The
argument is an induction over those blocks, and the induction step is a
finite table.

Splitting each block into its per-bit units (anchor pair plus weighted run,
outbound and reversed), and keying each unit by what the ant can actually
sense — unit kind, axis parity, bit value, own-leaf colour, entry offset —
the observed behaviour over `n` of 5..8 is a **function** of that key: 0
conflicts across the corpus.  Two facts make it finite and `n`-free:

- every lowercase run inside a unit fires **0** steps — it is blocked on its
  first character, so by L3 its magnitude, and hence `n`, is irrelevant;
- the offsets that occur at unit boundaries are just
  `{(0,-1), (-1,0), (-1,-1)}` — a fixed three-state set, the same at every
  arity checked.

Each block therefore maps the canonical rest state `(0, -1)` back to itself
with no paint, whatever its bit pattern and whatever the arity; composing
any number of them is again the identity on that state.  The non-block
segments (`Ssn`, the routing, the body, and the final `WWwWWEEe` /
`NENEESWw` dance) are fixed strings, checked directly from the canonical
state.

The table is small and it *predicts*, which is the check that separates a
closed induction from a recorded observation.  Learned from `n == 5` alone
it has **30 entries**; replaying it against arities it never saw —
reconstructing each block's unit-by-unit motion from the table and comparing
to the real trace — gives **0 prediction errors** over 320 programs at `n`
of 6, 7, 8, 9 and 10, on adversarial and random tables alike.  A table whose
keys were arity-dependent could not do that: the `n == 10` programs are
about a million characters long and contain a thousand-fold more blocks than
the `n == 5` programs it was built from.

## Scope, and what rests on what

- `n <= 4` is **exhaustive by sweep** and does not depend on this argument:
  all 65536 four-input tables over all sixteen inputs, 0 failures, recorded
  in [`docs/walls.md`](walls.md).  `n == 3` is re-checked exhaustively by
  the script here.
- `n >= 5` rests on L1–L4.  L1, L2 and L3 are arithmetic or one-line
  semantic arguments, executed as confirmation over a range of arities.  L4
  is a finite check: its state set and unit vocabulary are constant in `n`,
  which is what licenses the extension past the arities actually run.
- The small-`n` offset `(-2, 0)`, reachable at `n` of 3 and 4 but not at
  `n >= 5`, is why the uniform argument is scoped to `n >= 5`; the smaller
  arities are covered by the sweep instead.

A positive control accompanies the coverage claim, since a zero-failure
result proves nothing until the probe is shown to fire: blanking the
template's painted leaves must break exactly the table's one-entries, and it
breaks 8 of 16 for XOR4.
