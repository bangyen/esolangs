# Roadmap

Open work only. See [limitations](limitations.md) for standing contracts
and proved limits; completed work is recorded in its commit.

## Conditional follow-up

- **Cyclic tag integration.** Its 94 complete backlinks clear the fame gate;
  [limitations](limitations.md) records the completed specification and
  generator audit. The direct padding construction emits 5T + 2n + 1 characters
  and passed 309 tables / 3,352 rows, plus sampled rows through n=14. Implement
  the semicolon-separated production parser, queue interpreter, ordered input
  embed, and final-deletion answer convention; register the language and add
  execution, VM, and convention coverage before integration.

- **Boolfuck, Subleq, and /// admission.** Fame scores are 76, 83, and 88;
  [limitations](limitations.md) records the specification audit and executed
  probes. Integrate Boolfuck's bit-stream I/O and prove rendered linearity;
  choose Subleq's I/O dialect and derive a linear rendered construction;
  derive ///'s general source-embedded generator. Execute every table through
  three inputs and sampled larger tables before integration. A failed build
  does not justify interpreter-only admission.

- **HQ9+, Nope., and Unary interpreter-only admission.** Scores are 136, 132,
  and 63; [limitations](limitations.md) records their generator obstructions.
  Pin HQ9+'s output/case conventions and Unary's decoded Brainfuck dialect;
  implement Nope.'s constant semantics without inspecting source or input.
  Add execution, VM, and convention coverage before integration.

