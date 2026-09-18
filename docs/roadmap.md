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
  and no construction or bound; WII2D's ten ended in a measured target and
  one unproved lemma.  Polynomial's fourteen rounds ended in the bound:
  its measured target, `Theta(L**2 log L)` digits for every multiple of the
  mandatory root product, is now proved, and the row closes on size and
  time as a language lower bound.  The clause is deliberate: a wall that
  has not been proved is not a lookup table, and both Factor's bound and
  Polynomial's came after their walls were measured.  SLOW ACV MAMMALIAN
  closed on generation time the same way its size and execution-time cells
  already had: the per-node retry loop was re-simulating an O(weight)
  `_w_raise` and an O(weight) trampoline build on every retry just to size
  and length-check a candidate landing, not to emit it.  Both dry-run costs
  close to O(1) -- `_w_raise`'s chunk sequence is a residue orbit over 256
  states (`r -> 2 * added(r) % 256`) that a cycle detector skips through by
  multiplication, and the trampoline's chunk count is exactly 1 `SEED` per
  chunk past the second, closed by division -- so a level's retries no
  longer each pay for the O(weight) build its accepted attempt alone needs.
  Measured flat at ~0.021 microseconds per emitted token across four
  doublings (n=14 to n=20, 4.3M to 271M tokens), byte-identical to the
  prior output on every table checked.  Closed 2026-09-18.

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
  | Streetcode | Total | Open | Open | Linear |
  | WII2D | Cap | Open | Open | Linear |

  Generation time, growth per added input at the top arity: Polynomial
  x3.4 dense (1.1 s at n=9), WII2D x4.8 dense (1.1 s at n=9), Factor x2.7
  (1.2 s at n=11).  B-tapemark, 6-5, Forth, Circuit Diagram past its n=8
  route change, and Vandevelo (x2.0 dense over n=11..15, 0.31 s at n=12,
  a peel that keeps its working sets across cubes) read x2.0--2.2,
  between the size contract's x2.15 and what these arities separate from
  noise; they are held linear until a wider measurement says otherwise.
  Streetcode and Interprogck8 read x2.07 and x1.96 the same way and are
  not held linear: their constructions carry a `log T` the twelve
  doublings cannot see, so their rows are open on what the code says.

  Each open row's question, with the searched negatives in
  [limitations](limitations.md#searched-negatives):

  - COD, all three: a two-exit zero test on a block of `R` values in
    `o(R)` cells with every stray cod dead (an input cell serves four
    headings, so a level's fifth node lives in the value; a one-lane
    node is eight commands but repeats the embed).
  - Streetcode, size and time: each level's hall spans every row of both
    subtrees, so the ~4T leaf rows are `Theta(n)` wide (220, 235, 244
    characters per row at n=8, 10, 12) -- `Theta(T log T)`, and the
    uncapped greedy order `Theta(T log**2 T)`; the escape is a packed
    positional layout like AddSubJump's, priced and unbuilt.
  - Interprogck8, size and time: a read at depth `d` is `3 + 2 floor(d /
    14)` lines, `Theta(T n / 14)` in steps of fourteen inputs (805--887
    characters per entry to n=14, 6300--6600 at n=15, refused past 40);
    a constant-width read gadget exists at ~8x per node at every arity,
    priced and not taken.
  - WII2D, three cells: a rule emitting readouts within a constant of the
    exact optima (1.4--2.4 characters per entry to domain 14); no one-step
    or bounded-beam rule over small centres is one, and the optima's
    non-ratcheting shape ends between domain 32 and 64: a first epoch
    within eight units of the origin then leaves magnitude 4--8 `D`,
    and from the shipped decoder's own states no two epochs return to
    `4 live` under `live / 4` unary, a floor it tracks within 2x
    (the zone lemma in [limitations](limitations.md#searched-negatives)).
  - `%^2^-1`, size and time: no invariant bounds a point's relocations
    (~1.5 KB each), and the top arities read x4.8 per input (375 KB at
    n=13, 1.8 MB at n=14, refused at 15); the contract's x1.11 measures
    only to n=12 past the n=4 route change.  Its `Exception` cannot close,
    and which tables through sixteen inputs the planners refuse is finite
    (every table tried through fourteen builds).
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
  template is the program with each input spelled as a run of one
  character outside the language (`$`), one run per input in order and
  exactly as long as the code that replaces it, plus one `(zero, one)`
  pair per input; three of the five are therefore the template's own
  shape.  *Single embed*: each input is one run (the constructor refuses
  a run of the wrong length, a run left over, or the character in the
  program proper).  *Constant width*: every instantiation of one template
  has the template's length, so `len(program)` reveals nothing (the
  constructor refuses a pair of unequal width).  *Slot order*: the k-th
  run is input k, by definition.  *No spaces*: a bit is spelled in
  commands, never as a blank or padded with blanks; a single blank
  between two tokens of the embed is a delimiter and is fine (Bitdeque's
  `INVERT PUSH`, RAM0's `Z A`).  *Uniform*: the pair is the same pair
  for every input, so the template would be one character and one pair
  (16 of 17 spell it so: one `PAIR` constant the generator module owns,
  which the example's `pair` field reads; %^2^-1 passes a `setters`
  function instead).
  The last two are measured, not structural: `tests/proofs/test_conventions.py`
  reads this table and measures every cell off the programs -- the embed
  is the span, row by row, on which the two fills of one input differ; a
  blank left after deleting each single blank between two non-blank
  characters is a spaces violation, and two inputs whose spans differ are
  a uniformity one -- on dense and parity tables at n=2..6, every
  instantiation.  `Open` means a spelling is not ruled out; `Language`
  means the alphabet leaves none.  A row is present while any cell is
  open and leaves when both close; the table is empty since Nopstacle,
  whose alphabet was the blank and `#`, left the collection.

  | Language | No spaces | Uniform |
  | --- | --- | --- |

  Toggles are an open decision.  The proposed shape: a keyword per relaxed
  convention on the generator, off by default and carried through the
  example's `kwargs` so the suite builds and executes the relaxed program
  through the same harness (`replace(example, kwargs=...)`); the contract
  sweeps the defaults, and `takes_width` is the precedent for reading a
  capability off the signature.  *Differing widths* buys size where the
  zero pad is long (BF-PDA's pair would return to `<` against `<@`)
  and buys the length leak back.  Add the width toggle only where a
  measured build is smaller; a space toggle has nothing left to relax and
  is not worth its plumbing.
- **ArrowQueue reusable drain.**  Ship the verified deep-fold drain only if
  a proof makes folding meaningfully testable at `n >= 5`; current coverage
  does not reach its crossover.

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
  and the replaced ranking stays in the tests as the oracle.

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
