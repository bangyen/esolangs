# ArrowQueue boolean generator: a totality proof for every arity

**Claim.** For every `n >= 1` and every truth table `t` of length `2**n`,
`esolangs.tools.boolean.parameterized.arrowqueue(t)` builds a template
whose instantiation at input bits `b` halts iff `t[b] == "0"` and loops
forever iff `t[b] == "1"`.

The generator is therefore **total at every arity**, not merely at the
arities that have been swept.  This document is the argument; the
executed checks that ground its finite lemmas are in
`scripts/arrowqueue_lemmas.py`, and each lemma below names the check that
backs it.

Genre note: this is the `docs/walls.md` genre — prose argument plus named
executed checks — not the Lean genre of `docs/proofs.md`.  Nothing here is
machine-checked.  Each lemma is marked **[code]** (follows from reading
the constructor), **[exec]** (verified by running the interpreter), or
**[induction]** (an argument over the recursion, with an executed base
and step).

Language mechanics live in the interpreter module's docstring
(`esolangs.interpreters.grid_based.arrowqueue`) and are not restated.  The
three facts used throughout: `*` turns the IP clockwise, `~` pushes the
current heading, and `+` pops the queue and *replaces* the heading —
halting the run if the queue is empty.  Headings are `0=right`, `1=down`,
`2=left`, `3=up`.

## Why a proof rather than a sweep

`n <= 4` is swept exhaustively (65536 tables, 167s).  `n == 5` cannot be:
it has `2**32` tables, and at the per-table cost `docs/walls.md` prices
(8.2 ms; independently reproduced here at 7.9 ms) that is **roughly 400
CPU-days**.  No per-table optimization divides `2**32` down — a runner
100x faster still leaves four CPU-days.  The table count is the wall, so
coverage past four inputs has to come from an argument that never
enumerates a table.

The construction makes that possible because **the table's contents only
ever choose which leaf blocks appear**, never how the program is routed.
Routing depends on `n` and on the fold structure, and the leaves are
finitely many shapes.  So the proof factorises into a chain of lemmas
about pieces, plus an induction over the tree.

## The shape of an instantiated program

An instantiated program is three sections stacked vertically:

```
  header    4n + 1 rows   embeds each input bit as a queued direction
  middle    7 rows        queues the four loop components R, D, L, U
  tree      variable      pops the bits and routes to a leaf
```

The IP starts at `(0, 0)` heading right and never returns to a section it
has left, so the sections compose by hand-off: each lemma below states
the state one section leaves and the next expects.

## H — the header embeds the inputs

**H1 (pitch) [code, exec].** `_FIRST_ONE` and `_FIRST_ZERO` are 5 rows;
`_NEXT_ONE` and `_NEXT_ZERO` are 4 rows.  `_header_rows` emits one first
block and `n - 1` next blocks, so it is exactly `5 + 4(n-1) = 4n + 1` rows
for every `n` and **every bit pattern** — the two blocks of each kind have
equal height, so the height cannot depend on the inputs.  This is the
constant `_instantiate_arrowqueue` slices the body by (`rows[4*n + 1:]`),
which is why template and instantiation stay aligned at every arity.
Checked over all `2**n` patterns for `n <= 10` and 200 sampled patterns at
`n = 11, 12`: 0 violations.

**H2 (chain) [exec].** Running the header alone from `(0, 0, right)`
leaves the IP heading **down at column 3**, at row `4n + 1` — one row past
the header — with queue exactly the input bits in order, most significant
first.  A `1` bit pushes `down` (1) and a `0` bit pushes `right` (0), once
each.  Per-block traces:

| block | entry | exit | pushes |
|---|---|---|---|
| `_FIRST_ONE` | `(0,0)` right | `(5,3)` down | `(1,)` |
| `_FIRST_ZERO` | `(0,0)` right | `(5,3)` down | `(0,)` |
| `_NEXT_ONE` | `(0,3)` down | `(4,3)` down | `(1,)` |
| `_NEXT_ZERO` | `(0,3)` down | `(4,3)` down | `(0,)` |

Each next block's entry is exactly the previous block's exit, so the
chain composes by induction on the block count.  Verified end to end over
all patterns for `n <= 9` and sampled at `n = 10, 11, 12`: 0 violations.

**H3 (hand-off) [exec].** Appending `_MIDDLE` (7 rows), the queue becomes
`bits + (R, D, L, U)` and the IP enters the tree **heading down at column
1**, at row `4n + 8`.  0 violations over the same range.

This is the tree's entry condition, and the rest of the proof is about
what the tree does with it.

## G — the tree's geometry

The tree is built by `_connect(t0, t1)`, which allocates a rectangle of
spaces and writes at exactly three places: the 0-branch at rows 0–2,
columns 0–2; the 1-branch at rows `yb`–`yb+2`, columns 0–2, where
`yb = len(t0)`; `t0` at row 0, column 3; and `t1` at row `yb`, column 3.

**G1 (row disjointness) [code].** `t0` occupies rows `[0, len(t0))` and
`t1` occupies rows `[yb, yb + len(t1))` with `yb = len(t0)`.  The ranges
are disjoint, so no row holds cells of both subtrees.

