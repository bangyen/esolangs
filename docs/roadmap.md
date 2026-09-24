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
  | Malbolge | Exception | Open | Open | Linear |
  | Polynomial | Cap | Language lower bound | Language lower bound | Linear |

  Malbolge cannot be total: its finite source space omits some 18-input truth
  tables.  Its shipped constructions cover every table through fourteen inputs;
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

- **Coefficient-mass sharpness, residue.**  CLOSED in
  [coefficient-mass-attainment](proofs/coefficient-mass-attainment.tex):
  extremality of the escaping placement for distinct roots `>= 2`
  (`thm:extremal`, run chord), the partial-sum criterion at repeated roots
  (`thm:converse`, `cor:charrep`, Descartes at infinity), and the repaired
  bound below 2 (`cor:repairedsharp`: with an exempt root below 2 it is the
  infimum exactly under `prop:subtwosharp`'s hypotheses; the two-sided bound
  `min(|P(1)|, |P_u(1)|)` of `cor:twosided` beats it when the exempt roots
  straddle 2, with its own criterion `thm:twosidedsharp`).  Repeated roots are CLOSED too (`thm:extremalrep`,
  `thm:twosidedsharprep`, via the coalescence limit `lem:coalesce`), and so
  is the shift with its hypothesis at run ends (`cor:shiftend`, via the
  three-point bound `lem:threepoint`).  Below the cutoff the value is a
  finite computation for every `u` (`thm:finite`: `T` is a max over
  placements in `[1, u(L-u)Delta]` of minima over zero sets within
  `(L-1-u)Delta` of the placement; e.g. `(11/10, 3, 5, 7)`, `u = 2`:
  `inf b_3 = 294156/21995` at `X = {2,4}`).  Attainment and the far-zero
  rate are settled too (`thm:noattain`, `thm:attainchar`, `prop:farrate`).

- **Coefficient mass at complex roots.**  Purely imaginary pairs are CLOSED
  ([coefficient-mass](proofs/coefficient-mass.tex) `thm:transfer`,
  `cor:imag`: by multisection a pair `+-ci` is worth exactly one real root
  `c**2`, rows, mass and sharpness included), and the first row holds at
  every root set (`prop:rowone`).  Beyond that no bound can depend on the
  moduli and the angles alone (`prop:noangle`: `x**(2M) + rho**(2M)`).
  At Gaussian-integer pairs, integer multiples split into blocks
  (`lem:gausscarry`, `lem:gaussblocks`) each paying `log(rho_min/2)` per
  degree (`thm:gausscharge`), so the mass infimum is a finite computation
  per root set (`cor:gaussfinite`), certified at four sets with `a != 0`
  (`prop:gaussinst`); no multisection or ray reduces them
  (`prop:gaussnotransfer`).  `q`-adic Newton polygons give an
  unconditional mass bound (`thm:padicmass`) that pays `sum j log rho_j`,
  within a factor 4, on circles of prime-power norm (`cor:padiccircle`);
  carry sizes alone cap at linear mass (`prop:carrylimit`), row 2 is a
  rounding-recurrence question (`lem:gaussround`), and rows need
  `0 < |a_j| < c_j` (`prop:gaussrowsfail`).  An Archimedean Newton
  polygon (`thm:archnewton`) gives rows and mass `sum j log(rho_j/3)` for
  every complex multiple once moduli grow by a factor 9 (`cor:separated`),
  so one prime with distinct exponents is CLOSED (`cor:oneprime`), and
  at most `g` moduli per annulus `[R, 9R]` costs a factor `g**2`.  Open:
  rows `k >= 2` or an `Omega(K**2 log)` mass for many pairs in one annulus,
  as Polynomial's register roots `a +- p**b i` over many primes (coprime
  norms), uniformly in `K`.

- **Polynomial's routing constant.**  CLOSED in
  [polynomial](proofs/polynomial.tex): the next-read count `thm:count`
  gives `N*(k) <= min(K_in, L)`, sharp (`prop:sharp`), so routing adds no
  factor; and one input root can serve first-essential residuals at
  `n - Theta(log n)` levels (`rem:levels`), so summing levels is not
  available to the lower bound.

