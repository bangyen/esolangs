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

  A row closes when its generator is O(T) on every audit axis below, when
  it carries a proved language-wide lower bound, or when tests pin a
  semantic obstruction that every attempted construction breaks. A
  syntax-level lookup table does not count as a generator. If one more
  executed round produces neither a construction nor a bound, the row
  moves to [Parked](#parked): one line there, its known state in the
  language's proof page. The language stays, and its status-table cells
  keep their vocabulary; [curation](limitations.md#curation) alone admits
  and removes languages.
  An unproved wall is not a lookup table.

  The three axes are totality (does the generator handle every table it
  claims?), generation time, and output size; execution time and workspace
  are `proofs/index.md`'s Execution and Workspace columns.
  `proofs/index.md` defines totality; `tests/proofs/deep/linearity.py`
  measures output size by same-parity successive differences through
  n=12. Timings use the top five arities, best of three, and exclude
  loading; runs under 10 ms do not establish an exponent. An axis closes
  only with a language-wide lower bound; `Measured` keeps the empirical
  regression gate without asserting a proof. To update the table, edit
  `src/esolangs/proof_status.json` and run `python scripts/generate.py docs`. Current
  status:

  <!-- SCALING-STATUS:START -->

  | Language | Totality | Generation time | Output size |
  | --- | --- | --- | --- |
  | Befunge | Exception | Linear | Linear |
  | Factor | Total | Language lower bound | Language lower bound |
  | Malbolge | Exception | Open | Linear |
  | Polynomial | Cap | Language lower bound | Language lower bound |
  | Vandevelo | Total | Open | Measured |

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

- **[Transistor](https://esolangs.org/wiki/Transistor)** (2 backlinks).
  Tri-state values (true, false, floating), N/P transistors and pull
  resistors as the only primitives, plus `circuit`, `let` and `while`.
  Generator: a mux fold with inputs as `let` lines, O(T). Gaps: no grammar,
  no I/O (output would be a chosen variable), computational class unstated.

## Open problems

Each item names its next executable step. When an item is answered, record
the answer in the linked proof and remove the item. An item that stalls
for a round moves to [Parked](#parked).

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
  pair-decoded router realizes every table on up to 13 rows at `k=6`. On
  pair rows it caps at `9.33*(k-1)` rows by region counting and reaches
  `13*floor(k/6)` by disjoint blocks, so text stays `Theta(T log T)`; rows
  of at most `s` features cap at `O(k log s)`
  ([pair router](proofs/fractran.md#pair-decoded-two-priority-consultations)).
  Next: exhibit a `Theta(k log k)`-row family with rows of `k**Omega(1)`
  features that a fixed pair decoder shatters, or bound such rows without
  counting. (The indexed threshold route already achieves linear text by
  magnitudes.)

Controls are in `tests/proofs/test_research_tracks.py`. The linked proofs
close ordered input-forgetting construction, generated-family loading
bounds, and the weighted-description theorem.

## Parked

Stalled problems, one line each; detail lives in the linked proof page. A
line changes only when its next step does.

- **Brainfuck behaviour count.** Next: count balanced bodies by the
  context-free system or a depth-indexed transfer matrix
  ([brainfuck-count](proofs/brainfuck-count.md#8-what-is-not-settled)).
- **Brainfuck on bounded inputs.** Next: establish Theorem 6's limit or
  sharpen either side ([brainfuck-count](proofs/brainfuck-count.md#8-what-is-not-settled)).
- **Polynomial's constant.** Next: replace the instruction profile or raise
  the coefficient-mass bound ([polynomial](proofs/polynomial.md#explicit-constants)).
- **Factor leading constant.** Next: a sound local rewrite lowering the
  lower side's Perron root, or a cheaper weighted command stream
  ([factor](proofs/factor.md#open-problems)).
- **Malbolge's first unreachable arity.** Next: shrink the decoder or share
  more of its common initialization
  ([malbolge-scaling](proofs/malbolge-scaling.md#open-problems)).
- **Vandevelo structural scaling.** Next: settle Cohen and Shinkar's
  `O(log n)` DNF-of-parities gap, which bounds output and so generation
  time; on the build side, a `certify` that rebuilds a level only when its
  direction drops below half the average
  ([index](proofs/index.md#vandevelo-identifier-and-fallback-audit)).
