# Roadmap

This page lists work that is still open. Finished work lives in the git
history; standing rules and proved limits are in [limitations](limitations.md).

## Research follow-up

- **Piet++: finish the specification and generator audit.** The wiki still
  tags Piet++ as [Unimplemented](https://esolangs.org/wiki/Piet%2B%2B), but a
  [partial executor](https://github.com/Esolang-NET/Piet/blob/14d1533cc46e27463b4baa6957137f5af6c83380/Processor/PietPlusPlusExecutor.cs)
  exists. In that executor, Read, Write and Roll-Context are no-ops, and Dup
  aliases nested stacks. A strict subset already runs: nested-stack cofactor
  descent adds a data-tree selection mechanism, and the subset executed 309
  tables across 3,352 rows, including every table through three inputs. That
  shows the approach is feasible; it does not yet prove full-language
  correctness or admission. The executor cannot arbitrate the open
  conventions: its Read/Write are no-ops and its arithmetic reads a stack
  operand as 0, so operand consumption, the coordinate origin and image
  updates are unobservable there. Next: fix those conventions from the wiki
  text alone, audit invalid typed operations and image/block updates, then
  run the loop-less O(T) generator through three inputs and sampled
  larger tables under the chosen input conventions.

- **Linear Boolean generators: make generation and output grow only with
  the table.** Here `T` is the truth-table length. The goal is build time
  and emitted size both O(T). For each generator still open, the path to
  done is either (a) add a loop-less O(T) construction with an executed
  scaling regression, or (b) record a structural proof that the language
  or its required encoding forces super-linear output, then move on.
  Generation time includes choosing an input order and writing the result.

  A language stays in the repo if its generator is O(T) on all four audit
  axes below, if its row carries a proved language-wide lower bound, or if
  tests pin a semantic obstruction that every attempted construction
  breaks. A syntax-level lookup table does not count as a generator. If one
  more executed round produces neither a construction nor a bound, that
  language and its row leave. An unproved wall is not a lookup table.

  The four axes are totality (does the generator handle every table it
  claims?), generation time, output size, and execution time.
  `proofs/index.md` defines totality; `tests/proofs/deep/linearity.py`
  measures output size by same-parity successive differences through
  n=12. Timings use the top five arities, best of three, and exclude
  loading; runs under 10 ms do not establish an exponent. An axis closes
  only with a language-wide lower bound; `Measured` keeps the empirical
  regression gate without asserting a proof. To update the table, edit
  `src/esolangs/proof_status.json` and run `python scripts/generate.py docs`. Current
  status:

  <!-- SCALING-STATUS:START -->

  | Language | Totality | Generation time | Output size | Execution time |
  | --- | --- | --- | --- | --- |
  | Befunge | Exception | Linear | Linear | Linear |
  | Factor | Total | Language lower bound | Language lower bound | Linear |
  | Malbolge | Exception | Open | Linear | Linear |
  | Polynomial | Cap | Language lower bound | Language lower bound | Linear |
  | Vandevelo | Total | Open | Measured | Measured |

  <!-- SCALING-STATUS:END -->

  Where the remaining rows stand:

  - **Befunge** ships through thirteen inputs using a six-bit
    printable-ASCII lookup. Its fixed 80x25 source grid admits fewer than
    `2**42000` programs even with Unicode cells, whereas sixteen inputs
    admit `2**65536` truth tables, so some tables have no program under the
    source-embedded contract. Unbounded runtime integers do not enlarge
    the source alphabet.
  - **Malbolge** ships through sixteen inputs. Finite source space
    excludes some 18-input tables, so generation time at seventeen inputs
    is the open axis. Its fixed 59,049-character source makes output
    `O(1)`, while set cells grow linearly; see
    [malbolge-scaling](proofs/malbolge-scaling.md#the-emitted-size-law).
  - **Factor** has worst-case encoding and language floor `Theta(T log T)`;
    [factor](proofs/factor.md) gives the totality and generation bounds.
  - **Polynomial** has language-level text complexity
    `Theta(T**2 / log T)` and super-linear generation time;
    [polynomial](proofs/polynomial.md) proves both bounds and the parser's
    totality.

  Measured growth, for calibration only: wider dense-table measurements
  give same-parity size-difference ratios 3.971 (B-tapemark), 4.004 (6-5),
  3.855 (Forth), and 4.211 (Vandevelo) over n=12,14,16. Circuit Diagram,
  after its n=8 route change, reads 4.135 over n=10,12,14 and 4.119 over
  n=11,13,15. Parity tables read no higher. All sit inside the measured
  4.4 contract; that is a measurement, not a proof of linearity.

## Candidate languages

Screened 2026-10-05 from 54 Category:Unimplemented pages. Each is a first
implementation (unique backlinks measured 2026-10-06); add with
`/new-language`, ranked.

- **[Smu](https://esolangs.org/wiki/Smu)** (4 backlinks). Zzo38's minimal
  Smurf: a string stack over `()=|+`, four commands, and a run that ends by
  outputting the top string and running the next one. Bit I/O per run.
  Generator: one node `(c0)(|)=(c1)(+)=()+(=)` stores both children under
  the input bit's names and runs the selected one on the next bit; a leaf
  is `()=` then its bit. O(T), hand-traced, not executed. Gaps: an unset
  variable's value (the cat example implies empty), `=` at EOF, and the
  byte-to-bit input convention. The cat program is the only stated output.
- **[SStack](https://esolangs.org/wiki/SStack)** (4 backlinks). Seven
  unsigned stacks `a`-`g`, empty reads 0, byte I/O, and a loop
  `[x\y/...]` while two tops are equal. Generator: nested one-shot ifs,
  O(T). Gaps: EOF, decrementing an empty stack. The page's brainfuck
  interpreter is untested, so it is not ground truth.
- **[Transistor](https://esolangs.org/wiki/Transistor)** (2 backlinks).
  Tri-state values (true, false, floating), N/P transistors and pull
  resistors as the only primitives, plus `circuit`, `let` and `while`.
  Generator: a mux fold with inputs as `let` lines, O(T). Gaps: no grammar,
  no I/O (output would be a chosen variable), computational class unstated.

## Open problems

Each item names its next executable step. When an item is answered, record
the answer in the linked proof and remove the item.

- **Brainfuck behaviour count.** In the repo model (clipped tape, EOF
  error), the growth constant is bracketed:
  `4.2420 <= liminf B(C)**(1/C) <= limsup <= 7.0347`. The limit itself, and
  any sub-7 upper bound, remain open. The 11,673-state certificate covers
  balanced bodies only to bracket depth one, and no finite monitor can
  count the unrestricted sound print-rotation and forced-divergence bodies:
  they match brackets across any depth. Next: count them with the
  context-free system `B0, B1, L0, L1, R, P` or a depth-indexed transfer
  matrix, preserving the cell-preservation condition (`+[-[]].` halts and
  prints NUL, while `+[].` diverges). Certificates, withdrawn bounds and
  the loop-free comparison: [brainfuck-count](proofs/brainfuck-count.md#3-upper-bound-theorem-1).

- **Malbolge's first unreachable arity.** The shipped cap is 16 inputs.
  Counting excludes some 18-input tables; 17 remains undecided, and a
  build needs more than two table bits per cell across almost the whole
  store. Packing uses 49,152 cells, and the five-state decoder executes
  all 2,744 one-group cases. Neither placement nor sharing setup
  between the address fold, row selector and decoder fits them: the
  shared union is 10,324 cells against a 9,897-cell complement, and the
  decoder's 1,173 conflicting overlaps are the binding term. Next: shrink
  the decoder or share more of its common initialization. See [the construction
  record](proofs/malbolge-scaling.md#seventeen-navigation-is-linear-in-address-so-packing-helps-measured).
  Proving impossibility instead needs a density lemma: cut the count by
  `2**46076`, or bound a normal-form representative's dependence by
  24,434 cells. A per-program dependence cut is false (`'o'*59046 + '/<v'`
  computes the one-input identity and depends on all 59,049 cells), and
  length and alphabet cuts are closed; [limitations](limitations.md#boolean-generators)
  records the controls.

- **Polynomial's constant.** `prop:bracket` in
  [polynomial](proofs/polynomial.tex) brackets both limits of
  `C_P n / T**2` in `[13/4 log10(2), 325/8 log10(2)]` — a factor of 12.5
  apart. Next: replace the instruction profile or raise the
  coefficient-mass bound. Four refinements provably cannot improve
  `325/8` (inline-state tuning, narrower decoder operands, local opcode
  substitution, affine dispatch); their proofs are in the paper. The
  lower-bound gap is a quadratic mass charge for Gaussian instruction
  roots: the forced factor currently gives only `8 log(K!) = Theta(T)`,
  and residual width alone does not force distinct Gaussian roots. Parity
  sources are universal and must be priced; the argument assumes exact
  register arithmetic, with float `**` a caveat. See [explicit
  constants](proofs/polynomial.md#explicit-constants) and the
  [coefficient-mass roadmap](https://github.com/bangyen/coefficient-mass/blob/main/ROADMAP.md).
  The [common-norm bound](proofs/polynomial-common-norm.md) is
  `Lambda(Q) >= K**2 log(R)/16` for the raw forced factor and scaled
  reciprocal or anti-reciprocal integer multiples. Arbitrary multipliers
  remain open, and register roots need not share a norm, so this does not
  close the constant bracket.

- **Factor leading constant.** [factor](proofs/factor.md#leading-constants)
  brackets worst-case minimum digits divided by `T*n` between 0.11528442
  and 0.29229475 asymptotically (a 2.535423-fold gap). The lower side
  counts weighted exponent compositions after local normalization and
  first-output pruning; the upper side prices a traveling counter, fixed
  signed-ball blocks, and an almost-all prime-window covering bound. Parity
  encodings executed through five inputs determine neither limit.
  On the executed corpus, semantic deduplication only halves the count (a
  constant factor), and the tempting `<>` deletion is unsound at the
  clamped edge. Next: find a sound local rewrite that lowers the lower
  side's Perron root, or construct a cheaper weighted command stream to lower
  the upper one. Whether the limit exists, and its value, remain open.

- **Vandevelo structural scaling.** Register upkeep is bounded at O(T)
  lines and O(T log n) characters; the identifier references are the part
  that still carries the extra factor. The exact fallback now transforms
  the quotient by a node's `d`-dimensional span: `O(n*|S|)` projection
  plus `O((n-d)*2**(n-d))` transform work per call. A forced six-input
  control executes the three-dimensional transform and matches full-space
  counts; 280 generated programs retain identical source and all 2,536
  rows execute. Affine-coset complements use direct violation guards: the
  n=12 one-zero table drops 40,938,391 candidate visits and shrinks from
  333 to 277 characters. The occurrence-weighted naming audit shrinks a
  seeded n=12 source by only 1.01%, below the shipping threshold;
  `scripts/profile_vandevelo.py` records its executed controls. Next:
  remove the identifier factor, amortize projection and fallback calls,
  and bound the dual-basis core's aggregate work. The fallback is not
  amortized now: one seeded 15-input table spends `60*T` in it
  ([proofs](proofs/index.md)). Neither remaining gap is
  a language-wide lower bound; measured scaling does not settle them.

- **FRACTRAN order encoding.** One unchanged multiset of eight fractions
  computes all sixteen four-row tables just by ordering each `1/p, 2/p`
  pair; all 64 rows executed. The one-consultation route is closed
  negatively: fixed applicability and postprocessing give a linear
  threshold class, requiring at least `T-1` distinct fractions and
  `Omega(T log T)` text. A four-guard overlap cycle executes all 24
  orders on four rows and realizes exactly fourteen tables, missing XOR
  and XNOR. See [the order
  bound](proofs/fractran.md#order-only-decoding-with-one-priority-consultation).
  Two consultations escape the one-consultation cap: a `2k`-fraction
  pair-decoded router realizes every table on up to 13 rows at `k=6`, but
  its checked maxima grow linearly in `k`, so text stays `Theta(T log T)`
  ([pair router](proofs/fractran.md#pair-decoded-two-priority-consultations)).
  Next: exhibit a `Theta(k log k)`-row family a fixed pair decoder
  shatters, or prove the router caps at `O(k)` rows. (The indexed threshold route already achieves
  linear text by magnitudes.)

- **Brainfuck on bounded inputs.** The finite-set upper bound is now
  `6.584428341`, below the all-input upper bound `7.0347`: delete
  unvisited reads, then count seven-command segments by a certified
  adjacency matrix. [Theorem 6](proofs/brainfuck-count.md#7b-bounded-input-upper-bound-theorem-6)
  also covers varying input sets with total read budget `o(C)`, including
  byte-input lengths at most `(1-eps)*log_256(C)`. The lower bound remains
  `3.366148`. For input length proportional to source length, Theorem 6's
  counting improves on `7.0347` only while the proportion stays below
  about 0.021, and never on `6.584428341`. Next: establish
  the limit or sharpen either side.

Controls are in `tests/proofs/test_research_tracks.py`. The linked proofs
close ordered input-forgetting construction, generated-family loading
bounds, and the weighted-description theorem.