- **Every row at other roots.**  For `r >= 2` the per-row bound is
  generalized ([coefficient-mass](proofs/coefficient-mass.tex)
  `thm:everyrowr`: `b_k >= max((r-1)**n, n r (r-1)**n/((r-1)**n + 1))`,
  `n = L-k+1`, and the one-hole bound `B_r(n)` for `r >= 5/2`); the last two
  rows are exact (`cor:tworowsr`), the last row for every `r > 1`
  (`cor:lastrowr`), and `thm:tailgen`/`cor:ordergen` extend `thm:tail` and
  `eq:order` to all roots above 1.  For `1 < r < 2` the rows are pinned up
  to a factor `1 + O(k**(n-1/2) theta**k)` (`thm:prefixrows`,
  `cor:belowtwo`); at several roots the one-hole tail has a closed form
  (`prop:oneholegen`) giving `thm:rowsgen`, which beats `eq:order`; the top
  row at any roots is bracketed by `prop:toprowgen`; and rows equal the top
  row exactly in explicit ranges (`thm:rowstop`, `cor:rowstopranges`).
  The hole shift at several roots is CLOSED for roots `>= 5/2`
  (`lem:holeshiftgen`, `thm:rowsgenfull`); insertion holds at holes with
  `prod_(c >= h) (1 + 1/c) <= r - 1` (`lem:insertpi`), so rows equal the
  top row whenever a top-row optimum has hole product `<= r - 1`
  (`thm:rowspi`, exact top rows by `prop:toprowcert`), proved for every
  `n <= 10` at `r >= 3` and at points up to `n = 24` (`cor:rowspiranges`).
  Open: the conjecture `V_r(L,k) = min_i 1/nu_i(n)` in general (the
  insertion inequality beyond hole product `r - 1`, `2 <= r < 5/2`, and
  `1 < r < 2` with `n >> k`).

- **Brainfuck behaviour count.**  Recorded in commit `9f81099` when the
  Factor constant work was cut: a drawing (word over `><+-`) of `C`
  characters reaches at most `(1 + sqrt 2)**(C + o(C))` tapes, attained by a
  Delannoy-ranked code, while words free of the five cancelling adjacencies
  number `(1 + lambda)**C`, `lambda = 6.388`.  Pin the exponential growth
  rate of distinct behaviours (input-output functions on bounded inputs) of
  `C`-character programs: enumeration to `C = 10` has I/O-only and
  full-prefix ratios still climbing (4.09, 4.52), so fitted bases are lower
  estimates, and forbidden-pattern lists stop near 7.37.  A global
  equivalence argument is needed.

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

- **Intermediate rows of `b_k`.**  CLOSED: every monic multiple of
  `(x-2)**L` has `b_k >= L - k + 1` for every row and degree
  (`thm:everyrow` in [coefficient-mass](proofs/coefficient-mass.tex)).  The
  certificate `r_Z(D - x d/dx)` (`lem:rowcert`) reduces row `k` to a
  `D`-free statement `T(n)`; `prop:rowsfree` proves it when `{1,2,3}` is
  not exempt, and `prop:rowstop` otherwise, bounding the values at the
  kept holes by the consecutive block (`lem:holevals`) and the tail by a
  Beta integral (`lem:holetail`): `(k+1) Phi <= 1/2 + 4/(3e) < 1`.

- **Polynomial's constant.**  `prop:bracket` in
  [polynomial](proofs/polynomial.tex) brackets `C_P n / T**2` explicitly:
  liminf in `[2 log10(2), 525/8 log10(2)]`, limsup in
  `[2 log10(2), 5821/32 log10(2)]`, a factor 32.8 / 91.0 (down from 211).
  Lower side: counting with the relabelling symmetry (`lem:gapauto`,
  `prop:counting`) forces `T/(n+4)` input values for every `n >= 7`.
  Upper side: automaton programs with a shared threshold decoder
  (`lem:decoder`, `prop:dfaprog`, profile `525/8` per state squared,
  `lem:profile`) and a stripped automaton with `3/2 T/n` states near
  `nu = 1` (`lem:strip`).  Open: levels (the worst-case minimum automaton
  near `nu = 1`, in `[1, 3/2] T/n`) and profile (`525/16` against mass `2`;
  the register and real roots the lower bound does not charge, see the
  complex-roots row).
