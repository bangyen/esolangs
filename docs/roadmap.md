# Roadmap

This page lists work that is still open. Finished work lives in the git
history; standing rules and proved limits are in [limitations](limitations.md).

## Research follow-up

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
  `src/esolangs/proof_status.toml` and run `python scripts/generate.py docs`. Current
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

Controls are in `tests/proofs/test_research_tracks.py`. The linked proofs
close ordered input-forgetting construction, generated-family loading
bounds, and the weighted-description theorem.

## Engineering

Generator gaps against the canonical pieces in
[CONTRIBUTING](CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping).

- **Canonical-gap screen.** Run every generator on every path (default,
  width, balance, dialect) to n=8 against the three canonical pieces, with
  execution and a positive control; price it before launch. It should find
  the two gaps below and any others.
- **BFStack constant fold.** A constant n=4 table emits 67 characters where
  a constant leaf takes 59.
- **Dig width paths.** A repeated flat leaf is shared on the default and
  balance paths (tiled n=8 -22.7%), never under `width`. Either route its
  wires in the narrow layout or record why none fit.
- **Dig wire rule.** Routes to a shared leaf come from a per-build
  fewest-turns search. Replace the search with a fixed route if one keeps
  the saving.
- **Back bend routes stay out.** They add under one point on tiled n=8,
  and raise worst commands at n=6/7 from 122/221 to 154/306, past the
  execution ledger's bound.

## Parked

Stalled problems, one line each; detail lives in the linked proof page. A
line changes only when its next step does.

- **FRACTRAN bit-linear pipeline.** Next: execute a forward cleanup scan
  for direct chunks in place of minimum-tree updates; factor removal cannot
  enable an earlier failed guard. Prime generation and literal conversion
  remain, with the materialized sieve forcing `Theta(T log T)` generation
  ([fractran](proofs/fractran.md#direct-chunks-with-exact-cleanup)).
- **Brainfuck behaviour count.** Cancelling tested-cell updates with balance
  confined to `{-1,0,1}` are certified. Next: cover larger excursions or
  lower the exponential bound
  ([brainfuck-count](proofs/brainfuck-count.md#8-what-is-not-settled)).
- **Brainfuck on bounded inputs.** Next: establish Theorem 6's limit or
  sharpen either side ([brainfuck-count](proofs/brainfuck-count.md#8-what-is-not-settled)).
- **Polynomial's constant.** Next: replace the instruction profile or raise
  the coefficient-mass bound ([polynomial](proofs/polynomial.md#explicit-constants)).
- **Factor leading constant.** Clearing-loop normalization lowers the Perron
  root to `5.948789300`. Next: broaden the normal form or construct a cheaper
  weighted command stream
  ([factor](proofs/factor.md#open-problems)).
- **Malbolge's first unreachable arity.** Seventeen remains open. Native
  components pass separate controls, but the reduced LAST-only layout is
  8,432 cells short before the full query and relocation selector. Next:
  share initialization and query control, then relocate records before capture
  ([malbolge-scaling](proofs/malbolge-scaling.md#native-components-and-layout-gap-2026-10-09)).
- **Vandevelo structural scaling.** Next: settle Cohen and Shinkar's
  `O(log n)` DNF-of-parities gap, which bounds output and so generation
  time; on the build side, a `certify` that rebuilds a level only when its
  direction drops below half the average
  ([index](proofs/index.md#vandevelo-identifier-and-fallback-audit)).
