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
  choosing an input order and writing the result.  Finish with a registry-wide
  scaling contract.

  All 65 generators are audited on four axes.  Totality is the `proofs.md`
  ledger's own label (`Cap`: refuses some tables on cost; `Exception`: no
  totality argument).  Output size is the registry-wide contract
  (`tests/proofs/deep/linearity.py`, per-entry cost to n=12).  Generation
  time and execution time were measured by hand (Sep 2026): the fitted
  growth per added input over the top five arities, best of three,
  execution on the worst sampled parity row with loading excluded, and a
  figure on a run under ten milliseconds is not read as an exponent.  A row
  is present while any axis is open and leaves when all four close; an
  n=8 -> 9 ratio near 2 is not evidence of O(T), so every verdict reads in
  one direction only.  The live audit is:

  | Language | Totality | Generation time | Output size | Execution time |
  | --- | --- | --- | --- | --- |
  | %^2^-1 | Exception | Linear | Linear | Linear |
  | Factor | Total | Language lower bound | Language lower bound | Linear |
  | Polynomial | Cap | Open | Open | Linear |
  | Vandevelo | Total | Open | Linear | Linear |
  | WII2D | Cap | Open | Open | Linear |
  | ZTOALC L | Cap | Open | Open | Linear |

  Generation time, growth per added input at the top arity: Polynomial
  x3.4 dense (1.1 s at n=9), WII2D x4.8 dense (1.1 s at n=9), Factor x2.7
  (1.2 s at n=11).
  B-tapemark, Streetcode, 6-5, Forth and Circuit Diagram past its n=8
  route change all read x2.2, between the size contract's x2.15 and what
  these arities separate from noise; they are held linear until a wider
  measurement says otherwise.  Interprogck8 and Unsquare left this table
  with their builds byte-identical -- printer flights laid once per shared
  channel (x3.3 -> x2.03, 2.8 s -> 0.2 s at n=12), and an incremental tree
  price that re-tests only the levels a sink moves (x2.4 -> x2.02).
  Circlefuck left at x1.92 (16 ms at n=12, from x2.5): its greedy order
  puts the essential inputs first and scores at most eight levels, its
  emitter settles the folds bottom-up and indexes the stream-order table
  per node instead of scanning every node's rows over a permuted copy,
  and the programs are unchanged through n=10 and within one percent
  either way on three of ten sampled tables above.  Vandevelo x2.9 dense
  (0.27 s at n=12, from x3.6 and 1.3 s, parity x1.9): the peel restarts
  per cube, scoring ~50 candidate directions on a 2**n-bit mask per round,
  Theta(T^2 / word).  Keeping the chain of intersected sets across cubes
  instead -- a peeled cube leaves every level exactly itself, so each
  level's candidate scores are kept per leaving row -- reads x2.14 at
  n<=12 (0.11 s, cover +2% on a 90-table corpus) but is quadratic too: a
  level's direction switches Theta(T) times and each switch rebuilds the
  level above at its parent's size, 4.2 -> 7.0 rows filtered per entry
  from n=12 to 14.  Bounding a level to a window of its lowest 512 rows
  with membership checked against the chain is linear in count and no
  faster (0.23 s at n=12, 2^depth lookups per test, cover +4%); scoring
  a sample and growing the cube through the lowest row alone is linear
  and 0.07 s but +13--20% of cover; re-deriving every level per cube
  (keep ratio 1.0) matches the shipped cover at 0.994x and is quadratic
  again.  Every non-restarting peel also trades Cohen--Shinkar's O(T)
  clause bound for a measurement, since the popular direction is no
  longer exact over the remainder.  `%^2^-1`
  left at x2.2 dense and x1.5 parity over n=6..10 (23 ms and 11 ms at
  n=10, from x4.2 and x2.6, 0.93 s and 0.11 s), byte-identical over 910
  tables through n=13: the fold planner keeps its points sorted in
  absolute position under one offset, so a step removes its victims
  from an end, bisects one landing and flattens row ids only for the
  victims it names; the emitter mirror is the same sorted list under a
  lazy offset with a union-find from rows to groups; and the deep band
  reads legality off the weighted values (class-pure or not, `T * n`)
  instead of enumerating `T ** 2` row pairs, walking only the zero-free
  weightings its screen admits.  Above n=10 the time follows the plan:
  53 ms, 161 ms and 494 ms at n=11..13, 17-30 us per fold step
  throughout, with the staged route's packed prefix at n=13 costing
  three steps per table entry where the ladders cost 1.3, and growing
  the program by the same factor.
  BFStack, BrainIf, LaserFuck, RAM0
  and Jaune left the execution column the same way: BFStack's ``[`` scanned
  for its ``]`` on every skip, and the other four rebuilt a whole immutable
  tape per write, now a chunked persistent tape
  (`esolangs.interpreters.persistent`); they read x1.5-x2.0
  with every output and step count unchanged.

  Closure requires a lower bound over every program in the language under
  the generator contract.  Super-linear output implies super-linear
  generation time; the time column is not an independent verdict there,
  but a linear output can still be built super-linearly, which is what
  Vandevelo's open generation-time cell records.

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

  Polynomial's cap is priced in [polynomial](polynomial.md); WII2D's lift
  is the extremal-fold rule, total but at megabyte sizes, and its three
  open cells are one question.  The `Exception` row cannot close:
  `%^2^-1`'s accumulator has 6263 distinguishable classes between two
  placeholders (6007 in-window values, 256 deep residues), and the suite's
  dense seventeen-input fixture forces at least 7640 distinct cofactors at
  every thirteen-input cut, so no template at any length computes it
  ([proofs](proofs.md), executed by `tests/proofs/deep/pct_squared_minus_one.py`).
  What is left is finite -- which tables through sixteen inputs the
  language admits and the planners refuse: every table tried through
  thirteen builds, and from fourteen the dense fixture refuses while
  parity and other tables whose suffix cofactors compact still build --
  and no cut below seventeen can exceed 4096 classes, so a construction
  there is not ruled out by counting.

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

  CV(N)(C) left: its halt gadget squares once more whenever the program
  is not shorter than its reach, two characters per leaf.  6-5 left: past
  35 inputs its walk loops on sixteen labels, reading each bit's stride
  off 2-adic valuation marks that one pass per bit shifts, linear in size
  and executed on every row through n=7.  NoComment left: its rows are
  code and its index is the stack, so the tape is six cells at any arity;
  the chain is the smaller program from four inputs (never larger on any
  four-input table) and executed on every row through n=10.  Factor's
  totality closed: its digit budget was a size policy, not the
  language's, and without it the encoder is the ledger's lift argument
  verbatim; the row stays for its two language lower bounds.

  Treat every emitted character as build work.  Input reordering is optional
  around the construction, but its work still counts toward end-to-end
  generation time.  Order selection builds at most four named candidates and
  its generic greedy scorer stops at n=10; factorial and exponential contests
  are test-only oracles.

  No generator construction may use BFS or DFS; test-only oracle searches and
  prose about retired searches may remain.

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
