# Roadmap

Only live work belongs here. Contracts and standing walls go to
[limitations](limitations.md); a closed row leaves, and its commit is the record.

## New interpreters

Two routes feed this queue: obscure languages without an implementation, and
popular languages implemented elsewhere but absent here. The 2026-09-27 spec
read is complete; rejected candidates are recorded under Curation in
[limitations](limitations.md).

- **thisthat** (2025): the strongest untouched survivor.  The 2026-09-02 audit
  was misfiled as unread: its transclusions inject CSS, not the node table.
  An acyclic mux network using only `□` NOR passes every table through three
  inputs and has `n + 8T - 7` nodes. Rendering is open: shared input fan-outs
  cross the formula tree, the language has no transparent data crossover, and
  `◐◑◒◓` route by the carried bit. Find a linear crossover or planar
  construction, then execute the Unicode drawing; the netlist alone is not an
  implementation.
- **INTERCAL**: target C-INTERCAL with `WRITE IN`/`READ OUT`. `NEXT` pushes a
  return frame and `RESUME <expression>` selects its depth; `COME FROM` is
  unconditional. Price the labels in a decision tree before building: the
  stack permits 79 entries, and 1/5--1/3 of statements must carry `PLEASE`.
- **Smallfuck** (2002): clears the fame bar at 0.23. The spec deliberately
  leaves the finite tape size and initial/final-state I/O to implementations.
  A folded local-result tree passes every table through three inputs and
  approaches `48.5T` characters. Its equal-width setters are `[*]>>>` for 0
  and `***>>>` for 1; child results move three cells upward, avoiding the
  first prototype's `Theta(T log T)` walk to one answer cell. Pin tape length
  to source length and expose cell 2 as the decoded final answer.

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
  it the language leaves with its row.  A wall that has not been proved is
  not a lookup table.

  Every generator is audited on four axes.  Totality is the `proofs/index.md`
  ledger's own label (`Cap`: refuses some tables on cost; `Exception`: no
  totality argument).  Output size is the registry-wide contract
  (`tests/proofs/deep/linearity.py`, the successive-difference ratio over
  three same-parity arities to n=12, which is four for any `a*T + b` and so
  reads the growth rather than the prologue).  Generation
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
  | Factor | Total | Language lower bound | Language lower bound | Linear |
  | Malbolge | Exception | Open | Linear | Linear |
  | Polynomial | Cap | Language lower bound | Language lower bound | Linear |

  Malbolge cannot be total: its finite source space omits some 18-input truth
  tables.  Its shipped constructions cover every table through fourteen inputs;
  generation time remains open over the reachable gap below that language
  ceiling.  Output size is settled by the language itself: a source must load
  into 59,049 cells, so every Malbolge program -- shipped or not -- is at most
  59,049 characters, which is `O(1)` and so `O(T)`.  No super-linear size
  bound can exist: at sixteen and seventeen inputs `T` already exceeds that
  ceiling, and above seventeen some tables have no program.

  Factor's adaptive residue sequence is bounded by fixed-modulus Hoheisel:
  its last selected prime `Q` is polynomial in the run count. Worst-case
  generated text and the weighted exponent-vector language floor are both
  `Theta(T log T)`. Prime discovery is now an
  arbitrary-precision segmented sieve, and the decoder uses `isprime` only in
  its proven `< 2**64` range, closing both machine-word and BPSW totality gaps.
  Cold generation is
  `O(T + Q log log Q + D**log_2(3))` in the documented RAM/byte model;
  generated-family parsing is polynomial in `T`, while arbitrary semiprimes
  retain exponential trial-sieve loading. The time bound is naturally
  output-sensitive in the last selected prime `Q` and digit count `D`, without
  assuming a prime-gap conjecture. See [factor](proofs/factor.md).

  Polynomial has language-level text complexity `Theta(T**2 / log T)`.  Equal
  real roots form contiguous blocks; their noncrossing opener/closer incidence
  graph is outerplanar and bipartite, giving `m_routing <= 2L_real - 2`.  The routing lemma gives
  `L_real = Omega(T/log T)` for every read count: only the last two reads
  before a routing position can carry a residual that depends on its next
  input and not on it alone.  The distinct-root slack certificate
  then gives the lower bound for every cofactor and operand sign.  The uncapped
  residual-DAG construction has `O(T/log T)` instructions and expands to the
  upper bound.  The pre-expansion estimator bounds rendered and live
  decimal digits before the resource cap admits multiplication.  Put
  `alpha = log_2 3`.  Libmpdec's fixed maximum transform makes the uncapped
  root multiplication Karatsuba-with-FNT at scale, and the balanced packed
  operands give matching bounds: generation is
  `Theta(R**alpha) = Theta((T**2/log T)**alpha)`.  Below that fixed maximum,
  including the public capped range, direct FNT gives
  `Theta(R log R) = Theta(T**2)`.

  Root recovery now lifts through `D**2`, covering the generated
  `|a| < 50D` envelope, and swaps NTT field roles when an instruction prime
  equals the primary modulus.  Exact division remains acceptance.  Therefore
  every generated factor peels.  Cold parsing of *every* source is now
  polynomial in its length: a sparse term map (no dense list for
  `x^1000000000000 - 1`), the gap lemma and `x d/dx` multiplicities with
  Hajos' bound, `p`-adic lifting plus a 2-D lattice for the Gaussian roots
  of one dense chunk in place of `factor_list`, and a `convert` that proves
  primality (deterministic Miller--Rabin below `2**64`, BPSW then AKS above)
  instead of scanning to the widest root.  The output matches the old
  parser on every source it finished.  Conservative generation and cold-parse work/memory estimators cover the
  tested corpus and boundary controls, including pre-expansion refusal and a
  parse outside the former fixed lift.  See [polynomial](proofs/polynomial.md) and
  `tests/proofs/deep/multiplicity.py`.

  Generation time, growth per added input at the top arity: B-tapemark,
  6-5, Forth, Circuit Diagram past its n=8 route change, and Vandevelo
  (x2.0 dense over n=11..15, 0.31 s at n=12, a peel that keeps its
  working sets across cubes) read x2.0--2.2, between the size contract's
  x2.15 and what these arities separate from noise; they are held linear
  until a wider measurement says otherwise.

