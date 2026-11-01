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

- **Malbolge:** generation at seventeen inputs is open (2026-10-26).
  - *Why it is hard:* a table cell cannot carry eight
    address-independent meanings (window conflict graph: independence
    number 8, twelve classes); lockstep adjacent-cell reads reach 110 of
    512 triples a phase; the seven-meaning build's 1,994 gotos have 2.77
    cells each in the complement against a 3.6-cell annealed routing
    floor (certified at least 2.99).
  - *Ruled out:* hub substrates in the shipped and re-addressed
    geometries, marching and data-initialized decoders, threaded and
    streaming emission, membership dispatch, the permutation families;
    see [limitations](limitations.md) for eligibility, mechanism or
    measured rates.
  - *Reopen with:* a decoder variant whose word-mediated landing is
    realized in a full build that passes its gates (parity contract,
    per-row cases and a fresh census at the new window embedding, then
    placement and threaded rates inside the 9,897-cell complement), or
    new mathematics toward the 46,076 bits an impossibility proof needs
    beyond counting.
  - *Next lead (2026-10-27; tested 2026-10-31, refuted as stated):*
    the deposit half of the claim is true -- a lockstep fall-through
    sweep deposits a full word for exactly one source cell (a real
    296-cell program in the shipped interpreter, 94 of 94 deposits
    matching the stepper), against 21 cells measured for the shipped
    label phase.  The application half fails: the sweep placed 0 of
    the 74 shipped label cells in every configuration (best steered
    case 8-10), because a prescribed word at a prescribed cell is
    exactly what a sweep cannot do (still about 21 cells, as shipped).
    The stated residue count matches nothing measured -- `p` sweeps
    leave 36-41 of 94 residues uncovered, the `*` family 11, never
    29; steering completes coverage only through two windows or the
    k=5 family at 5 cells per word.  The five value bands are not
    there either: `p` deposits form two narrow bands, `*` deposits
    three rotation rails of width at most 31.  Nor does the lead move
    the paused reseed's economics: the deposits its first stage
    counts are few (12) and all prescribed, so the saving is at most
    about 240 cells against that stage's 1,113-cell kill line; any
    value is bulk seeding at the later stages' scale, through a
    redesign inside the paused loop.
