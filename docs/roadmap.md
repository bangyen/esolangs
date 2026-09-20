# Roadmap

Only live work belongs here. Contracts and standing walls go to
[limitations](limitations.md); a closed row leaves, and its commit is the record.

## New interpreters

Implement the surveyed interpreter candidates in this order.  The first four
are the 2026-09-19 re-run of the `Category:Unimplemented` x
`Category:Two-dimensional languages` pass (116 pages, up from 111); the
verdicts are spec reads, not executed generators, so the size question is open
for every entry.  INTERCAL and Piet are outside that pass -- already
implemented, so never in the screen.

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
- **Piet** (2001): outside the pass for the same reason.  A non-textual
  colour-raster source whose command is the hue/lightness delta between the
  block left and the block entered; `pointer`/`switch` pop a value to rotate
  the direction pointer and toggle the codel chooser, so the branch is a
  data-selected direction -- a sixth mechanism against the five in
  [contributing](CONTRIBUTING.md), the same axis INTERCAL claims and dearer.
  The generator would be the grid walk the set has, so the language case
  rests on the branch alone.  The medium carries the integration case: image
  source is not a language axis, but two raster sources give the registry a
  reason to carry one -- `line` alone is a path no registry caller reaches,
  and registering Piet beside it gives a raster source kind two consumers,
  the downstream a shared shim needs to stay off the curation removal list.
  Pin before building: exact-palette matching (anti-aliasing moves a codel;
  non-standard colours are implementation-defined), the eight-attempt
  black/edge termination, the DP/CC initial state.  Spec read only; output
  size is open -- area, where every pushed constant is a block of that many
  codels.

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

  Every generator is audited on four axes.  Totality is the `proofs.md`
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
  | Polynomial | Cap | Language lower bound | Language lower bound | Linear |

  Polynomial has tight language-level text complexity
  `Theta(T**2 / log T)`.  Equal real
  roots form contiguous blocks; their noncrossing opener/closer incidence
  graph is outerplanar, giving `m_routing < 3L_real` and therefore
  `L_real = Omega(T/log T)`.  The distinct-root slack certificate then gives
  the lower bound for every cofactor and operand sign.  The uncapped
  residual-DAG construction has `O(T/log T)` instructions and expands to the
  matching upper bound.  The pre-expansion estimator bounds rendered and live
  decimal digits before the resource cap admits multiplication.  Its root
  bound `R = O(T**2/log T)` makes packed expansion `O(R log R) = O(T**2)` on
  libmpdec's large FNT path (`O(R**2) = O(T**4/log**2 T)` with schoolbook
  multiplication), against the `Omega(T**2/log T)` output cost.

  Root recovery now lifts through `D**2`, covering the generated
  `|a| < 50D` envelope, and swaps NTT field roles when an instruction prime
  equals the primary modulus.  Exact division remains acceptance.  Therefore
  every generated factor peels and cold parsing is polynomial; arbitrary
  programs outside the envelope retain the general factorization fallback.
  Conservative generation and cold-parse work/memory estimators cover the
  tested corpus and boundary controls, including pre-expansion refusal and a
  parse outside the former fixed lift.  See [polynomial](polynomial.md) and
  `tests/proofs/deep/multiplicity.py`.

  Generation time, growth per added input at the top arity: B-tapemark,
  6-5, Forth, Circuit Diagram past its n=8 route change, and Vandevelo
  (x2.0 dense over n=11..15, 0.31 s at n=12, a peel that keeps its
  working sets across cubes) read x2.0--2.2, between the size contract's
  x2.15 and what these arities separate from noise; they are held linear
  until a wider measurement says otherwise.

- **Boolean generator conventions.**  Five conventions govern the *embed*,
  the text that stands for one input -- not the program around it.  A
  template has one ordered run per input, constant width, no padded spaces,
  and a uniform `(zero, one)` pair.
  | Language | No spaces | Uniform |
  | --- | --- | --- |
  `tests/proofs/test_conventions.py` checks these on dense and parity tables
  at n=2..6. The table is empty; add a relaxed-width toggle only for a smaller
  executed build. A space toggle has no remaining use.
- **ArrowQueue reusable drain.** Ship it only if folding is testable at `n >= 5`.

- **Reorder ArrowQueue inputs.**  The three-input screen leaves 12.4%
  headroom, but its queued inputs cannot be renamed in place.  Find a
  re-enqueue and grid-routing construction, then compare emitted, executed
  programs against the current template; abandon it if the routing spends
  the apparent gain.

- **Raster source kind.**  Admit Piet only with `line` registered, so an image
  source has two consumers.  Registry half, small: a source kind beside
  `split` on `Language` (`_table.py:21`), surfaced without breaking the public
  `RUNNERS` shape (`registry/__init__.py:51`, read as ``(module, split)``) --
  a sibling `SOURCE_KIND` map or a `raster` frozenset.  `generate`
  (`__init__.py:143`) is typed `-> str` and wraps through `wrap_program`; a
  raster language reads rather than embeds, so it must return the generator's
  `Raster` untouched and skip the string path, widening the return type
  `_Template`/`_Tagged`, `check_program` and `run` (`__init__.py:375`) assume.
  `describe` gains the kind.  Language half, large: `line` is not an
  interpreter in this repo's sense -- `line/simulate.py` offers
  `compile_program`/`run_compiled`, with no `_Machine`, `step`, `halted`,
  `snapshot` or `ip_shape`, and its generator round-trips through a file
  (`render(...).save` -> `extract(path)`, `tests/line/test_line_boolean.py:40`).
  Every interpreter-sweeping suite (fuzz, VM protocol, input convention,
  stepping parity, examples) would then require its conformance, and both
  generators are area-cost, pulling `line` into `tests/proofs/deep/linearity.py`.
  Worth it for the source kind itself; it does not strengthen the Piet case.

- **Image-source candidates.**  A read of the 129 `Category:Non-textual` pages
  for raster sources only -- music (Fugue, Velato), music-note, and
  steganography pages excluded.  Verdicts are spec reads, not executed
  generators.  For the source kind above: Braincopter (2005) first, a PNG
  Brainfuck clone whose opcode is `(65536R + 256G + B) % 11` and whose
  generator is a palette render of the registered `brainfuck` generator
  (`tools/tape.py:63`) -- the cheapest second consumer; Brainloller (2005),
  its fixed-RGB-palette sibling, is the same interpreter landed first.
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