- **ArrowQueue reusable drain.** Ship it only if folding is testable at `n >= 5`.

- **Reorder ArrowQueue inputs.**  The current three-input screen leaves 7.2%
  headroom, but its queued inputs cannot be renamed in place.  Find a
  re-enqueue and grid-routing construction, then compare emitted, executed
  programs against the current template; abandon it if the routing spends
  the apparent gain.

- **Reorder Circuit Diagram selectors.**  The three-input exhaustive screen
  leaves 20.4% headroom.  Its inputs already occupy separate rails, so keep
  their read order and permute only which rail each Shannon level selects.
  Ship only if executed programs beat both flat and H layouts on a wider
  corpus without moving generation above O(T).

- **Reorder Crement testers.**  The same screen leaves 12.4% headroom.  Keep
  the parameterized runs in name order and map each tree level to the chosen
  tester address.  Ship only if every three-input table executes correctly
  and the routing win survives the emitted tester and patch addresses.

- **Prune raster dependencies.**  Line and Piet both retain every input and
  every table entry when the function ignores inputs: at four inputs, an
  all-zero Line drawing is 1,920 x 2,060 pixels and an all-zero Piet program
  is 258 codels.  Read every input to preserve the interface, but branch or
  index only on the essential ones.  Ship separately per language only if
  the PNG round trip executes and reduces pixels or codels on an exhaustive
  small-table corpus; constants are the positive control.

## Open problems

Research questions the proofs leave open.  Each names the first executable
step; an answer lands in the paper it extends, and the row leaves.

