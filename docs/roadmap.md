# Roadmap

Only live work belongs here. Contracts and standing walls go to
[limitations](limitations.md); a closed row leaves, and its commit is the record.

## New interpreters

Implement the surveyed interpreter candidates in this order.  The first four
are the 2026-09-19 re-run of the `Category:Unimplemented` x
`Category:Two-dimensional languages` pass (116 pages, up from 111); the
verdicts are spec reads, not executed generators, so the size question is open
for every entry.  Piet is already implemented, so it was never in the screen;
INTERCAL, listed last, is outside the pass.

- **thisthat** (2025): the strongest untouched survivor.  The 2026-09-02 audit
  filed it unread, thinking the `{{:thisthat}}` transclusions hid the node
  table; they inject only a CSS `style=` string, so the table is in the
  wikitext.  Native gates -- `◘` NAND, `□■▦` NOR/OR/XOR with `□■` also
  emitting 0/1, `◇` one-bit input/output, `◐◑◒◓` bit-conditioned routing --
  make a combinational network the natural generator, a construction the set
  does not occupy.  Settle `◨⬒` and the partial-node cases first, and dodge
  `◘`'s random pointer pick by construction.
- **Self-replicating marbles** (2024): a second gate-native pick the 2026-09-02
  audit missed -- it recorded "no input or output vocabulary", but `i` and `o`
  are in the command table and the NAND example uses both.  A marble carries one
  bit, `?` deletes it on 0, and two marbles on one tile merge with NAND; a
  marble leaving a section replicates to every instruction of the next, a
  fan-out primitive the set does not have.  Pin "the next section" and the
  collision tick before building.
- **Wirefunge** (2011): native not/and/or/xor/nor/nand/xnor gates over
  bit-addressable `a-h`/`1-8` ports, but the page is a self-labelled "Draft
  Spec" and propagation is simultaneous.  Pin one evaluation order, then admit.
- **Gridify** (2026): the most complete new spec -- Befunge-style stack, `~`/`&`
  in, `.`/`,` out, a four-way `?` dispatch -- but its construction is the grid
  walk the set already has.  Last: admit only if it forces a new axis.
- **INTERCAL** (1972): not from the 2D pass, and not a completeness add -- the
  well-known candidates otherwise re-occupy an axis the set already has, and
  the collection is curated by admission, not coverage.  INTERCAL is the
  exception: `COME FROM` is pull-based, label-triggered transfer, where every
  branch here is push/conditional/jump/pointer, so it forces a new branch
  mechanism.  Spec read only, not priced: whether a loop-less O(T) construction
  survives the computed-label and `COME FROM` wiring, and whether its binary
  I/O routes through the package's stdin convention, is the work.

- **Classic-language audit.**  Spec-read Thue, FRACTRAN, Unlambda, and FALSE
  against the admission test, using brainfuck, Befunge, Malbolge, Piet,
  Whitespace, and Super SNUSP as the retained comparison set.  For each
  candidate, identify the new axis, deterministic semantics, stdin route, and
  a loop-less Boolean construction or a documented obstruction.  Promote only
  survivors to ordered interpreter work; record rejections in limitations.

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
  | Factor | Total | Language lower bound | Language lower bound | Linear |
  | Malbolge | Exception | Open | Open | Linear |
  | Polynomial | Cap | Language lower bound | Language lower bound | Linear |

  Malbolge cannot be total: its finite source space omits some 18-input truth
  tables.  Its shipped constructions cover every table through eleven inputs;
  generation time and size remain open over the reachable gap below that
  language ceiling.

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
  graph is outerplanar, giving `m_routing < 3L_real`.  The routing lemma gives
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
  every generated factor peels and cold parsing is polynomial; arbitrary
  programs outside the envelope retain the general factorization fallback.
  Conservative generation and cold-parse work/memory estimators cover the
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

- **Image-source candidates.**  A read of the 129 `Category:Non-textual` pages
  for raster sources only -- music (Fugue, Velato), music-note, and
  steganography pages excluded.  Verdicts are spec reads, not executed
  generators.  Brainloller and Braincopter are not popular enough to clear
  the collection's alternative admission route.
  Deferred: Bytemap (2012, source and data the same self-modifying grid, no
  interpreter yet) and Gifunk (2021, APNG/GIF fungeoid whose IP crosses frames)
  are the
  only image languages beyond Piet that force an axis the set lacks, both WIP;
  Turing Paint (2020, six hand-drawable colours) needs the website, not the
  wiki stub; Befunk (2014, Befunge-98 in PNG, Funk value
  `(R%10)*100 + (G%10)*10 + B%10`) waits on Befunge-98 and a construction that
  dodges `?`'s random delta.  Rejected: HuePrism (output-only, no input
  interface) and BitCode/PicCode (no interpreter, no numbers); the Minecraft
  ports are game-save media, not a reproducible raster.

## Open problems

Research questions the proofs leave open.  Each names the first executable
step; an answer lands in the paper it extends, and the row leaves.