- **Emmental and AsciiDots intrinsic-axis audits.** Curated recognition sources
  in [limitations](limitations.md) motivate investigation, not admission.
  For [Emmental](https://esolangs.org/wiki/Emmental), test whether redefining
  instruction meanings yields a construction or branch mechanism absent from
  the collection; its 43 backlinks do not clear the fame gate. For
  [AsciiDots](https://esolangs.org/wiki/AsciiDots), pin scheduling, dot
  duplication, interaction, and I/O semantics before comparing data-bearing
  paths with existing grid walkers. Admit either only after establishing a
  distinct axis and deriving an O(T) Boolean generator under the embed
  conventions. Execute every table through three inputs and sampled larger
  tables; record ambiguity or obstruction rather than inventing semantics.

- **Linear Boolean generators.**  Make build time and emitted size O(T), where
  T is the truth-table length.  For each remaining generator, either add a
  loop-less O(T) construction and an executed scaling regression, or record a
  structural proof that the language or required encoding forces super-linear
  output and continue with the next generator.  Generation time includes
  choosing an input order and writing the result.

  A language stays if its generator is O(T) on all four axes, its row has a
  proved language lower bound, or tests pin a semantic obstruction broken by
  every attempted construction. A syntax-level lookup table is not a
  generator. After one more executed round without a construction or bound,
  that language and row leave. An unproved wall is not a lookup table.

  Audit totality, generation time, output size, and execution time.
  `proofs/index.md` defines totality; `tests/proofs/deep/linearity.py` measures
  size by same-parity successive differences through n=12. Timings use the
  top five arities, best of three, and exclude loading; runs under 10 ms do not
  establish an exponent. Closure requires a language-wide lower bound. Current status:

  | Language | Totality | Generation time | Output size | Execution time |
  | --- | --- | --- | --- | --- |
  | Factor | Total | Language lower bound | Language lower bound | Linear |
  | Malbolge | Exception | Open | Linear | Linear |
  | Polynomial | Cap | Language lower bound | Language lower bound | Linear |

  Malbolge ships through sixteen inputs; finite source space excludes some
  18-input tables, leaving generation time at seventeen open. Its fixed
  59,049-character source makes output `O(1)`, while set cells grow linearly;
  see [malbolge-scaling](proofs/malbolge-scaling.md#the-emitted-size-law).

  Factor's worst-case encoding and language floor are `Theta(T log T)`;
  [factor](proofs/factor.md) gives the totality and generation bounds.
  Polynomial's language-level text complexity is `Theta(T**2 / log T)` and
  its generation time is super-linear; [polynomial](proofs/polynomial.md)
  proves both bounds and the parser's totality.

  Wider dense-table measurements give same-parity size-difference ratios
  3.971 (B-tapemark), 4.004 (6-5), 3.855 (Forth), and 4.211 (Vandevelo)
  over n=12,14,16. Circuit Diagram, after its n=8 route change, reads
  4.135 over n=10,12,14 and 4.119 over n=11,13,15. Parity tables read no
  higher. All remain inside the measured 4.4 contract; this is not a proof
  of linearity.

## Open problems

Each problem names a next executable step. Record its answer in the linked
proof and remove the completed item.

- **Brainfuck behaviour count.**  [brainfuck-count](proofs/brainfuck-count.md)
  brackets the growth rate of distinct behaviours (input-output maps on all
  inputs, repo model: clipped tape, `,` at EOF an error) of `C`-character
  programs: `4.2420 <= liminf B(C)**(1/C) <= limsup <= 7.0347`, from
  `[2.414, 7.388]`.  Upper: behaviour-preserving shortlex rewriting (dead
  loops, clears, diverging bodies, excursion commutation) and an exactly
  certified Perron bound on the irreducible words; the old `7.388` counted
  `[]` as removable, which is unsound when programs may diverge.  Lower:
  token families decodable from their event sequences, with reads sent to
  the nearest cell whose value is never printed again and nested loops
  attached to prints.  Reads in every body guarantee termination; alternating
  the first event type of directly nested bodies makes bracket direction
  decodable.  The exact Collatz-Wielandt certificate gives `2121/500 = 4.242`,
  above the loop-free ceiling `2 + sqrt 5 = 4.2360`.  Thus loops strictly
  raise the rate.  A single fixed input gives `>= 3.366`.
  Open: the limit and a sub-7 upper bound. The 7.0341 and 7.0194 certificates
  used `[Y[] -> []` for arbitrary balanced read-free `Y`, which is unsound:
  `+[-[]].` halts and prints NUL, while `+[].` diverges. The local-rule upper
  certificate was 7.0600257. Extended sound commutations, positive-pointer cancellation,
  print-loop rotation, and forced-divergence rules now certify 7.0347 with 11,673 DFA states.
  Next: count unrestricted rotation and forced-divergence bodies in the corrected grammar;
  the current regular monitors cap body bracket depth at one.

- **Malbolge's first unreachable arity.**  Counting proves some 18-input
  table has no Malbolge program; 17 needs the program count a further
  `2**46076` down, and the length and alphabet cuts are dead
  ([limitations](limitations.md), Malbolge).  The live route is a dependence
  cut over the 24,434-cell threshold (the largest `K` with
  `C(59049, K) * 8**K < 2**131072`). This cannot hold for every program:
  `'o'*59046 + '/<v'` computes the one-input identity and changing any
  cell flips it, so a program can depend on all 59,049 cells. With full
  stores a cell's first access is always a read, so dependent cells are
  touched cells; in the shipped constructions every sampled touched cell
  is dependent (3,416 at `n = 4`, 9,308 at 10, 16,650 at 11, at least
  19,007 at 12). A proof must count one normal-form representative per table,
  stripping nop runs and padding, or count descriptions instead of
  flip-sensitive cells. Either route requires a
  density lemma: 17 inputs need 2.22 bits a cell against the 3 a cell
  holds, so every program must waste 0.78 bits a cell (the sixteen-input
  build stores 1.11).  Directly sampling scaled stores cannot measure this:
  at `3**6` cells the threshold is 1,618 bits, so even the first expected
  collision needs about `2**809` programs (`2**2428` at `3**7`).  In 10,000
  random legal programs, 234 at `3**6` and 246 at `3**7` computed a total
  one-input table, but the sample itself caps any distinct-table estimate at
  0.0183 and 0.0061 bits a cell.  A local canonical form cannot shrink the
  alphabet either: every address admits one character for each of the eight
  operations, and a first-use cell can carry all three bits as data.  The
  constructive routes now fit the table in 49,152 cells.  The orbit packing
  maps its 2,401 collision pairs to free cells by a certified mixed-radix
  formula.  The five-state decoder runs all 2,744 one-group cases; the address
  fold and parity reducer now emit together as a 9,588-cell source, 5,151 of
  its 9,580 instructions overlapping table cells and 4,429 in the 9,897-cell
  complement.  Relocating alone leaves 317 cells, and the decoder needs
  thousands, so the remaining work is sharing setup, not placement.  See
  [malbolge-scaling](proofs/malbolge-scaling.md#seventeen-navigation-is-linear-in-address-so-packing-helps-measured).
  The shipped construction reaches 16 inputs; 17 remains undecided. A build
  needs more than two table bits in nearly every cell; an impossibility proof
  needs the density lemma.

- **Polynomial's constant.**  `prop:bracket` in
  [polynomial](proofs/polynomial.tex) brackets `C_P n / T**2` explicitly:
  both limits in `[13/4 log10(2), 325/8 log10(2)]`, a factor 12.5 (down
  from 211).
  Lower side: counting with the relabelling symmetry (`lem:gapauto`,
  `prop:counting`) forces `T/(n+4)` input values for every `n >= 7`.
  Upper side: embedded automaton programs with an additive decoder
  (`lem:adddec`, `prop:embprog`, effective profile `325/8` per state
  squared, `lem:effprofile`) on a trie-banded automaton (`lem:trieband`,
  `lem:bandtrie`) with `(1 + o(1)) T/n` states for every `n`. The level-count
  problem is settled; the profile remains open (`325/8` against mass `13/4`).
  Sources neither even nor odd pay mass `4` (`rem:parity`), even or odd ones `3`
  (`lem:evensigns`, both-signs rows on `E` with `f = x^e E(x**2)`), plus
  `1/4` for every large `n` by counting sign skeletons
  (`lem:evencount`, `cor:evenhard`; even or odd sources add and subtract
  only right after a read, `lem:symruns`; exact register arithmetic, the
  float `**` is a caveat).  The register and real roots are not
  charged, see the complex-roots row of the
  [coefficient-mass roadmap](https://github.com/bangyen/coefficient-mass/blob/main/ROADMAP.md).
  Retuning which states the embedded-automaton construction places inline
  cannot lower `325/8`: two unique successors per inline state force
  `a >= 1/2`, and its effective profile is minimized at `a = 1/2`, `x = 0`.
  Next: replace the instruction profile or raise the mass bound. Decoder
  parameter tuning cannot lower the constant.
  Spending a fraction `delta` of the band width to shrink its operands is
  also closed: even the favorable relaxed constant
  `(325/8 - 4 delta)/(1 - delta)**2` is minimized at `delta = 0`.
  Local opcode substitution is closed too: among one-arithmetic-instruction
  splits, adding `-48` and testing positive/zero has componentwise-minimal
  effective exponents `1,1,1,4`.
  Direct affine dispatch is also worse: replacing a fraction `t` of the
  quadratic-operand additions by multiply/add pairs changes the profile to
  `325/8 + 34t + 4t**2`.
  The parity count now exposes its missing algebraic charge: a separate hard
  table forces `(1-o(1)) T/(2n)` expensive gaps, and each but one forces a
  distinct Gaussian register-root pair (`lem:expensive-gaussian`,
  `cor:gaussianhard`).  Their Gaussian factor forces `8 log(K!) = Theta(T)`
  mass through one lowest coefficient (`lem:gaussian-low`), which is below
  the `T**2/n` constant scale.  Turning those pairs into quadratic
  coefficient mass is the remaining lower-bound step.
  The [common-norm subproblem](proofs/polynomial-common-norm.md) now has
  `Lambda(Q) >= K**2 log(R)/16` for the raw forced factor, and the same
  bound for scaled reciprocal or anti-reciprocal integer multiples of
  any degree.  Arbitrary integer multipliers remain open: support alone
  does not locate radius-charged coefficients, and local approximation
  bounds still need a cancellation-resistant height transfer.  Common
  norm is an extra hypothesis, not guaranteed for the register roots
  above; this checkpoint closes neither that general case nor the
  constant bracket.
  On the lower side, the two zero targets counted per expensive gap really
  are independent: symmetric remainder pairs realize arbitrary ordered
  first-zero positions from consecutive register values.  Raising `13/4`
  therefore needs a coefficient-mass charge for those Gaussian instruction
  roots, not a smaller transition count.  `lem:maximal-width` improves the
  independent first-essential residual width from `T/(4n)` to `T/(2n)`,
  but distinct residuals can arrive at one arithmetic cursor with different
  register values, so width alone does not supply distinct Gaussian roots.
  The parity case cannot be excluded: `prop:evenuniversal` gives even and
  odd symmetric decision-tree programs for every table, executed
  exhaustively through two inputs.  A matching lower bound must price
  parity sources themselves.

- **Factor leading constant.** [factor](proofs/factor.md#leading-constants)
  now brackets the worst-case minimum digits divided by `T*n` between
  0.11528442 and 0.29229475 asymptotically (2.535423-fold gap). The lower side
  counts weighted exponent compositions after local normalization and first-output pruning;
  the upper side prices a traveling counter and fixed signed-ball blocks and an almost-all
  prime-window covering bound.
  Parity encodings executed through five inputs do not determine either limit.
  Next: count only semantically distinct decoded programs to
  raise the lower coefficient, or construct a cheaper weighted command stream
  to lower the upper one; the existence and value of the limit remain open.

- **Vandevelo structural scaling.** Upkeep bounds `O(T)` lines and
  `O(T log n)` characters; identifier references still carry the extra
  factor. Exact fallback now transforms the quotient by a node's
  `d`-dimensional span: `O(n*|S|)` projection plus
  `O((n-d)*2**(n-d))` transform work per call. A forced six-input control
  executes the three-dimensional transform and matches full-space counts;
  280 generated programs retain identical source and all 2,536 rows execute.
  Affine-coset complements use direct violation guards: the n=12 one-zero
  table drops 40,938,391 candidate visits and shrinks from 333 to 277 characters.
  Next: remove the identifier factor, amortize projection and fallback calls,
  and bound the dual-basis core's aggregate work. Neither remaining gap is a
  language-wide lower bound; measured scaling does not settle them.

- **FRACTRAN order encoding.** One unchanged multiset of eight fractions
  computes all sixteen four-row tables by ordering each `1/p, 2/p` pair;
  all 64 rows executed. The one-consultation route is now closed negatively:
  fixed applicability and postprocessing give a linear threshold class,
  requiring at least `T-1` distinct fractions and `Omega(T log T)` text.
  A four-guard overlap cycle executes all 24 orders on four rows and
  realizes exactly fourteen tables, missing XOR and XNOR.
  See [the order bound](proofs/fractran.md#order-only-decoding-with-one-priority-consultation).
  Next: use repeated priority consultations with an admissible uniform-embed
  router to encode the table solely by ordering a fixed `O(T)`-text multiset.
  The indexed threshold route already achieves linear text by magnitudes.

- **Brainfuck on bounded inputs.** The finite-set upper bound is now
  `6.584428341`, below the all-input upper `7.0347`: delete unvisited reads,
  then count seven-command segments by a certified adjacency matrix.
  [Theorem 6](proofs/brainfuck-count.md#7b-bounded-input-upper-bound-theorem-6)
  also covers varying input sets with total read budget `o(C)`, including
  byte-input lengths at most `(1-eps)*log_256(C)`. The lower bound remains
  `3.366148`. Next: establish the limit or sharpen either side, and derive
  a nontrivial bound when input length is proportional to source length.

- **Execution and workspace bounds.** `scripts/screens/resources.py` executes
  constant, parity and seeded dense tables through eight inputs. Sophie
  advances monotonically through its source, using one accumulator and no
  stack; BFStack's seven-bit leaves give at most `100*n + 8192` commands
  and `2*max(n-7, 0) + 3` data-stack items. The benchmark's `--track-store`
  measures exposed memory cells and stack items, excluding code, hidden
  control stacks and integer bit widths. Next: count those omitted costs,
  and extend construction bounds to another generator. Run
  `python -m scripts.screens.resources --max-inputs 8`.

- **Independent grammar certificates.** `scripts/perron_certificate.py`
  checks exported DFA transitions and positive-vector inequalities using
  integers only; the 11,673-state Brainfuck certificate passes at
  `70347/10000`, and corrupted transitions, vectors and bounds are rejected.
  This certifies the supplied matrix, not the soundness of its rewrite
  grammar. Next: independently reconstruct forbidden-factor acceptance and
  check each rewrite's semantic side conditions with divergence controls.
  Export with `python -m tests.proofs._brainfuck_count --export notes/bf.json`,
  then run `python scripts/perron_certificate.py notes/bf.json`.

Controls are in `tests/proofs/test_research_tracks.py`. The linked proofs
close ordered input-forgetting construction, generated-family loading bounds,
and the weighted-description theorem.
