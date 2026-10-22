# Roadmap

This page lists work that is still open. Finished work lives in the git
history; standing rules and proved limits are in [limitations](limitations.md).

## Generator linearity

For truth-table length `T`, target O(T) generation time and emitted size.
Generation includes input ordering and writing the program. Close a gap with
an executed, loop-less construction or a language-wide lower bound; measured
scaling alone does not prove linearity. Preserve totality, execution, and
workspace contracts.

The [scaling status](proofs/index.md#scaling-status) records current verdicts.
Edit the `[proof_status]` section of the language's own `language.toml` and run
`just docs` to update it. Proved limits remain
evidence, not optimization tasks.

- Polynomial has a documented language lower bound.
- Unary has a documented language lower bound.
- Befunge has a finite-source totality exception.

- **Malbolge:** generation at seventeen inputs is open (2026-10-21): a
  table cell cannot carry eight address-independent meanings (window
  conflict graph: independence number 8, twelve classes), lockstep
  adjacent-cell reads reach 110 of 512 triples a phase, and the
  seven-meaning build's 1,994 gotos have 2.77 cells each in the
  complement against a 3.6-cell routing floor
  ([limitations](limitations.md)). Reopen only with a layout that needs a
  quarter fewer gotos at that floor, or a decoder whose per-cell meaning
  is not a function of the window cell.
- **Open worst-case bounds** (2026-10-22): these cells have a route to
  `worst`. The 55 `at most` cells without one are in
  [limitations](limitations.md#run-time-and-memory).
  - Partial range: SMU scaling past n = 15 (the lower macros take
    two-letter names from n = 16), 1 + i workspace past n = 23,
    INTERCAL execution and workspace past n = 12 (level n - 3's 240 pairs
    cap the named nodes) and scaling outside n = 3..10, Inject scaling
    past n = 49 (two-letter input names).
  - Proved, not reached: Back, Bitdeque and Boolfuck scaling.
  - Algebraic Programming Language execution: `max(21, ⌈65n/2⌉ + 3n - 27)`
    is exact through n = 4 (exhaustive); parity reaches it to n = 10 and
    searches to n = 8 never beat it, unproved past n = 4.
- **Unformulated scaling** (2026-10-22): 20 cells state a mechanism, no
  size formula. Bleh, Quassaunt and Stisp have a bound only as a per-level
  optimisation (not a rule); CVNC's unshared 8T + 12 is beaten by sharing
  on 12,926 of 65,536 four-input tables. Brainfuck, Dig, For Thorn,
  Interprogck8, Minifuck, Pointless, ROTfuck, Smallfuck, Subleq, Thisthat,
  3x and AddSubJump (n <= 5) race routes or layouts; Line, Piet and Circuit
  Diagram need a raster unit; Polynomial is a lower bound. Slow ACV's three
  cells are prose too: candidate bounds hold to n = 20 but are unproved.
- **Unmeasured classes:** Befunge, Malbolge and Polynomial execution carry
  formulas; Unary execution and workspace do not (`max(n, min(n + 4, 8))`
  commands is exact on the nine-command budget, unapplied).
- **Argued, not derived** (2026-10-22): six `worst` cells rest on an
  argument past the executed range. Clockwise scaling (an essential-input
  subset sweep to n = 9), Codesick and Forbin scaling ("fewer nodes never
  win" and the shrink argument, past n = 8), Circuit Diagram execution
  (parity as the fold past n = 16, from size growth), INTERCAL scaling
  n = 5..10 (an integer program over level shapes, every level non-empty)
  and Suffolk scaling past n = 8 (the one-pair family enumerated at n = 7, 8,
  sampled at 9, 10). Derive each, or scope it to the executed range.
- **Derived, not executed:** Forþ workspace's log factor needs a twin call
  50,625 or more scopes back, at least 20 inputs
  ([limitations](limitations.md#run-time-and-memory)); What!? past n = 19
  (execution past 17) and S*bleq scaling past n = 21 were not built.
- **Loose bounds:** FALSE workspace (15x) and Object Disoriented workspace
  (4x) sum component peaks no row reaches together. A per-row profile
  tightens them without a route to `worst`.
- **Open mathematics:** Polynomial's worst-case length constant
  `C_P(n)*n/T**2` is bracketed only within a factor 12.5, and whether the
  limit exists is open ([proofs](proofs/index.md#polynomial-bound)). Whether
  some 17-input Malbolge table has no program is open; the Malbolge row
  above is the constructive side ([proofs](proofs/index.md#malbolge-bound)).

Keep the registry-wide scaling regressions in `tests/proofs/deep/linearity.py`.
An unresolved bound stays open; it does not authorize removing its regression
check or weakening a contract.

## Language candidates

Unimplemented wiki pages shortlisted for the first-implementation route
(2026-10-22): their specs read whole once the standing conventions (EOF,
empty-stack pops, output framing, cell width) fill the gaps. None is
admitted yet. Each needs a prototype audit first: an interpreter matching
every example on its page, a linear generator executed over every table at
small n, and a re-spelling comparison with the nearest collected generators
([curation](limitations.md#curation)). BASICER, CARP and IEBEL jump by
line number, so a plain tree costs T log T; they need equal subtrees shared.

- **Ready for the audit:** Pilas (two lockstep stack lines; `{...}` runs
  while the top is zero), Aprknia (one stack; `*` pushes five results),
  lol waht i cant edit talk pages (while-equal blocks over variables),
  IEBEL (equality-branch OISC; its truth machine forces `b` as a register
  for the controls and a literal for the load) and BASICER (`GOTO` menus
  read the input and branch in one step).
- **Re-spelling risk:** CARP's decrement-and-branch tree is Decleq's
  without the input normalization, and CreativeScript v2's arithmetic
  (integer division, forced by its own `==` program) invites Blindfolded
  Arithmetic's shifted literal or APL's `x`/`!x` selection. Each needs a
  construction neither collected generator uses.
- **No linear construction yet:** NOR machine (reaching an operand rotates
  the queue), Balik (a 2D tree in O(T) area) and Tiangou (markers set as
  they run, so jumps go backward only).

## Engineering

Dead-code leads, unmeasured against the
[10% size bar](CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping).
A removal must leave the generated corpus byte-identical (tiled, constant and
ignored-input tables included).

- **Plain-rewrite audits are one-off:** Streetcode and LaserFuck were each
  audited once -- write the plain canonical construction, price every
  bespoke trick against it, and remove the ones whose saving is a fixed
  amount rather than a genuine percentage (see
  [CONTRIBUTING](CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping)):
  Streetcode's lift and tail overlap, LaserFuck's sized leaf retirement and
  Dig's default banded tree came out this way, and four of SStack's six
  sharing routes (2026-10-21), and 6-5's copy node and Minifuck's dead lookup
  threshold (2026-10-22). Flowchart, Circlefuck and Circuit Diagram kept
  every trick and Ascenic has none. Line, Alight, Polynomial, Slow ACV
  Mammalian, APL, INTERCAL and Packlang are inventoried (2026-10-22): their
  unrecorded mechanisms are width/balance layout or core-construction
  constants, not default-path tricks. The audit is repeatable per generator.
- **The S*bleq variants are interpreter-only, and stay so unless they
  are ever registered:** the interpreter runs the store targets `a`
  (base), `ab` (S*bl*q) and `b` (Subl*q), each also in an indirect
  form, but the generator emits base S*bleq only and no public path
  selects a variant (no registry entry, no dialect setting -- they are
  distinct languages, not readings of one spec). Not scheduled work:
  if the variants are ever registered, generalizing the hoisted tree
  and the packed decoder across the other two store targets belongs to
  that project, execution-gated per variant and re-audited afterwards,
  against the plain-rewrite sweep's S*bleq prices as the baseline. The
  indirect forms would stay out of scope even then: their operands are
  dereferenced, so a generated program can embed no literal address and
  every operand would need a materialized pointer cell -- a different
  construction, not a parameter of this one.
- **FRACTRAN's one-literal guards (retirement candidate #19) wait on the
  index:** writing each guard as one literal (`11*29` as `319`) leaves
  programs the interpreter's index refuses -- the literals are products of
  two of the program's primes and outgrow any linear cap on its bases
  (36,041 against a 4,337-character program at n=10), so runs scan the
  fraction list. It ships only with an index that factors guards over the
  program's own primes; its saving is 8.4% at n=10.
