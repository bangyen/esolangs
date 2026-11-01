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

## First-implementation candidates

The 2026-11-01 wiki API screen found 2,537 language pages in neither
implementation-status category; the heuristic link filter retained 2,248.
Missing categories and links do not establish first-implementation eligibility.
Screen these in order under [curation](limitations.md#curation):

- **[Retrograde](https://esolangs.org/wiki/Retrograde):** reversible blocks
  with direction-dependent instructions. Admission probe (2026-11-01,
  wiki revision 198201): native conditionals pass 4,848 row executions,
  including all 276 tables through n=3 and five tables each at n=4..6.
  Ordered single-instruction input setters and final-current-cell extraction
  need no new opcode. Chunk emission is O(T), at most `14T + 4n - 13`
  characters; AND witnesses through n=16 attain `12n - 1` native steps
  (excluding the adapter dump). Three backlinks; no public implementation
  found in the spec, author links/repositories or targeted searches.
  Next: production integration, explicit zero-tape and dump conventions,
  canonical ablations and size/step pins, then the full language gate.
  The inline tree needs a construction-specific sharing exemption: native
  turns have paired lexical targets, not named calls.
- **[NQ](https://esolangs.org/wiki/NQ):** trit queue with guarded execution.
  Check the WIP specification, restricted output alphabet and contribution
  beyond existing queue/tag languages.

Before admission, check public implementations beyond wiki links, resolve core
semantics, and execute a loop-less Boolean generator with proved O(T)
construction and emitted size. Apply the existing verification gates.

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
    - B-tapemark: FENCED (2026-10-31); evidence in
      [limitations](limitations.md#notes-on-individual-languages).  Reopen
      on new page evidence (Talk page, author statement, reference
      implementation), a folded or narrow construction beating the named
      obstructions, or a real consumer for the other reading (the dialect
      branch is ready).

<!-- BLIND-REIMPLEMENTATIONS:START -->

90 of the 91 first implementations: 1 + i, 3x, 6-5, A Painter Ant,
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
- **Trick prototypes, round 2:** one admissible size rule per generator,
  executed with a control, shipped or recorded against CONTRIBUTING's gate.
  Round 1 covered 111/111. Restart by increasing count of kept ablation
  rules, alphabetically within ties. The zero-trick queue is BASICER,
  CARP, CreativeScript v2, HQ9+ with headers, Qrain; all five are complete.
  HQ9+ now folds constants. Next: Aprknia, Basicfuck, Chicken. Record
  completion as `[audits] trick_prototype = <date>`; retain earlier evidence.

<!-- TRICK-PROTOTYPES:START -->

5 of the 112 generators: BASICER, CARP, CreativeScript v2, HQ9+ with
headers, Qrain.

<!-- TRICK-PROTOTYPES:END -->

- **Constant-table audit:** size census 111/111 at n=1..8,10,12; n=0 is
  outside every generator's contract. Optimization reviews 15/111: Movesum,
  Parenthesys, Unary, Malbolge, Quassaunt, LaserFuck, Interprogck8,
  ABCDirection, BrainIf, Collatz Multiverse, Streetcode, Hot, Ascenic and
  Circuit Diagram improved; Line retains its read-first constant path.
  Malbolge also drains its final ignored byte before output on seventeen-input
  projections. Next: Pointless, Shakespeare, Qoibl. Keep this counter separate
  from trick prototypes.