**G2 (right corridor) [code, induction].** Within `t0`'s rows nothing is
written right of `t0`, and within `t1`'s rows nothing is written right of
`t1` — the only writes are the two branch blocks at columns 0–2, which
sit *left* of the subtrees, and the subtrees themselves.  Since the grid
starts as spaces, everything right of a subtree within its own rows is
blank.  Inducting over the recursion, in the **fully composed** grid each
subtree's rows are blank to the right of that subtree, so an IP heading
right anywhere inside a subtree's rows crosses only blanks and leaves the
grid.  This is what makes a `0` leaf's escape route sound at any nesting
depth — its rightward run cannot be blocked by a sibling or an ancestor.

**G3 (entry cell and drop column) [code, exec].** The 0-branch's `+` is at
`(0, 1)`, which is the cell an IP descending column 1 lands on — matching
H3.  Column 1 in rows 3..`yb-1` is blank, so the 0-branch's downward exit
falls to the 1-branch rather than hitting anything on the way.

G1/G2/G3 are read off `_connect`'s three writes rather than sampled; the
runner confirms them on composed trees as a check on the reading, by
comparing the subtrees' actual glyph rows and scanning the corridors —
not by restating `_connect`'s own arithmetic back at it.

## B — the branch blocks

**B1 (`+` pops on arrival regardless of heading) [code].** `_advance`
handles `+` before it moves, and a pop *replaces* the heading outright.
So a `+` behaves identically whether the IP arrived heading down, right,
or any other way.  This is the fact that lets the same subtree be entered
two different ways, which the induction needs.

**B2 (0-branch routes on the popped bit) [exec].** Entered at its `+`
with the bit at the queue's head, `_TREE_BRANCH_0` pops it and exits
`(0, 3)` heading **right** for a `0` bit, or `(3, 1)` heading **down** for
a `1` bit.  Column 3 is `t0`'s offset, so a `0` routes into `t0`; the
downward exit falls to the 1-branch at row `yb`.  Verified under **both**
entry styles — down-entry at `(0,1)` (the top level) and right-entry at
`(0,0)` (every recursive subtree, where the IP crosses one blank before
reaching the `+`) — with **identical** exits and pops, which is B1 in
action.

**B3 (1-branch reflects without popping) [exec].** `_TREE_BRANCH_1`
entered heading down at column 1 exits `(0, 3)` heading **right** with the
queue **unchanged** — it is three `*` turns, no `+`.  So the `1` route
reaches `t1` at its column-3 offset having consumed exactly the one bit
the 0-branch popped.

**B3′ (the entry column is load-bearing) [exec].** `_TREE_BRANCH_1`
entered heading down at column **0** leaves the grid in one step.  The
reflector only works from column 1, which is where B2's downward exit puts
the IP.  Recorded because it shows the geometry lemmas are not decorative.

## L — the leaves

**L1 (`0` leaf halts) [code, exec].** `_TREE_0` is 3x3 of spaces.  By G2
the IP heading right through it crosses only blanks and leaves the grid,
which halts.  No queue content can prevent this — that is why a `0` leaf
needs no drain.  Confirmed under both entry styles.

**L2 (`1` leaf sustains) [exec].** `_TREE_1` is a ring that pushes on
every edge and pops at every corner.  Entered heading **right at (0,0)**
with queue exactly `(R, D, L, U)`, it revisits an exact state, which is a
proof it loops forever (`run_until_halt_or_cycle`).

**L2′ (the ring is entry-sensitive) [exec].** The same ring entered
heading **down at (0,1)** *halts*.  The two entry styles are **not**
interchangeable for a bare ring, so the proof has to establish that a bare
ring is only ever entered rightward.  L4 does that.

