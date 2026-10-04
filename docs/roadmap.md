# Roadmap

Open work only. See [limitations](limitations.md) for standing contracts
and proved limits; completed work is recorded in its commit.

## Research follow-up

- **Piet++ specification and generator audit.** The language is tagged
  [Unimplemented](https://esolangs.org/wiki/Piet%2B%2B). Nested-stack cofactor
  descent adds a data-tree selection mechanism: a strict raster subset ran
  309 generated tables across 3,352 rows, including every table through three
  inputs. Pin Read/Write operands, invalid typed operations, and image/block
  updates before implementing the full language. Verify that no implementation
  exists, derive the loop-less O(T) generator, and execute it through three
  inputs and sampled larger tables under the input conventions. The subset
  probe establishes feasibility, not full-language correctness or admission.

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
  establish an exponent. Closure requires a language-wide lower bound.
  Edit `proofs/status.json` and run `python scripts/generate.py docs` to update
  both status tables. Current status:

  <!-- SCALING-STATUS:START -->

  | Language | Totality | Generation time | Output size | Execution time |
  | --- | --- | --- | --- | --- |
  | Befunge | Exception | Linear | Linear | Linear |
  | Factor | Total | Language lower bound | Language lower bound | Linear |
  | Malbolge | Exception | Open | Linear | Linear |
  | Polynomial | Cap | Language lower bound | Language lower bound | Linear |

  <!-- SCALING-STATUS:END -->

  Befunge ships through thirteen inputs using a six-bit printable-ASCII lookup.
  Its fixed 80x25 source grid admits fewer than `2**42000` programs even with
  Unicode cells, whereas sixteen inputs
  admit `2**65536` truth tables. Some have no program under the source-embedded
  contract; unbounded runtime integers do not enlarge the source alphabet.

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

- **Brainfuck behaviour count.** In the repo model (clipped tape, EOF error),
  `4.2420 <= liminf B(C)**(1/C) <= limsup <= 7.0347`; the limit and a sub-7
  upper bound remain open. The 11,673-state certificate restricts balanced
  bodies to bracket depth one. Next: count unrestricted sound print rotation
  and forced-divergence bodies. Preserve the cell-preservation condition:
  `+[-[]].` halts and prints NUL, while `+[].` diverges. See
  [brainfuck-count](proofs/brainfuck-count.md#3-upper-bound-theorem-1) for the
  certificates, withdrawn bounds and loop-free comparison.

- **Malbolge's first unreachable arity.** The shipped cap is 16; counting
  excludes some 18-input tables, while 17 remains undecided. A build needs
  more than two table bits per cell across almost the whole store. Packing
  uses 49,152 cells, and the five-state decoder executes all 2,744 one-group
  cases. Next: share setup between the address fold, row selector and decoder
  around an arbitrary table; placement alone does not fit them. See
  [the construction record](proofs/malbolge-scaling.md#seventeen-navigation-is-linear-in-address-so-packing-helps-measured).
  An impossibility proof instead needs a density lemma: reduce the count by
  `2**46076`, or bound a normal-form representative's dependence by 24,434
  cells. A per-program dependence cut is false: `'o'*59046 + '/<v'` computes
  identity and depends on all 59,049 cells. Length and alphabet cuts are also
  closed; [limitations](limitations.md#boolean-generators) records the controls.

- **Polynomial's constant.** `prop:bracket` in
  [polynomial](proofs/polynomial.tex) bounds both limits of `C_P n / T**2`
  in `[13/4 log10(2), 325/8 log10(2)]`, a factor 12.5. Next: replace the
  instruction profile or raise the coefficient-mass bound. Inline-state
  tuning, narrower decoder operands, local opcode substitution and affine
  dispatch cannot improve `325/8`; their proofs are in the paper.
  The lower-bound gap is a quadratic mass charge for Gaussian instruction
  roots. The forced factor currently gives only `8 log(K!) = Theta(T)`;
  residual width alone does not force distinct Gaussian roots. Parity sources
  are universal and must be priced; the argument assumes exact register
  arithmetic, with float `**` a caveat. See
  [explicit constants](proofs/polynomial.md#explicit-constants) and the
  [coefficient-mass roadmap](https://github.com/bangyen/coefficient-mass/blob/main/ROADMAP.md).
  The [common-norm bound](proofs/polynomial-common-norm.md) is
  `Lambda(Q) >= K**2 log(R)/16` for the raw forced factor and scaled
  reciprocal or anti-reciprocal integer multiples. Arbitrary multipliers
  remain open, and register roots need
  not share a norm, so this does not close the constant bracket.

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

Controls are in `tests/proofs/test_research_tracks.py`. The linked proofs
close ordered input-forgetting construction, generated-family loading bounds,
and the weighted-description theorem.
