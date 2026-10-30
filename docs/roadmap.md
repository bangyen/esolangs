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
  - *Next lead (2026-10-27, untested):* a `p` or `*` run during the
    initial walk or a lockstep sweep deposits a full word for one source
    cell, against 25-30 in the shipped label phase; its words fall in
    five value bands, so one window sweep places about 30 labels and
    leaves 29 of 94 residues uncovered. Try steering the sweep from
    words prepared in the window.
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

- **Malbolge's two searches as rules:** navigation (`emitter.py` `goto`)
  and the short layout (`digits.py` `_short_layout`) are the repo's only
  table-independent searches ([limitations](limitations.md#searches-kept)).
  A closed-form navigation must end the main line below 6,561 at n=1; the
  three tried end at 13,501, and on the BFS's memory states no navigation
  with at most three jumps per `goto` fits.  Reordering the label phase
  (seed chains before the pointer priming, ~1,800 path cells of returns
  past 127) is the open route.  The layout's cost is where navigation lands
  each walked cell, so a navigation rule comes first.
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
    - SLOW ACV MAMMALIAN: LEAPFROG "jump[s] to the ...th instruction"
      but ours resumes after it.  The cell-256 programs now run under
      both; the cell-255 chains (`_mammalian_compact`, `_mammalian255`)
      still need resume-after.
    - B-tapemark: the swap-marker Decision's only evidence is that the
      other reading hangs our own generated programs (page re-read
      2026-10-30, no Talk page; history unread).  In the traced ``01``
      program, a swap round trip
      (swap at X heading d0, back at Y heading d1) resumes the program at
      X+d1 under ours, X+d0 under the other, and leaves the blank grid's
      mark at Y vs Y+d1, so safe needs d1=d0 and a cancelling second round
      trip per branch (the mark offset is the answer); the stage's turn
      gives d1!=d0.  Not built; the extra trip would add about a
      stage-sized block per input (estimated, unmeasured).
    - Minifuck: non-commands count as instructions `[` can skip, against
      "only 3 instructions"; the `[x` filler relies on it.  No drop-in
      for `[x` works under both: every real command in the slot differs by
      branch (`<` ends at p vs p+1; `[` and `.` flip, print or read), and no
      `<`/`[` string of length 1..14 matches `[x` on 300 random tapes.  A
      both-readings construction would have to restructure the conditional,
      untried.  The page's sole example has no non-command.

<!-- BLIND-REIMPLEMENTATIONS:START -->

91 of the 91 first implementations: 1 + i, 3x, 6-5, A Painter Ant,
ABCDirection, AddSubJump, Algebraic Programming Language, Alight, Aprknia,
ArrowQueue, Ascenic, B-tapemark, Back, Balik, BASICER, Basicfuck, Between,
BFStack, Bitdeque, bit~, Bleh, Blindfolded Arithmetic, BrainIf, Caballo,
CARP, Circlefuck, Circuit Diagram, Clockwise, Codesick, Collatz Multiverse,
Container, CreativeScript v2, Crement, CV(N)(C), Decleq, Dig, Dimensional,
DINAC, EGL, Eval, Fackward, Fargo, Flowchart, Forbin, Forþ, Freestajlo,
Grapheme, Home Row, Hot, HQ9+ with headers, IEBEL, Inject, Interprogck8,
Kiss, LaserFuck, Line, lol waht i cant edit talk pages, Minifuck, Minsky
Swap, Modulous, Monotonic Boolfuck, Movesum, Nandypants, NOR machine, Object
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

19 of the 112 generators: Alight, Aprknia, BASICER, Bleh, CARP, Chicken,
CreativeScript v2, Cyclic tag, DINAC, HQ9+ with headers, IEBEL, Kiss, lol
waht i cant edit talk pages, Monotonic Boolfuck, Movesum, Parenthesys,
Pilas, Qrain, Shakespeare.

<!-- TRICK-PROTOTYPES:END -->
