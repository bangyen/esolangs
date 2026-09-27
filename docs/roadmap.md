# Roadmap

Only live work belongs here. Contracts and standing walls go to
[limitations](limitations.md); a closed row leaves, and its commit is the record.

## New interpreters

Implement the surveyed interpreter candidates in this order.  The first four
are the 2026-09-19 re-run of the `Category:Unimplemented` x
`Category:Two-dimensional languages` pass (116 pages, up from 111); the
verdicts are spec reads, not executed generators, so the size question is open
for every entry.  Piet is already implemented, so it was never in the screen;
INTERCAL, listed after them, is outside the pass.  Among the classics the
build order is Cyclic tag, INTERCAL, Emmental, Prelude, and each row carries
why.

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
- **INTERCAL**: not from the 2D pass, and not a completeness add -- the
  well-known candidates otherwise re-occupy an axis the set already has, and
  the collection is curated by admission, not coverage.  INTERCAL is the
  exception, but not for the reason first filed.  `COME FROM` is an
  *unconditional* trap door -- manual 4.4.14, fired "immediately after
  statement (label)", an error for two of them to name one label -- and
  `ABSTAIN` takes a literal label or a gerund list, so there is no computed
  label anywhere in the Revised Reference Manual and `COME FROM` cannot branch
  on data at all.  What branches is `DO (label) NEXT` with
  `RESUME <expression>`: a computed *return depth* over the NEXT stack, which
  the manual's own cat program uses to select 1 or 2 frames with
  `PLEASE RESUME '?.1$#256'~'#256$#256'`.  That is the new mechanism against
  push/conditional/jump/pointer here, and it is the claim to carry, not
  "pull-based transfer".  Target C-INTERCAL, not INTERCAL-72: `COME FROM` is a
  C-INTERCAL addition, so the 1972 language does not carry the feature the
  admission rests on.

  Settled, and no longer blocking: the I/O.  There is no plain byte I/O --
  `WRITE IN` reads English digit words one per line (`ZERO`/`ONE`, also `OH`
  and `NINER`), `READ OUT` prints extended Roman numerals with zero an
  overline over no character -- but `_answers.py` already carries
  per-language stdin overrides of exactly that shape (Grapheme spells
  `%`/`A`, Fargo takes one number).  The Turing Text array model (manual 5.2)
  gives literal `0`/`1` instead, at the cost of differencing every input
  against the previous character and bit-reversing every output byte; take
  `WRITE IN`/`READ OUT`.

  Open: the size.  A depth-`n` NEXT/RESUME tree is O(T) statements at O(1)
  text each, and E123 caps NEXTing at 80 levels -- depth, not rows, so a tree
  clears it and any per-row frame build does not.  One generator constraint
  nothing else here has: 1/5 to 1/3 of statements must carry `PLEASE`, or
  E079/E099 fires.

- **Cyclic tag system** (2004): Matthew Cook's tag variant, the one that
  carried the Rule 110 proof.  A production list `P_0 .. P_{n-1}` over a
  binary word, stepping `(i, dX) -> (i+1 mod n, X P_i^d)`: the only decision
  in the language is the word's leading symbol, control is the cyclic index,
  and nothing addresses anything.  Every branch here is
  conditional/jump/pointer/first-match/promise-forced, so a cyclic schedule
  forces a new one, and the inputs embed as symbols of the initial word --
  a one-character embed, which is the convention's easiest case.  **Build this
  one first**; nothing is left to decide.  The answer is the last symbol
  deleted.  Halting needs the final consumed symbol to append nothing:
  automatic for `d = 0`, and for `d = 1` exactly when `P_i` is empty, which is
  legal and which Cook's tag-to-cyclic reduction already appends `|Sigma|` of.
  Both values are reachable as the last deletion, so the halt carries a bit
  where FRACTRAN's carries a value.

  Two mechanics for the generator.  Consumption is FIFO, so the symbol at
  position `k` meets `P_(k mod n)`, and every production length `0 mod n`
  makes the schedule data-independent; a length that is not shifts the phase
  of everything after it, and phase in `Z_n` is the only state the language
  has.  A width-1 embed is monotone -- it can only append -- so negation wants
  the width-2 dual rail `'01'`/`'10'`, equally legal under the five
  conventions.  Source shape follows FRACTRAN: productions, then an initial
  data string.

  Open: the size.  A block-aligned width-`w` build pays about `w` per
  production across `w` productions, so it needs a construction holding width
  O(1), or a bound.
