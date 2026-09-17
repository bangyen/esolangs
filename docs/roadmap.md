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

  All 65 generators are audited on four axes.  Totality is the `proofs.md`
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
  | %^2^-1 | Exception | Linear | Linear | Linear |
  | COD | Total | Open | Open | Open |
  | Factor | Total | Language lower bound | Language lower bound | Linear |
  | Nopstacle | Total | Linear | Open | Linear |
  | Polynomial | Cap | Open | Open | Linear |
  | Vandevelo | Total | Open | Linear | Linear |
  | WII2D | Cap | Open | Open | Linear |
  | ZTOALC L | Cap | Open | Open | Linear |

  Generation time, growth per added input at the top arity: Polynomial
  x3.4 dense (1.1 s at n=9), WII2D x4.8 dense (1.1 s at n=9), Factor x2.7
  (1.2 s at n=11), Vandevelo x2.9 dense (0.27 s at n=12, parity x1.9).
  B-tapemark, Streetcode, 6-5, Forth and Circuit Diagram past its n=8
  route change read x2.2, between the size contract's x2.15 and what
  these arities separate from noise; they are held linear until a wider
  measurement says otherwise.

  Each open row's question, with the searched negatives in
  [limitations](limitations.md#searched-negatives):

  - Vandevelo, generation time: a peel that does not restart per cube.
  - COD, all three: an H-tree that distributes input `i` to every node of
    level `i` without a shared run losing lane identity.
  - Nopstacle, size: a linear-area layout when one run fills one line.
  - Polynomial: a left-half-plane multiple with more terms than the
    Descartes minimum ([polynomial](polynomial.md)).
  - WII2D, three cells: a decode that reads the answer as the
    accumulator's top bit in O(T) characters.
  - Factor: stays for its two language lower bounds; `%^2^-1`'s
    `Exception` cannot close, and which tables through sixteen inputs the
    planners refuse is finite.
  - ZTOALC L: a rule, not a search, for a dense simple path in
    `p -> p/2 | 3p+1 | p+1`.

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
  (16 of 18 spell it so: one `PAIR` constant the generator module owns,
  which the example's `pair` field reads; Nopstacle and %^2^-1 pass a
  `setters` function instead).
  The last two are measured, not structural: `tests/proofs/test_conventions.py`
  reads this table and measures every cell off the programs -- the embed
  is the span, row by row, on which the two fills of one input differ; a
  blank left after deleting each single blank between two non-blank
  characters is a spaces violation, and two inputs whose spans differ are
  a uniformity one -- on dense and parity tables at n=2..6, every
  instantiation.  `Open` means a spelling is not ruled out; `Language`
  means the alphabet leaves none.  A row is present while any cell is
  open and leaves when both close.

  | Language | No spaces | Uniform |
  | --- | --- | --- |
  | Nopstacle | Language | Language |

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

- **`%^2^-1` fourteen inputs.**  The staged fold's endgame strands its last
  duplicated cofactor pairs.  Rank order is steerable (pulsed doubling), but
  a merge needs the pair's value gap `d` inside a wipe window, and diving
  the partner maps `d -> amount - d` with the amount free in the window --
  a derived, unbuilt alignment controller.  Build it only if a ~20x
  thirteen-input build cost (~430k plan ops, ~8MB templates, ~226 ops per
  merge) is acceptable.
