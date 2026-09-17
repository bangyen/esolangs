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

  Vandevelo's open cell is its peel, which restarts per cube and scores
  ~50 candidate directions on a 2**n-bit mask per round, Theta(T^2 /
  word).  Keeping the chain of intersected sets across cubes reads x2.14
  at n<=12 but is quadratic too: a level's direction switches Theta(T)
  times and each switch rebuilds the level above at its parent's size.  A
  window of a level's lowest 512 rows is linear in count and no faster; a
  sampled score with growth through the lowest row is linear and 0.07 s
  but +13--20% of cover.  Every non-restarting peel also trades
  Cohen--Shinkar's O(T) clause bound for a measurement, since the popular
  direction is no longer exact over the remainder.

  COD's fork/cascade generator embeds each input once, at its own `+`
  fork, and is super-linear on all three axes: size x3.9 per added input
  over n=5..9 (942,668 characters at n=8, 3.67 MB at n=9; the cascade's T
  leaf rows each carry a Theta(T) prefix and gate tail), build time
  tracking the size, and the worst row's command count x2.32 per added
  input at n=9 (40,464 commands), which the execution contract reads as
  its exemption.  The constant-size two-polarity test exists once a bit
  reaches a node (`<` keeps only one, `(<` keeps only zero, `(`/`)`
  normalize the survivor), so a linear-area H-tree needs input `i` at
  every node of level `i`; a shared run cannot distribute the bit to
  separate node lanes without losing the lane identity, and carrying that
  identity as the cod's value returns to the super-linear numeric decoder.
  That is the row's open question on all three axes.

  Nopstacle is open on size alone: a full decision tree of corridors,
  level `i` reading its input at `2**i` node columns of one row, in a
  padded rectangle `4 * 2**n` wide by `3n + 7` high, `Theta(n 2**n)` by
  construction (31,774 characters at n=8, x2.21 there and x2.13 at n=12
  on the contract's two-step mean, per-entry cost 44.5 rising by twelve
  per input).  The same H-tree question as COD's: a linear-area layout
  puts level `i`'s cells on `2**(i/2)` rows, and one run fills one line;
  every layout with a line per input is a `2**n`-wide row per input.

  Polynomial's remaining question is a left-half-plane multiple of the
  mandatory root product with more terms than the Descartes minimum:
  instruction count, monomial count, right-half-plane coefficient mass, and
  the Descartes-minimal class are all language-forced, every searched
  escape is closed, and the Rolle reduction behind Descartes cannot lower
  the kernel's rank; the open class carries O(1) primorial-sized
  coefficients and has degree `0.72 L log L` or more unless a second
  coefficient reaches the primorial's square root.
  [polynomial](polynomial.md) has the proofs, the measured negatives, and
  the literature match.

  WII2D's remaining question is the decode: the last junction's two
  branches turn the Horner index into the table's columns by folding
  (`'-' * c + 's'`, one character per unit of the centre) and halving, and
  the emitted size per table entry climbs 11 -> 16 -> 15 -> 58 -> 153 from
  n=5 to n=9 on the suite's dense fixture.  A linear construction needs the
  answer readable as the accumulator's *top* bit -- floor-halving discards
  low bits and a digit discards everything, so nothing discards the bits
  above -- and every cheap placement found (shifts by `2 ** q`, squaring's
  cross terms, a dot product by multiplication) leaves other entries or
  monomials above it.  Refuted by an op-string family of length O(T) that
  computes an arbitrary column from the index, or from `2 ** (K +- q)`,
  which the chain can emit in O(n) characters.  A readout that tolerates
  junk above the answer is refuted too: every op but `s` is monotone on
  non-negative values and `~` needs the exact 48 or 49, so after the last
  squaring the readout is a monotone map onto two values -- a threshold
  in value order -- and anything else needs another `s`, which is a fold
  with a unary centre.  "Nothing discards the bits above" holds only over
  a low field wider than one bit: `-` then `K - 1` halvings carry a one-bit
  low field up as a borrow, leaving `2a + b - 1`, and integer-centre folds
  then read `b` under any top field `a` at the price of `a`'s *value
  count* (a two-bit `a` at `K = 30` executes in 72 characters).  So the
  last junction is cheap given its two-bit class: `3x - 2y` on top yields
  `x` by a threshold and `x ^ y` by one fold, both O(K), executed on all
  four classes.  What that costs is the class, two functions of `n - 1`
  inputs -- the same problem.  Recursing instead (store the table, let
  each junction keep one half) needs the branch keeping the *lower* half
  to forget the upper one above a multi-bit field: the borrow carries one
  bit, halving further destroys the field, and a fold's centre there is
  spelled at that field's weight, `2 ** m` characters for an `m`-bit
  half.  The layout adds nothing: for a dense table every run reads every
  input, a second read order would put a cycle some assignment follows,
  and a junction cell can be entered from at most four headings, so any
  fill yields a fixed chain read at most four times, never a tree.
  WII2D's lift is the extremal-fold rule, total but at megabyte sizes,
  and its three open cells are one question.

  Factor's row stays for its two language lower bounds.  `%^2^-1`'s
  `Exception` cannot close ([limitations](limitations.md)); what is left
  is finite -- which tables through sixteen inputs the language admits
  and the planners refuse: every table tried through thirteen builds,
  from fourteen the dense fixture refuses while parity and other tables
  whose suffix cofactors compact still build, and no cut below seventeen
  can exceed 4096 classes, so a construction there is not ruled out by
  counting.

  ZTOALC L's cap and its size are one fact: every command sits on a value
  of one Collatz trajectory, and a trajectory crosses each scale band a
  few times, so the L-th smallest value grows exponentially in L.  The
  best start under `2**22` supplies 395 lines (a sieve of every start);
  dense n=10 is 311 commands on 1,477,714 lines, 14.5 -> 58.7 -> 1446
  characters per entry over n=8..10 (x8.1, x49 per input), and n=11 needs
  545-587 commands.  The ledger's lift, start `2**k`, is the same
  placement at `2**k` lines.  Neither is language-forced: `jump if` moves
  the pointer to the next line instead, and with it a program can execute
  about 0.7 of its lines in one straight run -- an exact search over every
  start and jump set is 28 of 36 lines at L=36 and 0.68-0.83 at every
  fourth L from 8 to 44, executed on the interpreter as 28 commands on 36
  lines where the trajectory placement needs 106.  What is missing is a
  rule.  The run must be a simple path in `p -> p/2 | 3p+1 | p+1`; a
  fixed local rule drifts by a power of 3/2 per round and visits O(log L)
  lines, and a boundary-reflected greedy (take the Collatz edge unless its
  landing is used, else jump) stops when both exits are used, about
  L^(2/3): 2,387 commands from 100,000 lines.  Dense paths are found only
  by search.

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
  for every input, so the template would be one character and one pair.
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
  | %^2^-1 | Holds | Open |
  | A Painter Ant | Holds | Open |
  | ArrowQueue | Holds | Open |
  | BIO | Holds | Open |
  | Bitdeque | Holds | Open |
  | Minsky Swap | Holds | Open |
  | Nopstacle | Language | Open |

  The seven uniform cells open for one reason, the input's *weight*: a
  linear route spells input `i` once at `2**(n-1-i)` units -- A Painter
  Ant `E` per unit, ArrowQueue a marker row per unit from n=5, Bitdeque
  `POP`/`EJECT` per unit with its block pads, BIO 4k-3 characters at
  weight k, Minsky Swap likewise, Nopstacle `2**i` cells across level
  `i`'s row -- and %^2^-1 solves its setters per table, so different text
  per input is its design.  Closing one means the template carries the
  weight and every input is one unit.  A Painter Ant and ArrowQueue
  *tile*: the embed at weight k is the unit embed repeated k times.  The
  other five do not: Bitdeque's units are 4 and 6 wide with no
  2-character no-op (its pads are per block), BIO's connective breaks the
  tiling, Nopstacle's cells have template between them, and a uniform
  %^2^-1 is a different generator.  Nopstacle's alphabet is the blank and
  `#`, so a zero bit *is* a blank: its input run is a bit cell at each of
  level `i`'s `2**i` node columns with blanks between, the same width
  either way, and there is no command to spell it with.

  Toggles are an open decision.  The proposed shape: a keyword per relaxed
  convention on the generator, off by default and carried through the
  example's `kwargs` so the suite builds and executes the relaxed program
  through the same harness (`replace(example, kwargs=...)`); the contract
  sweeps the defaults, and `takes_width` is the precedent for reading a
  capability off the signature.  *Differing widths* buys size where the
  zero pad is long (BIO's zero would embed as nothing instead of `0oz;`
  per unit of weight, BF-PDA's pair would return to `<` against `<@`)
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
  WII2D's decode still enumerates the legal folds, validates each against
  the decode model, and takes the head of a ranked shortlist.  The
  compressed-magnitude contest is load-bearing: on a 230-table seeded
  corpus the one-shot rules lose (nearest-midpoint centre 1.06x the size
  and 0 of 8 dense n=9 against 4 of 8; most-merges and cheapest-centre
  build nothing past n=6), and the extremal same-colour fold -- always
  legal, the argument that made the decode total -- refuses from n=7 under
  the shipped centre and magnitude caps and needs them lifted to build
  dense n=9 at a megabyte.  A closing rule must keep the prompt refusal or
  beat the contest on executed programs; a longer emitted program is an
  acceptable price, and the replaced search stays in the tests as the
  oracle.

- **`%^2^-1` fourteen inputs.**  The staged fold's endgame strands its last
  duplicated cofactor pairs.  Rank order is steerable (pulsed doubling), but
  a merge needs the pair's value gap `d` inside a wipe window, and diving
  the partner maps `d -> amount - d` with the amount free in the window --
  a derived, unbuilt alignment controller.  Build it only if a ~20x
  thirteen-input build cost (~430k plan ops, ~8MB templates, ~226 ops per
  merge) is acceptable.