- **Emmental** (2007): Chris Pressey's self-modifying language -- a stack, a
  queue, and `!`, which pops a symbol and a `;`-terminated program and
  redefines that symbol to mean that program.  The dispatch table is data,
  which nothing here has: Malbolge rewrites its source, not the meaning of an
  instruction.  That also points at a construction shape the ledger has no
  row for, a jump table the program defines for itself rather than a tree it
  walks: one symbol per table block, reached by `?`.

  Settled: binding is definition-time.  `createOp interpreter (head:tail) =
  composeOps (fetch interpreter head) (createOp interpreter tail)` (reference
  interpreter, `src/Language/Emmental.hs:82`) resolves every body symbol
  against the interpreter in force when `!` runs, so a later redefinition
  never reaches an existing definition, forward references do not work, and
  self-reference is not recursion -- the wiki's massive-redefinition example
  expands to a finite 251 copies, `5 * 50 + 1`.  Blocks still compose, through
  `?`: `opEval` calls `createOp` with the interpreter passed at *call* time,
  so `#NN?` resolves `NN` at run time, about five characters an edge, all at
  top level.  That indirection *is* the construction, because nesting is the
  cost -- a body's characters are pushed as `#NN` literals, so a definition
  runs about 4x its body and depth `d` about `4^d` (`'0` 3, `''0` 9, `'''0`
  27).  `~` is not the index primitive: `?` executes a popped symbol, so any
  byte-valued expression is already a 256-way computed dispatch (`,:.:?`),
  while `~` only folds 256 values into 9 classes -- a range test.

  Open, and Malbolge-shaped: symbols are bytes, so one dispatch level covers
  8 inputs and only 256 definitions are live at once.  Past 8 inputs a cascade
  must hold each stage's table either nested (`4^stages`) or inside the
  256-symbol table; price the row the way Malbolge's arity ceiling is priced,
  not as an ordinary tree.
- **Prelude** (2005): Nikita Ayzikovsky's language of *voices*, one per line,
  each with its own stack of zeroes, where instructions in the same column
  run simultaneously and every stack updates atomically.  Concurrency is an
  axis the set has nowhere, and it points at a width-wise construction
  instead of a depth-wise tree -- a voice a level, `^`/`v` reading the
  neighbouring voice's top.  **Last, and this row's plan is refuted, not
  open**: loop-less is impossible.  The instruction set is
  `+ - # ( ) ^ v ? ! 0-9` and everything else a nop, so with the brackets
  unused every value on every stack is an integer *affine* combination of the
  inputs and constants -- digits push constants, `^`/`v` copy a neighbour's
  top, `+`/`-` combine, and nothing multiplies.  `AND(x, y) = x y` is not
  affine, so no bracket-free program computes a general table.

  What survives: `(`...`)` as an execute-at-most-once guard is a conditional,
  not a loop, so a tree is still loop-less here.  It costs a column a guard --
  "It is illegal to have simultaneously more than one bracket", enforced at
  parse, where `prelude.py` aborts on `curr.count('(') + curr.count(')') > 1`
  -- so a `2^n`-leaf tree spans Theta(T) columns times the voice count: O(T)
  only at O(1) voices, which is also where the concurrency claim is weakest,
  and Theta(T n) for a voice a level.  Admission therefore rests on
  construction shape alone, since skip guard and print 0/1 are both occupied:
  a build that does not use simultaneity takes FALSE's verdict.

  Two spec decisions for the docstring.  `)` tests the top of the *opening*
  bracket's voice, and reads the previous column's snapshot
  (`topValues[openingVoice]`), where `(` tests its own live top.  The boundary
  read is a genuine gap: the author's Python wraps
  (`topValues[(voice-1) % numVoices]`), graue's C pushes 0, the draft spec is
  silent, and the wiki's wrap claim is `[citation needed]` -- free choice, and
  moot if the construction never reads across the boundary.

- **Classic-language admission.**  All four of Thue, FRACTRAN, Unlambda and
  FALSE now ship as interpreters with generators, in the classics tier.  What
  is left is the curator's call on promoting three of them out of it: Thue
  rewrites the table in place rather than walking a tree, FRACTRAN answers
  with the value it stops on and branches by which fraction divides first, and
  Unlambda has no conditional and branches by forcing one of two promises.
  FALSE is an ordinary stack language in costume and stays where it is.  Each
  promotion needs a comparison against the construction-shape, branch and
  answer axes the set already occupies, not just the observation above.

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

- **Coefficient mass.**  The open questions of the four coefficient-mass
  papers -- sharpness past the partial-sum criterion, complex roots, and every
  row below the root 2 -- moved with the papers to
  [bangyen/coefficient-mass](https://github.com/bangyen/coefficient-mass/blob/main/ROADMAP.md).

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