- **Open mathematics:** Whether some 17-input Malbolge table has no program
  is open; the Malbolge row above is the constructive side
  ([proofs](proofs/index.md#malbolge-bound)).

Keep the registry-wide scaling regressions in `tests/proofs/deep/linearity.py`.
An unresolved bound stays open; it does not authorize removing its regression
check or weakening a contract.

## Engineering

Dead-code leads, unmeasured against the
[10% size bar](CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping).
A removal must leave the generated corpus byte-identical (tiled, constant and
ignored-input tables included).

- **Malbolge navigation, inexpressibility for an algebraic
  signature:** the closed-form question is closed under the
  bounded-read definition in [limitations](limitations.md#searches)
  — a lower bound excludes every rule factoring through cycle data
  plus bounded algebraic features (a reproducing formula needs at
  least 59 forced cell reads; no navigation with at most three
  jumps per `goto` fits at n=1, the cheapest ending at 6,607).
  The open remainder is signature-relative: no term of any size
  over the restricted algebraic signature (reads only at derived
  indices, per-trit algebra, no equality against arbitrary value
  constants, no random access) computes the optimal first step.
  The preservation route to it was attempted (2026-10-31) and is
  closed: the invariant relations are fully classified (values
  admit only the trivial two; positions admit a period-94
  family), no surviving relation separates, and the joint
  domain test is empty.  What remains is a proof by
  non-product or non-uniform relations, unpriced, or a term
  exhibiting the contrary.  See
  [limitations](limitations.md#searches).
- **Blind reimplementation of first implementations:** a clean-room
  interpreter written from the wiki page alone, diffed over the generated
  corpus.  With no outside interpreter, this is the only independent
  check a first implementation gets.  Found: one spec contradiction
  (Tiangou halted on underflow), five generators emitting forms the page
  does not license (Collatz Multiverse, Decleq, Minsky Swap, Modulous,
  SendStuff), the rest spec gaps now in the docstrings.  Record one as
  `[audits] blind_reimplementation = <date>`.
  - *Weakly grounded readings the generators rely on:* each record
    agrees only with the clean room patched to our reading.  Make the
    generator run under both, or find page evidence.
    - B-tapemark: FENCED (2026-10-31).  The page does not settle which
      grid's marker moves after a swap: re-read 2026-10-31, it says the
      symbol on the first grid is executed and then "the position
      marker" is moved, each grid has one, and neither example program
      swaps.  The page history was checked later the same day: all
      five revisions, back to the 2013 creation, leave the swap and
      marker wording unchanged, and no example in any revision
      swaps, so history does not settle it either.  Measured: under
      the other reading
      (the executing grid's marker moves), 147 of 218 corpus rows hang
      (step cap at least 50,000 against at most 759 shipped steps) and
      the 71 clean rows are exactly the swap-free executions --
      constant programs and each stage program's all-ones row, the only
      row whose every compare misses (witnesses n=1..4 all rows,
      parity/random n=5..6 sampled, narrow layout included; ours is
      correct on all 218).  The traced ``0110`` round trip (swap at X
      heading d0, back heading d1) fixes the algebra: the program
      marker's offset between readings is d0-d1 and the data marker's
      is +d1, so no single trip is invariant and a cancelling second
      trip per branch must satisfy sum(d1) = 0 with sum(d0-d1) = 0 --
      e.g. each trip beam-safe (d1 = d0) with opposite exit headings.
      Building it means a second copied gadget, entry and exit turning
      lanes and lane funnels on the match branch of every stage, in all
      three layouts: a stage redesign priced at about a stage-sized
      block per input, not a bounded patch.  A prototype (2026-10-31,
      wide layout, `0110` stage 0) built and measured the data half of
      the cancellation: a parallel walk on stage row 2 (weight-1 `|`
      cells -- the beam already executes the stage's own
      compare-column `|` heading E, the mismatch branch's +1 cell)
      plus one W `|` on row 3 cancels the +d1 offset exactly (the alt
      data marker reaches the descent column at the shipped post-walk
      position; shipped behaviour on all rows unchanged; +12 chars for
      the stage, 5 of them the lane's cells).  The program half is
      blocked in the shipped geometry: the lane crosses the descent
      column (a `%` there is a no-op under both readings), but the
      beam travelling W on stage row 3 meets that row's own `\` and is
      turned N into the copy row, and every other exit from the row-2
      corridor is blocked by a named shipped cell (the copy row, the
      run cells, the compare turn).  A working construction must
      relocate the run, the descent and the exit funnel together --
      the stage redesign above, whose price is the rejoin's, not the
      correction's.  The redesign was taken the same day: the wide
      stage is built (the cancelling lane plus an intercept dropping
      the alt beam to a travel row that re-enters the next stage down
      its own entry column, the exit `|` changed to `*`; witnesses
      n=1..4 all rows and n=5..6 samples clean under both readings)
      at about +30% size (221 to 281 chars at n=2, 2,489 to 3,311 at
      n=8), and is held unlanded on its prototype branch --
      invariance against an unevidenced reading does not pay a third
      more size on every wide program.  Folded is fenced: the fold
      links at local column 9 sever the lane's east passage (the alt
      beam turns N at the link; a parity control runs 31 of 32 rows
      alt-bad), and fold 0's run is unrideable with a deficit that
      cannot be paid.  Narrow is fenced: at weights 1..2 the only
      candidate intercept column is the shipped descent column
      itself, and with the lane hand-patched and accounted exactly
      the template `\` at local 7 turns the beam N.  Both readings
      were also implemented as a registered dialect with a
      dialect-parameterized generator (a 222-row corpus correct
      under each reading's own semantics, the alt dialect's programs
      no larger than the default's) and withdrawn the same day by
      decision: no consumer needs the second reading executable and
      the page gives it no grounding, so the dialect commitment is
      not owed; the verified implementation is kept unlanded on its
      local branch.  Reopen on new page evidence (a Talk page, an
      author statement, or a reference implementation), on a folded
      or narrow construction beating the obstructions named here, or
      on a real consumer for the other reading -- the dialect branch
      is the ready implementation if one appears.
    - Minifuck: REMOVED (2026-10-31) under the spec ground (see
      limitations.md, Removed languages).  Non-commands count as
      instructions `[` can skip, against "only 3 instructions"; the
      `[x` filler the emission model is built on relies on it, and
      under the clean-room reading the shipped generator diverges on
      258 of 258 corpus rows.  A rebuild grounded the general,
      two-state, parity, constant, unary and gap routes, but the
      stored route is structurally blocked (no command-only
      equivalents at lengths up to 12 and 15 on exact searches; its
      travel crosses row-dependent cells), so full grounding is
      unreachable and the language was removed rather than kept
      fenced.  The rebuild branch stays unlanded as the record.

<!-- BLIND-REIMPLEMENTATIONS:START -->

90 of the 90 first implementations: 1 + i, 3x, 6-5, A Painter Ant,
ABCDirection, AddSubJump, Algebraic Programming Language, Alight, Aprknia,
ArrowQueue, Ascenic, B-tapemark, Back, Balik, BASICER, Basicfuck, Between,
BFStack, Bitdeque, bit~, Bleh, Blindfolded Arithmetic, BrainIf, Caballo,
CARP, Circlefuck, Circuit Diagram, Clockwise, Codesick, Collatz Multiverse,
Container, CreativeScript v2, Crement, CV(N)(C), Decleq, Dig, Dimensional,
DINAC, EGL, Eval, Fackward, Fargo, Flowchart, Forbin, Forþ, Freestajlo,
Grapheme, Home Row, Hot, HQ9+ with headers, IEBEL, Inject, Interprogck8,
Kiss, LaserFuck, Line, lol waht i cant edit talk pages, Minsky Swap,
Modulous, Monotonic Boolfuck, Movesum, Nandypants, NOR machine, Object
disoriented, Packlang, Painfuck, Parenthesys, Pilas, Pointless, Qoibl,
Qrain, Quassaunt, RAM0, ROTfuck, Rubic, S*bleq, SendStuff, SLOW ACV
MAMMALIAN, Smu, Sonata, SStack, Stisp, Streetcode, Suffolk, Super SNUSP,
SwitchCase, Taglate, thisthat, Unsquare, What!?.

<!-- BLIND-REIMPLEMENTATIONS:END -->
- **Trick prototypes:** one agent a generator searches for one admissible
  size trick (CONTRIBUTING's bar, a rule, executed with a control) and
  ships it or records the near miss.  The zero-trick pilot shipped four of
  nine (Aprknia 53%, lol waht i cant edit talk pages 47.5%, Movesum 17.3%,
  Monotonic Boolfuck 13.2% at n=8); CARP's best, a jump register sized to
  the deepest path, reached 8.2%.  Next: the 7 one-trick generators, then
  the 18 two-trick ones.  Record one as `[audits] trick_prototype = <date>`.

<!-- TRICK-PROTOTYPES:START -->

100 of the 111 generators: ///, 1 + i, 6-5, A Painter Ant, ABCDirection,
AddSubJump, Algebraic Programming Language, Alight, Aprknia, ArrowQueue,
Ascenic, Back, Balik, BASICER, Basicfuck, Befunge, Between, BFStack,
Bitdeque, Bitwise Cyclic Tag, bit~, Bleh, Blindfolded Arithmetic, Boolfuck,
brainfuck, BrainIf, Caballo, CARP, Chicken, Circlefuck, Clockwise, Codesick,
Collatz Multiverse, Container, CreativeScript v2, Crement, CV(N)(C), Cyclic
tag, Decleq, Dimensional, DINAC, EGL, Eval, Fackward, FALSE, Fargo, Fish,
Flowchart, Forbin, Forþ, FRACTRAN, Freestajlo, Grapheme, Home Row, Hot, HQ9+
with headers, IEBEL, Inject, INTERCAL, Interprogck8, Kiss, lol waht i cant
edit talk pages, Minsky Swap, Modulous, Monotonic Boolfuck, Movesum,
Nandypants, NOR machine, Object disoriented, Packlang, Painfuck,
Parenthesys, Pilas, Pointless, Qoibl, Qrain, Quassaunt, RAM0, ROTfuck,
Rubic, SendStuff, Shakespeare, SLOW ACV MAMMALIAN, Smallfuck, Smu, Sonata,
SStack, Stisp, Suffolk, Super SNUSP, SwitchCase, Taglate, thisthat, Thue,
Unary, Underload, Unlambda, Unsquare, What!?, Whitespace.

<!-- TRICK-PROTOTYPES:END -->