- **Brainfuck behaviour count.**  [brainfuck-count](proofs/brainfuck-count.md)
  brackets the growth rate of distinct behaviours (input-output maps on all
  inputs, repo model: clipped tape, `,` at EOF an error) of `C`-character
  programs: `4.1858 <= liminf B(C)**(1/C) <= limsup <= 7.0601`, from
  `[2.414, 7.388]`.  Upper: behaviour-preserving shortlex rewriting (dead
  loops, clears, diverging bodies, excursion commutation) and an exactly
  certified Perron bound on the irreducible words; the old `7.388` counted
  `[]` as removable, which is unsound when programs may diverge.  Lower:
  token families decodable from their event sequences, with reads sent to
  the nearest cell whose value is never printed again and nested loops
  attached to prints (four local rules make brackets decodable; the fourth, a
  read in every loop body, closes a gap where a read-free loop diverges and
  hides its output, lowering the old 4.1963), certified by a Collatz-Wielandt vector; loop-free programs alone
  lie in `[4.061, 2 + sqrt 5 = 4.236]`.  A single fixed input gives `>= 3.366`.
  Open: the limit.  Local rules have saturated near 7.06, so the upper side
  needs a global equivalence argument; the lower side needs a decodable
  loop gadget beating `4.236`; the nested family without the local rules
  certifies 4.2418 at `W = 6` and shows no collisions by brute force, so a
  decoding proof for it would settle that loops raise the rate.

- **Malbolge's first unreachable arity.**  Counting proves some 18-input
  table has no Malbolge program; 17 needs the program count a further
  `2**46076` down, and the length and alphabet cuts are dead
  ([limitations](limitations.md), Malbolge).  The live route is a dependence
  cut over the 24,434-cell threshold (the largest `K` with
  `C(59049, K) * 8**K < 2**131072`), but NOT per program: `'o'*59046 +
  '/<v'` computes the one-input identity and every one of its cells flips
  it, so some program for a table can depend on all 59,049.  With full
  stores a cell's first access is always a read, so dependent cells are
  touched cells; in the shipped constructions every sampled touched cell
  is dependent (3,416 at `n = 4`, 9,308 at 10, 16,650 at 11, at least
  19,007 at 12).  What survives is a cut over ONE program per table -- a
  normal form that strips nop runs and padding -- or a count of
  descriptions rather than of flip-sensitive cells.  Either way it is a
  density lemma: 17 inputs need 2.22 bits a cell against the 3 a cell
  holds, so every program must waste 0.78 bits a cell (the shipped builds
  store 0.14).  Next step: measure bits per cell of the tables computed
  by a scaled-down Malbolge (`3**6`..`3**7` cells, same decode and
  re-encipher) as the store grows; near 3 kills the route.  The shipped
  constructions reach 14 inputs (four copies over a three-level cascade);
  between them and 17 the least unreachable arity is unknown in both
  directions.

- **Polynomial's constant.**  `prop:bracket` in
  [polynomial](proofs/polynomial.tex) brackets `C_P n / T**2` explicitly:
  both limits in `[13/4 log10(2), 325/8 log10(2)]`, a factor 12.5 (down
  from 211).
  Lower side: counting with the relabelling symmetry (`lem:gapauto`,
  `prop:counting`) forces `T/(n+4)` input values for every `n >= 7`.
  Upper side: embedded automaton programs with an additive decoder
  (`lem:adddec`, `prop:embprog`, effective profile `325/8` per state
  squared, `lem:effprofile`) on a trie-banded automaton (`lem:trieband`,
  `lem:bandtrie`) with `(1 + o(1)) T/n` states for every `n`, so levels
  are CLOSED.  Open: profile (`325/8` against mass `13/4`).  Sources neither
  even nor odd pay mass `4` (`rem:parity`), even or odd ones `3`
  (`lem:evensigns`, both-signs rows on `E` with `f = x^e E(x**2)`), plus
  `1/4` for every large `n` by counting sign skeletons
  (`lem:evencount`, `cor:evenhard`; even or odd sources add and subtract
  only right after a read, `lem:symruns`; exact register arithmetic, the
  float `**` is a caveat).  The register and real roots are not
  charged, see the complex-roots row of the
  [coefficient-mass roadmap](https://github.com/bangyen/coefficient-mass/blob/main/ROADMAP.md).
