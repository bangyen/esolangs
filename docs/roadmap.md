# Roadmap

Only live work belongs here. Contracts and standing walls go to
[limitations](limitations.md); a closed row leaves, and its commit is the record.

## New interpreters

The candidate list is empty.

## Conditional follow-up

- **Linear Boolean generators.**  Make build time and emitted size O(T), where
  T is the truth-table length.  For each remaining generator, either add a
  loop-less O(T) construction and an executed scaling regression, or record a
  structural proof that the language or required encoding forces super-linear
  output and continue with the next generator.  Generation time includes
  choosing an input order and writing the result.

  The bar for membership: a language stays while its generator is O(T)
  on all four axes under the conventions, or its row carries a proved
  language lower bound, or its generator is a construction whose open
  cells carry an executed obstruction -- a semantic model of the language
  that every construction tried has broken on, pinned as tests.  A lookup
  table in a language's syntax is not a generator -- any language can be
  brute-forced -- so a row whose generator is one carries a clock: one
  more executed round, and if neither a construction nor a bound comes of
  it the language leaves with its row.  ZTOALC L (a chunked array lookup
  on Collatz slots, no line-local rule and dense paths only by search)
  left under it on 2026-09-17.  Nopstacle left the same day on the first
  clause, not this one: its generator was a decision tree of corridors
  like twenty-five others', `Theta(n 2**n)` because a level's run must
  sit on one line, but its alphabet -- the blank and `#` -- can spell
  neither the no-spaces nor the uniform convention, and no construction
  under the conventions exists to be linear.  COD stays on the third
  clause: four executed rounds the
  same day produced the model in its searched-negatives paragraph (no
  routing primitive, joins that leak a copy, a kill per zero-set per copy)
  and no construction or bound.  WII2D stays on the third clause too:
  the fold is the language's only branching, pinned in
  `tests/tools/test_boolean_wii2d.py::test_the_junction_catalogue_alone_cannot_replace_the_fold`.
  Polynomial's fourteen rounds ended in the bound:
  its measured target, `Theta(L**2 log L)` digits for every multiple of the
  mandatory root product, is now proved, and the row closes on size and
  time as a language lower bound.  The clause is deliberate: a wall that
  has not been proved is not a lookup table, and both Factor's bound and
  Polynomial's came after their walls were measured. SLOW ACV MAMMALIAN closed
  on generation time on 2026-09-18: an O(1) residue-orbit dry run replaced
  retry-time O(weight) simulation, with byte-identical output.

  All 63 generators are audited on four axes.  Totality is the `proofs.md`
  ledger's own label (`Cap`: refuses some tables on cost; `Exception`: no
  totality argument).  Output size is the registry-wide contract
  (`tests/proofs/deep/linearity.py`, per-entry cost to n=12).  Generation
  time and execution time are measured by hand: the fitted growth per
  added input over the top five arities, best of three, execution on the
  worst sampled parity row with loading excluded, and a figure on a run
  under ten milliseconds is not read as an exponent.  A row is present
  while any axis is open and leaves when all four close; an n=8 -> 9
  ratio near 2 is not evidence of O(T), so every verdict reads in one
  direction only.  Closure requires a lower bound over every program in
  the language under the generator contract.  Super-linear output implies
  super-linear generation time; the time column is not an independent
  verdict there, but a linear output can still be built super-linearly.
  The live audit is:

  | Language | Totality | Generation time | Output size | Execution time |
  | --- | --- | --- | --- | --- |
  | %^2^-1 | Exception | Open | Open | Linear |
  | COD | Total | Open | Open | Open |
  | Factor | Total | Language lower bound | Language lower bound | Linear |
  | Interprogck8 | Total | Open | Open | Linear |
  | Polynomial | Cap | Language lower bound | Language lower bound | Linear |
  | WII2D | Cap | Open | Open | Linear |

  Generation time, growth per added input at the top arity: Polynomial
  x3.4 dense (1.1 s at n=9), WII2D x4.8 dense (1.1 s at n=9), Factor x2.7
  (1.2 s at n=11).  B-tapemark, 6-5, Forth, Circuit Diagram past its n=8
  route change, and Vandevelo (x2.0 dense over n=11..15, 0.31 s at n=12,
  a peel that keeps its working sets across cubes) read x2.0--2.2,
  between the size contract's x2.15 and what these arities separate from
  noise; they are held linear until a wider measurement says otherwise.
  Interprogck8 reads x1.96 but remains open: its construction carries `log T`.
  Streetcode closed on generation time and output size on 2026-09-18; its
  alternating-axis H-tree (`9250e3ce`) is linear by construction and measured
  within the size contract through n=14.

  Each open row's question, with the searched negatives in
  [limitations](limitations.md#searched-negatives):

  - COD, all three: a two-exit zero test on a block of `R` values in
    `o(R)` cells with every stray cod dead (an input cell serves four
    headings, so a level's fifth node lives in the value; a one-lane
    node is eight commands but repeats the embed).
  - Interprogck8, size and time: a read at depth `d` is `3 + 2 floor(d /
    14)` lines, `Theta(T n / 14)` in steps of fourteen inputs (805--887
    characters per entry to n=14, 6300--6600 at n=15, refused past 40);
    a constant-width read gadget exists at ~8x per node at every arity,
    priced and not taken.  Pinned: a spelled distance of 261 after
    `DownAccLines` lands 6 lines on, not 262 (acc wraps mod 256), and a
    stride-30 two-hop flight meant to reach +60 stops at +30 on an inner
    node's own landing marker of the same residue -- every control
    transfer is `DownAccLines` on an 8-bit acc, so a flight past 255
    lines needs a relay chain, and a residue shared for transit collides
    with a nested marker on it.  The other primitives were surveyed for a
    way around it: `{values...}` writes only 81/84, and a bare `$py`
    assigns acc with no wrap but only from an extra stdin read outside
    the n-bit convention; the function slot skips a captured body of any
    size with no jump distance at all and branches with no
    `DownAccLines`, but cannot nest -- capturing a subtree that itself
    holds `<` is refused unconditionally, so it routes one read and no
    more.  `z` restarts with acc 0 and an empty slot, but a conditional jump
    can retain one bit in which adjacent marker it deletes.  These are
    obstructions to the routed-tree model, not a language lower bound:
    within that model a tree's total flight length is `Theta(n T)`, the total
    edge length of a linear arrangement of a complete binary tree.  Any bound
    must price `z`'s deletion state.
  - WII2D, three cells: a rule emitting readouts within a constant of the
    exact optima (1.4--2.4 characters per entry to domain 14); no one-step
    or bounded-beam rule over small centres is one, and the optima's
    non-ratcheting shape ends between domain 32 and 64: a first epoch
    within eight units of the origin then leaves magnitude 4--8 `D`,
    and from the shipped decoder's own states no two epochs return to
    `4 live` under `live / 4` unary, a floor it tracks within 2x
    (the zone lemma in [limitations](limitations.md#searched-negatives)).
    A non-fold construction is closed: the language has no instruction
    that reads a value into control, so a branch is a build-time embed
    choice between two edges sharing one op string per surviving value,
    and only the fold's arithmetic can split them
    (`tests/tools/test_boolean_wii2d.py::test_the_junction_catalogue_alone_cannot_replace_the_fold`).
  - `%^2^-1`, size and time: the shortest 2/3 descent shrank the dense
    fourteen-input template from 1.84 MB to 1.59 MB (280 KB at thirteen),
    but does not bound a point's relocations or the number of them: the
    four-input `0101010100100010` plan moves one row ten times in 62 steps,
    renders to 14,739 bytes, and executes all sixteen rows.  The contract's
    x1.11 measures only to n=12 past the n=4 route change.  Its `Exception`
    cannot close, and which tables through sixteen inputs the planners refuse
    is finite (every table tried through fourteen builds).
  - Polynomial: stays for its language lower bound on size and time.  The
    exact minimum-mass multiple of the mandatory root product is the
    product itself (integer to L=7, and the real relaxation one digit
    lighter), and the iterated elimination's slack certificate now proves
    `Theta(L**2 log L)` = `Theta(T**2 / log T)` digits for *every* multiple,
    every cofactor and every operand sign -- the lemma on exponential sums
    it rested on is a theorem in [polynomial](polynomial.md).  No
    construction is left and nothing on the bound is open; only the `Cap`
    remains, and a `Cap` cannot close.
  - Factor: stays for its two language lower bounds.

- **Boolean generator conventions.**  Five conventions govern the *embed*,
  the text that stands for one input -- not the program around it.  A
  template has one ordered run per input, constant width, no padded spaces,
  and a uniform `(zero, one)` pair.
  | Language | No spaces | Uniform |
  | --- | --- | --- |
  `tests/proofs/test_conventions.py` checks these on dense and parity tables
  at n=2..6. The table is empty; add a relaxed-width toggle only for a smaller
  executed build. A space toggle has no remaining use.
- **ArrowQueue reusable drain.** Ship it only if folding is testable at `n >= 5`.

- **Reorder ArrowQueue inputs.**  The three-input screen leaves 12.4%
  headroom, but its queued inputs cannot be renamed in place.  Find a
  re-enqueue and grid-routing construction, then compare emitted, executed
  programs against the current template; abandon it if the routing spends
  the apparent gain.

- **Replace WII2D's build-time fold search.**  "Uses a simulator" means
  the module drives an interpreter or an execution model while generating,
  and only one of the three ways that happens is a defect: driving a
  *search* over candidate codes.  Simulation used as bookkeeping for what is
  already being emitted is fine, and size contests run no simulator at all.
  WII2D's decode still enumerates the legal folds and ranks a shortlist;
  what remains is the enumeration and the rank itself (the losing rules
  are in [limitations](limitations.md#searched-negatives)).
  A closing rule must keep the prompt refusal or beat the shipped decode
  on executed programs; a longer emitted program is an acceptable price,
  and the replaced ranking stays in the tests as the oracle.  The fold
  itself is the language's only branching, executed and pinned
  (`tests/tools/test_boolean_wii2d.py::test_the_junction_catalogue_alone_cannot_replace_the_fold`),
  so this item is about the choice rule alone: one-step keys, Phi, an
  added merge-free vocabulary and a two-ply lookahead all rank no better
  than the shipped depth predictor (numbers in
  [limitations](limitations.md#searched-negatives)).

- **`%^2^-1` fifteen inputs.**  Fourteen builds by laying the next input
  when the lay fits (a collision-free even split with `span + total <=
  6006`) and the rules merge 25 more points on the laid state (a
  one-move probe lays too early and jams), carrying the stranded
  duplicate pairs into the next stage where the conveyor merges them at
  sixteen classes: dense n=14 in 9.8 s and 1.84 MB, about 5x the size
  and 12x the plan ops of thirteen, 40 sampled rows executed, n<=13
  byte-identical.  At
  fifteen the 11-cut has 2,017 distinct sixteen-row cofactors among
  2,048 rows, so nothing compacts below 2,017 points before the lay; the
  rules stall (20k ops, no merge), the spread state refuses the lay
  (span 4,638 + total 4,640), an immediate lay has no rule move at op 0,
  and a forced band gap jams the conveyor at 4,088--4,091 points.  A
  fifteen needs a mechanism that lays an input onto ~2,000 unit-spaced
  points while merging its 256 child classes; nothing in the move set
  does so cheaply.