- **Extremality of the escaping placement.**  `T = tau*` (escaping exempt
  coefficients extremal) is still the step `tau_k(X) <= tau_{k+1}(X \ {max
  X})`, which has no known counterexample.  The step is proved unless the
  minimizer `Z^-` for `X' = X \ {g}` straddles `g = max X` with a gap
  below `g`: `prop:stepeasy` (aligned), `prop:slidealigned` (a minimizer at
  or below `g`), and `thm:slideinitial` (smooth the minimizing certificate
  against the new node, `v = (1 - y_c x F)/(1 - y_c x)`, tail
  `<= y_c/(1-y_c)` times the target; it vanishes on the initial segment and
  has the opposite sign at `g`, so the segment to `F` crosses `v_g = 0`
  inside the certificates for `X`, whatever zeros lie above `g`).  The slide
  with all other zeros fixed is FALSE (nine nodes `1/2 - i*10^-4`,
  `B = {1,2,3,11,12,13}`, `g = 4`, `M = 6`, every point of the slid line
  `1.026x`), so the one inequality is now `eq:shift`: with `B_0 = Z^- n (0,g)`
  and `A = Z^- n (g, inf)`, `Tail_c(B_0 u {g} u (A+1)) <= Tail_{c-1}(Z^-)`
  whenever no single move `a -> a+1` (`a in A`) lowers the tail, which
  minimality gives; `prop:shift` proves that it implies the step, that for
  `|A| = 1` the hypothesis is the half-mass condition
  `sum_{d<=M}|H_d| >= sum_{d>M}|H_d|` on the `ell_inf` direction, and the
  confluent block case (`B_0 = {1..k}`, `g = k+1`, `A = {M}`: hypothesis and
  conclusion both `<=> M >= 2k+2`, equality iff `M = 2k+2`, by the
  negative-binomial identities).  Evidence: 0 failures in 7023 instances
  with the hypothesis at `L <= 9` (clustered and random nodes, `|A| <= 5`),
  283 failures without it; `|A| = 1`: 0 in 6015 more at `L <= 7` and 0 in
  468 confluent gap instances; worst ratio 0.9993 (clustered
  `B_0 = {1,2,3,4}`, `g = 5`, `A = {10}`), 1 at the confluent block.
  Structure for a proof: on the plane `P = {v_0 = 1, v_{B_0} = 0}` every
  certificate is `v_d = H_d (alpha + beta theta_d - rho_d)` with
  `theta = K/H` (`K` the `c`-node hom on `{0} u B_0 u {M+1}`) and
  `rho = -F_M/H`, both monotone in `d` and `rho` concave in `theta` by the
  zero bound, so `Tail` is a weighted `l^1` affine regression, `F_a` the
  constant fits, `p_{ab}` the chords; the `|A| = 1` case is `cost <= gain`
  with `gain = Tail(F_M) - Tail(p_{M,M+1})` (the deletion step, eq:split) and
  `cost = Tail(p_{g,M+1}) - Tail(p_{M,M+1})` along `ell_{M+1}`, and
  `cost/gain` reaches 0.9991, so every loose bound from eq:gamma fails: the
  proof must be exact, as the block proof is.  First step: prove
  `eq:chord`, the hypothesis-free chord lemma
  `Tail(F_M) >= lam Tail(F_{M+1}) + (1-lam) Tail(p_{g,M+1})` with `lam`
  from `p_{M,M+1} = lam F_{M+1} + (1-lam) p_{g,M+1}` on `ell_{M+1}`
  (`(M-g)/M` confluent); it says the deletion-step gain `eq:split` is at
  least the convexity gap along `ell_{M+1}`, it plus the hypothesis gives
  the `|A| = 1` case, it holds in 4632 exact instances with no hypothesis,
  and it is an identity in the block case exactly when the new node is at
  the cutoff `1/2` (strict below it; confluently it is the NB closed form of
  `E|D-M|`); it does not extend verbatim to `|A| >= 2`, and it is FALSE for
  real zero positions (confluent `B_0 = {1, 5/2}`, `g = 3`, `M = 6`), so a
  proof must count the empty integer slots below `g`, not argue by
  convexity or continuity in the zeros.  Dead: the half-mass point of
  `ell_M` (fails at the confluent block `B = {1..24}`, `g = 25`, `M = 50`),
  any fixed window, shifting only the smallest zero above `g` (fails at
  `L = 5`), arbitrary weights with the same decay (the regression form fails
  for them), deleting `min X`, freeing the largest zero, adjoining without
  sliding, block-plus-one zero sets, a real-valued zero position, pointwise
  deflation at `r_1 <= (3+sqrt 5)/2`.
  Also open: that `tau*` is always attained by a full certificate with a
  multiplier witness.  Repeated roots beyond `(3,3)` are open too, as is the
  case where an exempt root lies below 2 and more than `u` partial sums of
  `P` exceed `|P(1)|`, where the repaired bound need not be sharp.  See the
  section "The infimum when the criterion fails" in
  [coefficient-mass-attainment](proofs/coefficient-mass-attainment.tex).
