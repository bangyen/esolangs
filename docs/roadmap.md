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
  X})`, which has no known counterexample.  Write the minimizer for
  `X' = X \ {g}`, `g = max X`, as `Z^- = B_0 u A` with `B_0` below `g` and
  `A` above.  The step is PROVED when `B_0` is an initial segment
  (`thm:slideinitial`, any `A`), when `A` is empty (`prop:stepeasy`), and
  when `|A| = 1` (`cor:shiftone`): the shift-by-one inequality `eq:shift`
  (`Tail_c(B_0 u {g} u (A+1)) <= Tail_{c-1}(Z^-)` whenever no single move
  `a -> a+1` lowers the tail, which minimality gives, `prop:shift`) follows
  for `A = {M}` from the hypothesis-free chord lemma `prop:chord`:
  `Tail(F_M) >= lam Tail(F_{M+1}) + (1-lam) Tail(p_{g,M+1})` with `lam` from
  `p_{M,M+1} = lam F_{M+1} + (1-lam) p_{g,M+1}` on `ell_{M+1}`.  Its proof:
  the difference equals `sum_{e<g} delta_e + sigma sum_{g<d<=M+1} E(d) -
  sigma sum_{d>=M+2} E(d)` (`eq:chordsplit`) with `E(d) = (F_M - p)(d-1) +
  2(1-lam) w(d)`, an exponential sum whose zeros at the consecutive pairs of
  `{0} u B_0 u {g}` and at `M+1`, signs at the gap starts, and weight on the
  new node (sign fixed by the cutoff `y <= 1/2`) pin its sign on the window
  by the zero bound; equality iff the block `B_0 = {1..g-1}` at the cutoff.
  OPEN: `eq:shift` with `|A| >= 2`, i.e. a gap below `g` and at least two
  zeros above it in the minimizer.  Evidence: 0 failures in 7023 instances
  with the hypothesis at `L <= 9` (clustered and random nodes, `|A| <= 5`),
  283 failures without it; worst ratio 0.9993.  What is known about it: the
  chord of `prop:chord` does NOT extend.  With `M` the end of the first run
  of `A` and `C` the other zeros, `eq:chordsplit` holds with `B_0 -> C`
  only with the LOCAL sign `s_d = sigma (-1)^{#(C n (g,d))}` (the global
  `sigma` form is false in every instance); `E` is short one forced zero
  per run of `A` above `M+1`, and the chord fails at `L = 9`, clustered
  nodes, `B_0 = {1,2,3,5,6}`, `g = 7`, `A = {8,12}`, by 19%, all in the far
  term.  No fixed weights work (<= 0.683 at `L <= 7`, >= 0.794 at `L = 9`).
  The case split on whether the far sign is pinned is DEAD: pinned implies
  the chord (never violated) but pinning never occurs with a gapped `A`,
  and unpinned does NOT imply the hypothesis fails (552 of 1515 unpinned
  at `L = 9` satisfy it).  What DOES hold, 0 failures at `L <= 10` and
  `|A| <= 3` (least relative slack 0.063, against 150 chord failures at
  `L = 10`, all violating the hypothesis): `Tail(Z^-) <= Tail(F_1)` implies
  the chord, which with `prop:shift` closes the case.  Prove THAT.  The
  hypothesis equals the mass form `sum_{d<=M}|H_d| >= sum_{d>M}|H_d|` for
  the `(L-1)`-node sum `H` vanishing on `{0} u C` -- indeed `F_M - F_1 =
  alpha H` (one-dimensional space) and the GAP IDENTITY `T1 - TM =
  |alpha| (mass_le - mass_gt)` holds exactly at every tier to `L = 10`.
  Dead for it: first-order convexity (`Tail` IS convex along `[F_1, w]`
  and `TM - Tp >= DD` always, but `DD >= D` fails 1089/1600 at `L = 9`,
  64 under the hypothesis, so no supporting hyperplane works); and any
  hypothesis-free bound of `(1-lam)(T1 - Tw)` by `|alpha| mass_le` (it
  would prove the chord unconditionally, which the failures refute -- the
  far mass MUST enter); and `BELOW * mass_gt >= (-ABOVE) * mass_le`, which
  passes `L <= 7` and fails at `L = 9` and `L = 10` (the c<=7 trap again).
  Dead: the
  half-mass point of
  `ell_M`, any fixed window, shifting only the smallest zero above `g`,
  arbitrary weights with the same decay, Schur/LPP positivity (the cleared
  polynomial has thousands of negative terms even at the cutoff), deleting
  `min X`, freeing the largest zero, adjoining without sliding,
  block-plus-one zero sets, real-valued zero positions (`eq:chord` is false
  there), pointwise deflation at `r_1 <= (3+sqrt 5)/2`.
  That `tau*` is always attained by a full certificate with a multiplier
  witness is now PROVED (`prop:attain`): the tail is a norm, so the infimum
  is attained; a minimiser with fewer than `m-1` zeros can be moved along a
  direction that keeps its zeros until it gains one, the move being finite
  because the zero bound makes the sign of the kink parameter eventually
  constant; the multipliers come from the nonsingularity of the exponents
  `{0} u Z`; and the witness is constant past `max Z`, so `(1-y)W` is a
  polynomial and its cofactor a monic `M`.  It needs only distinct nodes in
  `(0,1)` -- no `r_1 >= 2` cutoff.  The same proof runs in the confluent
  basis `d^a y^d`, where the zero bound is Polya-Szego; checked exactly with
  witnesses on 9 repeated-root sets.  Repeated roots beyond `(3,3)` are open on the
  PLACEMENT side only (`u >= 1`; at `(3,3)`, `u = 0` and `tau* = 5/24`, so
  the infimum of `b_1` is 24/5): a proof needs confluent analogues of
  `prop:partial`, `thm:converse` and `thm:value`.  Round 11 REDUCED that to
  ONE step.  In the Hermite basis `d^a y^d` ordered by growth, Descartes
  counts with multiplicity, the Vandermonde change of variables becomes
  Hermite interpolation on a multiset, and `thm:value`'s unisolvence and
  positivity steps are `prop:confluent`'s `M(0)` and Polya-Szego -- all
  routine; `prop:partial` needs only the extra hypothesis that the cut is
  ALIGNED with the blocks (`r_u < r_{u+1}`).  The one step that FAILS is the
  minor estimate inside `lem:far`, which `thm:value` reuses verbatim:
  `c = prod (1 - y_b/y_a)` is 0 the moment two nodes coincide, so
  `|alpha_{J*}| >= c M_{J*}` is vacuous, and `alpha_{J*}` can vanish outright
  -- at `(3,3,4,4)`, `u = 3`, the span of `d(1/3)^d, (1/3)^d, d(1/4)^d` has
  `(2187/16384) d(1/3)^d - (15309/8192)(1/3)^d + d(1/4)^d` zero at
  `d = 6,7,8` (the ONLY singular triple in `{1..13}`; none with
  `min E >= 21`; the full 4-function basis has no singular 4-subset of
  `{0..11}`).  The rate degrades too: `sup eta` over a window is
  `Theta(1/min E)` -- exactly `1/(n0+1)` at `(3,3)`, `(2,2)`, and
  `(3,3,5)`/`(3,3,4,4)` with `u = 1` -- when the cut falls INSIDE a
  multiplicity block, against geometric at an aligned cut (2.1e-23 at
  `(2,3,3)`, 3.0e-30 at `(3,3,5)` `u = 2`, `n0 = 140`).  Round 12 then PROVED
  the replacement (`prop:conffar`, commit below) for `E` of BOUNDED DIAMETER,
  which is a CLUSTER EXPANSION: write `E = {n+f : f in F}` with `F` fixed,
  pull `z_i^n` and `n^a` out of each column to get
  `Lambda_J(n) = (prod z_i^{n k_i}) n^{P(J)}`, then expand
  `(1+f/n)^a = sum_b C(a,b)(f/n)^b` multilinearly.  Columns at one node that
  pick the same `b` are equal, so `sum b >= sum_i C(k_i,2)` with equality only
  at `{0..k_i-1}`, giving
  `alpha_J = +- Lambda_J n^{-sum C(k_i,2)} [kappa_J W(F;k) + O(1/n)]` with
  `kappa_J = prod_i prod_{t<t'}(a_t' - a_t)/prod_{s<k_i} s! > 0` and
  `W(F;k) = det(f^b z_i^f)` the UNGAPPED alternant, nonzero by Polya-Szego.
  So the degeneracy is harmless: a gapped alternant's leading term is a
  POSITIVE MULTIPLE of the ungapped one, and a gap only moves the power of
  `n`.  `J*` greedily fills the largest nodes and takes the TOP exponent
  segment at the cut node, so it uniquely maximises both `sum k_i log z_i`
  (others lose `kappa = min log(z_i/z_{i+1})`) and `P`; hence
  `Lambda_J/Lambda_J* <= 1/n` at equal profile and `<= n^{Nk} e^{-kappa n}`
  otherwise.  VERIFIED independently (tmp/esc/verify12.py, exact Fractions,
  N=10, z=1/2,1/3,1/5, mults 3,4,3, gapped `J` included): alpha/prediction
  -> +-1 with error falling exactly 10x per decade of `n`.
  CONSEQUENCE: confluent `thm:value` is CLOSED -- it uses only
  `E_nu = {nu+1..nu+u}`, diameter `u-1`.  STILL OPEN: confluent
  `thm:converse`, whose proof lets the elements of `E_nu` separate.  Round 13
  REDUCED that to ONE scale-free inequality.  PROVED there: the cluster
  expansion is EXACT for every `E` (no fixed-`F` hypothesis) --
  `alpha_J(E) = Lambda_J(n) sum_b (prod C(a,b_ia)) n^{-|b|} W_b(F)` with
  `n = min E`, `F = E - n`, boundedly many terms -- so ALL dependence on the
  shape of `E` sits in the `W_b(F)`.  PROVED: `W(F;k)` never vanishes (its
  SIGN is a column-ordering convention -- I checked 400 instances, 0 zero,
  and the sign is constant across `F` for each of 50 profiles, so the
  "positivity" claim is convention, the content is nonvanishing).  PROVED
  (Lemma B): the inequality `eq:altratio`,
  `|W_B(F)| <= C (1 + max F)^j |W(F;k)|` with
  `j = sum_i (sum B_i - C(k_i,2))`, IMPLIES the whole open case -- it makes
  the tail geometric once `max F <= tau n`, giving `alpha_J* != 0` and
  `eta = O(1/min E)` for ARBITRARY gap structure.  PROVED: `eq:altratio` at a
  single node (the ratio is a Schur polynomial `s_mu(F)`, `|mu| = j`), and
  `min F >> diam F` reduces to `min F = 0` (depth-1 recursion, constants do
  not compound).  Round 14 PROVED `eq:altratio` OUTRIGHT
  (`prop:altratio`): give each COLUMN its own variable, so
  `W_B(F) = [Theta_B det M(x)]` at the confluent point with
  `Theta_B = prod (x d/dx)^b` of order `M_0 + j`, `M_0 = sum C(k_i,2)`; by
  the bialternant identity `det M(x) = +- s_lambda(x) V(x)` with
  `lambda_u = f_{k+1-u} - (k-u)`; `V` is divisible by the `M_0` forms
  `x_{i,b} - x_{i,b'}` that VANISH at the confluent point, so Leibniz leaves
  only `|alpha| <= j` derivatives of `s_lambda`, giving
  `W_B(F) = sum_{|alpha|<=j} c_{B,alpha} (d^alpha s_lambda)(Z)` with `c`
  INDEPENDENT of `F`; and `s_lambda` is monomial-positive with every exponent
  `<= lambda_1`, so `d^alpha s_lambda(Z) <= (lambda_1/z_p)^{|alpha|}
  s_lambda(Z)`.  At `j = 0` this also re-proves `W(F;k) = +- c_0 s_lambda(Z)
  != 0`.  I VERIFIED the crux independently (verify14.py): `W(F;k)/s_lambda(Z)`
  is the CONSTANT `-1/53204107681274414062500000000` over 10 sets `F` with
  `max F` from 11 to 371, `z=(1/2,1/3,1/5)`, `k=(3,4,3)`.  Ingredient (L)
  also falls out: `lambda` depends only on `F`, both confluent points have
  coordinates in `[z_p, z_1]`, so the two Schur values differ by at most
  `(z_1/z_p)^{|lambda|}`, `|lambda| <= k max F <= k tau n`, and `tau` shrinks
  until `e^{-kappa n}` beats it.  WHAT IS LEFT, after round 15, is
  TWO isolated items in a BETTER FRAME -- expand over NODES, not clusters.
  PROVED there: the node expansion
  `alpha_J(E) = sum_{E = u E_i} eps prod_i z_i^{sigma(E_i)} D_i(E_i)`,
  `D_i(E_i) = det(e^a)`, exact for every `E`, so all node dependence is an
  explicit monomial and each `D_i` is a PLAIN generalized Vandermonde; the
  two-sided bound `Pi*Delta <= |D_i| <= C_N*Pi*Delta` with
  `V(E_i) = (prod e_(u)^{k_i-u}) Delta(E_i)`, `Delta = prod (1 - e/e')`, `Pi`
  the sorted pairing (I VERIFIED this: 600 instances, lower bound ATTAINED at
  ratio exactly 1.000000, upper max 3304, 0 vanishing -- verify15.py); the
  exchange lemma (sorted pairing maximises the monomial); pointwise
  domination giving `N_J/N_J* <= max(1/min E, e^{-kappa min E/2})` at EQUAL
  profile; and the aligned-cut case `alpha_J* != 0` for every `E` from
  `prop:altratio`.  Round 16 then PROVED (C') FOR THE SORTED
  PARTITIONS: the `u`-th function of `J` in growth order never precedes that
  of `J*`, the true node mismatches are the prefix intervals
  `(c_j(J), c*_j]`, every deficiency `delta(u,v)^{-1} = g_u/(g_u - g_v)` is
  `<= 2 g_v`, and the pair `(u,v)` CHARGES to slot `v`, which such a pair
  always forces into the mismatch set; a slot is charged `<= k-1` times, so
  `W_J/W_J* <= 2^{k-1} n^{abar+k-1} e^{-kappa n}` -- reproving the geometric
  rate at a split profile.  REMAINING: (G) `N_J <= C(N) W_J` (the sorted
  partition attains the max up to a constant) -- observed, constant `<= 32.4`
  over 4000 instances at `N = 9,10,12`, no growth in `min E` or spread; with
  (G), (C') follows since `N_J* >= W_J*` for free.  And (L)
  `|alpha_J*| >= c N_J*` is still OPEN -- observed `>= 3.2e-3` and INCREASING
  in `n`.  NEGATIVE RESULT, exact witness -- the sorted partition is NOT even
  the largest term, so (L) cannot come from termwise domination and must come
  from SIGNS: at `z = (1/3,1/4)`, `m = (2,2)`, `k = 3`,
  `E = {n,n+1,n+2}`, the partition `({n,n+2},{n+1})` beats the sorted
  `({n+1,n+2},{n})` by exactly `3*2*(1/4)*(n+1)/n` = 1.575 at `n=20`, tending
  to `2 z_2/z_1 = 3/2`, with the runner-up a fixed 2/3 of the max forever
  (I re-derived this ratio by hand: sorted `(1/3)^43 (1/4)^20 * 20` vs
  `(1/3)^42 * 2 * (1/4)^21 * 21`).  NEGATIVE RESULT -- do NOT retry
  the cluster/Laplace route: two clusters with the SAME profile but different
  exponent assignments compete at a ratio the separation bounds only by a
  CONSTANT, so no termwise domination exists there however small `tau` is.  And with gaps `floor(sqrt n)` and
  `N=10`, `eta * min E` ran to 1.000 at `k=4` and 2.98 at `k=6`
  (verify12b.py), the same `Theta(1/min E)`, so the lemma is expected TRUE.
  DEAD: `|alpha_J*| ~ M_J* prod_{same-node}(1 - e_s/e_t)` (fails at `k>=6`,
  ratio 4e-16 at `N=11, k=10`; exact for `k<=5`, another small-size trap).
  Also open is the
  case where an exempt root lies below 2 and more than `u` partial sums of
  `P` exceed `|P(1)|`, where the repaired bound need not be sharp.  See the
  section "The infimum when the criterion fails" in
  [coefficient-mass-attainment](proofs/coefficient-mass-attainment.tex).
  The companion question -- which root sets make `eq:order` an infimum for
  `k >= 2` (`coefficient-mass.tex`, end of the sharpness section) -- is
  settled for distinct roots by the partial-sum criterion
  (`prop:partial`, `thm:converse`) and is open exactly where this row is:
  repeated roots, pending confluent `thm:converse`.

- **Factor's constant.**  On GRH, `0.1505 <= C_F(T)/(T log T) <= 0.3416`, a
  ratio of 2.27 (`rem:gap` in [factor](proofs/factor.tex)); without GRH the
  ceiling is `0.3660`.  Number theory no longer separates the two: the gap is
  whether Brainfuck programs of `C` characters have nearer `(1+sqrt 2)**C`
  behaviours (the tapes a drawing reaches) or `(1+lambda)**C`,
  `lambda = 6.388` (the words free of the five cancelling adjacencies).  The
  floor rises as far as that count falls; the ceiling falls only if control
  flow carries more than `log2(1+sqrt 2) = 1.27` bits a character.  Within
  the drawing model the digit floor is `1/(2 log 10) = 0.217`, not yet met
  by `lem:draw`'s digit count.  Small-`C` enumeration does not settle it:
  over reduced words to `C = 10` (wrapping cells, left-clipped pointer,
  0/1 input bytes), drawings grow at 2.420 by `C = 16`, as `prop:drawing`
  says, but loops overtake them near `C = 11` and the I/O-only and
  full-prefix behaviour ratios are still climbing (4.09 and 4.52 at
  `C = 10`), so any fitted base is a lower estimate.  DEAD: quotienting
  loop-free I/O-free segments by their tape effect -- the transfer matrix
  over `.,[]` gives base 7.371 against 7.388, a floor of 0.1507; the
  count lives in short segments between separators.  Forbidding local
  patterns whose deletion preserves behaviour (the paper's count admits
  only deletions, so `[+]` -> `[-]` is not sound) barely helps either:
  a dead `+`/`-` before a clear loop and never-exiting pointer-neutral
  loops to body length 9 give 7.3787, floor 0.15062; adding `+,`/`-,`
  gives 7.1102, floor 0.1535, but that rule is sound only if `,` at end
  of input fails (the repo's interpreter raises `EOFError`), a convention
  `factor.tex` must state before relying on it.  A real gain needs a
  global equivalence argument, not a forbidden-pattern list.

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
  re-encipher) as the store grows; near 3 kills the route.  The `n = 14`
  route is written but refused: its annealed constants (`_F_SELECT12`,
  `_F_SELECT13`, `_F_LEVELS`, `_F_LINKS`) are still placeholders.  Between the shipped
  constructions and 17 the least unreachable arity is unknown in both
  directions.

- **Intermediate rows of `b_k`.**  `b_k(F) >= L - k + 1` for every monic
  multiple of `(x-2)**L` is proved for `k = 1, 2` (`prop:neartwo`),
  `k = L` (`thm:order`) and `k <= L/8` once `L >= 13`
  (`prop:quadratic`); the rows `max(2, L/8) < k <= L - 1` are open, with
  exact LP sweeps as the only evidence ([coefficient-mass](proofs/coefficient-mass.tex)).
  The dual is `max |q(0)| / sum_{s not in S} |q(s)| 2**-s` over `q` of
  degree `< L` vanishing on the exempt distances `S`.  Its tightest `S` is
  the bottom `k - 1` positions, each costing one degree of `q`, so the
  limit of row `k` at `L` is row 1 at `L - k + 1`; rows `L - 1` and `L` are
  asymptotically sharp, the rest carry growing slack, and tight duals are
  `prod_{z in Z} (1 - s/z)` with integer `Z` containing `S`.  PROVED from
  `sum_{s>=1} |prod_{z=2}^{n} (1 - s/z)| 2**-s = 1/n`:
  `b_k >= (L-k+1) / prod_{u in S} max(1, D/u - 1)`, so the row holds
  whenever the top `k - 1` coefficients all lie in the lower half of the
  degrees.  The open rows now REDUCE to one `D`-free lemma: `T(n)`, for
  every finite set `A` of positive integers some real `r` of degree
  `<= |A| + n - 1` with `r(0) = 1`, `r = 0` on `A` and
  `sum_{s>=1} |r(s)| 2**-s <= 1/n`.  `T(L-k+1)` implies row `k` at every
  `D` (take `A` the exempt distances below `D/2` and multiply by
  `prod (1 - s/u)` over the rest, each factor at most 1 on `1..D`), and is
  necessary as `D -> oo`; `A` empty is the identity above.  Checked in
  exact rationals for every `A` in `{1..12}`, `|A| <= 4`, `n <= 4`: the
  empty set is always the worst `A` (`n` times the optimum 1, 1, 1.212,
  1.461), nonempty `A` carrying slack at least 1.33.  Next step: prove
  that adjoining a zero to `A` never lowers the optimum.  DEAD: zeros
  scaled with `|A|` (`A = {11, 12}`, `n = 3`: 0.78), `Z = {2..n}`,
  first-free, odd and shifted-past-`S` choices, and trading one exempt
  point for one degree (it can lose a factor 4).  Floating LPs (HiGHS) report values below the
  bound from `D = 30`; check large-`D` optima with exact rational duals.

- **Polynomial's sharp constant.**  The language bound is proved by the
  slack certificate; the sharp form -- a coefficient of at least
  `(1 - o(1)) prod_{i>u} (p_i - 1)` with `u` coefficients free -- would
  give its constant, and has two gaps ([polynomial](proofs/polynomial.md), "The
  iterated elimination"): (a) the certificate is proved only for free
  positions `U = {0..K}`, though sweeps put the least threshold there for
  every `U`; (b) it is asymptotic in `D`, and the finite-`D` statement
  reduces to the skew-Schur inequality
  `s_{((d-c+1)**(c-1))} s_{lambda_B/mu} >= (prod rho)**(d-c+2) s_{lambda_A/mu}`,
  now proved for every `c` (Schur-positive by Pieri and dual Pieri; see
  *General `c`* in [polynomial](proofs/polynomial.md)), which closes (b).
  Left: (a).  Untested route: the certificate entries for any `U` are
  ratios of Schur functions `s_{lambda(U)}(r)`, so minimality at
  `U = {0..u-1}` is a monotonicity statement for such ratios as one part
  moves up -- the shape of the Lam--Postnikov--Pylyavskyy inequality
  `s_mu s_nu <= s_{mu v nu} s_{mu ^ nu}`.