**L3 (drains drain) [exec, induction].** `_drained_leaf("1", k)` prefixes
the ring with a `k`-step staircase.  Each step is a `+` whose two exits
reconverge on the next `+`: popping a `0` goes right then down, popping a
`1` goes down and around three `*` back up and right.  Both land on the
same cell — with different headings, which B1 says is fine.  The unit
repeats at a `(1, 1)` offset, so the chain composes by induction on `k`.
Structurally `_drained_leaf("1", k)` is `k + 3` rows with `k + 4` `+`
glyphs (`k` drains plus the ring's four) and **exactly the ring's four
`~`** — the drains push nothing, which is what leaves the ring the queue
it expects.  Verified for `k = 0..8` against **every** stale-bit pattern
(all `2**k` of them) under **both** entry styles: every case cycles.
Deep-`k` chains are exercised end to end by the all-ones runs at `n = 8`
and `n = 10` (k = 8 and 10).

**L4 (a bare ring is never the top-level tree) [code, exec].** This is
what reconciles L2 with L2′.  `_tree` folds a constant slice to
`_drained_leaf(v, k)` with `k = log2(len(values))`.  At the top level
`len(values) = 2**n`, so `k = n >= 1` — the domain requires `n >= 1`
(`_validate_truth_table` rejects one-entry tables), so the top-level leaf
of a constant-`1` table always carries **at least one drain**, and its
first `+` sits at `(0, 1)`, exactly where H3's down-entry lands.  The bare
`k = 0` ring appears only as a *nested* subtree at column offset 3, where
entry is rightward by B2/B3.  Confirmed: no table with `n <= 3` has the
bare ring as its top-level tree, and the constant-1 tree equals
`_drained_leaf("1", n)` for `n = 1..5`.

## T — the routing induction

**Induction hypothesis.** Let `S(values)` be the subtree `_tree(values)`
builds for a value slice of length `2**m`.  Entered either

- heading **down at (0, 1)** (the top-level entry, H3), or
- heading **right at (0, 0)** (the recursive entry, B2/B3),

with queue `bits + (R, D, L, U)` where `bits` are the `m` bits still to be
consumed, `S(values)` consumes exactly those `m` bits and reaches the leaf
indexed by them, arriving with queue exactly `(R, D, L, U)`; the run then
cycles iff that leaf's value is `1` and halts iff it is `0`.

**Base cases.** A folded constant slice is a single leaf: L1 for `0`
(halts whatever is queued), L3 for `1` (the `k = m` drains consume the
`m` unread bits and leave `(R, D, L, U)`, then L2's ring sustains) — with
L4 guaranteeing the entry style each shape actually receives.

**Step.** For a non-constant slice, `_connect(S(v0), S(v1))` places the
0-branch at the entry cell.  By B2 it pops the leading bit: a `0` exits
right at column 3 into `S(v0)`, a `1` falls to the 1-branch which by B3
reflects it right at column 3 into `S(v1)` **without** consuming a second
bit.  Both deliver the sub-subtree its right-entry form at its own
`(0, 0)`, with the remaining `m - 1` bits still at the queue's head and
`(R, D, L, U)` behind them — exactly the hypothesis at `m - 1`.  G1/G2
guarantee the delivery lands inside the intended subtree and that a `0`
leaf's escape is unobstructed.

The recursion strictly decreases `m` and bottoms out at a leaf, so the
hypothesis holds for every slice, hence for the whole tree at every `n`.

**Why the induction gives leaf *identity*, not just a verdict.** A
halt-or-cycle check alone cannot distinguish "reached leaf `b`" from
"reached a different leaf that happens to carry the same value."  The
hypothesis is stated on the leaf index, and the executed evidence closes
the gap by being exhaustive **over all tables** at `n <= 4`: any
misrouting `b -> b'` would show up as a failure on every table that
assigns different values to `b` and `b'`, and no table fails.

## C — compaction preserves the verdict

The verdict is read off the **compacted** program, so `_compact` is part
of the claim.

**C1 [code, exec].** `_compact` deletes wholly blank rows and columns and
right-strips.  A blank row or column carries only straight travel: a
vertical run through a blank row stays in its column and pushes nothing,
a horizontal run through a blank column likewise, and a run that would
leave the grid still leaves it.  Deleting rows and columns *together*
preserves every glyph's relative row and column ordering, which is all the
routing depends on — B2/B3's exits are "the next glyph rightward/downward",
not absolute coordinates.  So halting runs still halt and cycling runs
still cycle.  Verified by running both the uncompacted and compacted
program for every instantiation of all tables at `n <= 3` plus 40 random
tables at `n = 4`: **2760 pairs, 0 verdict mismatches**, and every
compacted verdict matched its table entry.

## Result

H1–H3 put the tree in its entry state at every arity; G1–G3 and B1–B3
make the routing step sound; L1–L4 close the leaves including the
entry-sensitivity of the bare ring; T inducts over the tree; C1 carries
the verdict through compaction.  Together they prove the claim for every
`n >= 1` and every table — no enumeration of tables anywhere.

### Executed evidence

Every finite lemma above is re-runnable via `scripts/arrowqueue_lemmas.py`
(a few seconds; `--deep` adds the high-arity runs, a couple of minutes).
Summary of what has been run:

| check | scope | result |
|---|---|---|
| H1 pitch | all patterns `n <= 10`, sampled `n = 11, 12` | 0 violations |
| H2/H3 hand-off | all patterns `n <= 9`, sampled to `n = 12` | 0 violations |
| G1/G2/G3 geometry | composed trees: glyph rows, corridors, drop column | 0 overlaps, 0 blockers |
| B2/B3 branches | both entry styles, both bits | identical routing |
| L2/L2′ ring | both entry styles | cycle / halt |
| L3 drains | `k = 0..8`, all `2**k` stale patterns, both entries | 0 failures |
| L4 top level | all tables `n <= 3`, constants to `n = 5` | bare ring never on top |
| T routing (tree alone) | **all 65536** `n = 4` tables, all inputs | 0 failures |
| C1 compaction | all `n <= 3` + 40 random `n = 4` tables | 2760 pairs, 0 mismatches |
| composition (deep) | random tables at `n = 6, 8, 10, 12`, all `2**n` inputs | 0 failures |
| composition (extremes) | all-ones / all-zeros / single-1 / alternating at `n = 8, 10` | 0 failures |

The `n = 12` run is 4096 inputs against a 227,937-byte program: past any
arity the sweeps reach, and the point at which the induction is doing the
work rather than the enumeration.
