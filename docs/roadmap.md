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

- **Plain-rewrite audits:** write the plain canonical construction, price
  every bespoke trick against it, and remove the ones whose saving is a
  fixed amount rather than a genuine percentage (see
  [CONTRIBUTING](CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping)).
  Eight of the first thirteen lost a trick.  Record a finished audit as
  `[audits] plain_rewrite = <date>` in the language's `language.toml`.
- **Brainfuck derivatives refused by the 2026-10-15 ban** are eligible
  again: screen them on route, spec and token substitution.
- **Movesum generator** (removed 9f3427b07, "no conditional means no
  generator story"): no ground excludes it, since ground 5 needs a proof
  that no generator exists, but it returns only with one.  With bits fed
  one per input, a first-line `42` key reads a single bit (index 0 or 1),
  and at run time there are only fixed-address copies, `sum` and halting
  when two commands leave the array unchanged.  With the row fed as one
  number v, `42=1` marks cell v and summing the 1-rows' cells prints
  f(v) in O(T) moves, but the stdin contract is per bit.
- **Malbolge per-arity layout** (parked 2026-10-29): live cells are 10-14% of
  the 59,049-cell image at n <= 12. Tables sit at 39,367-43,002 because the
  held top digit is 6; a bit-to-digit bijection putting it at 1, with hubs and
  stubs re-placed below ~14k, would cut n <= 12 programs about 4-5x. It
  re-derives the fold's digit math and its 2,464-sequence check.

<!-- PLAIN-REWRITE-AUDITS:START -->

Audited (68): ///, 1 + i, 3x, 6-5, A Painter Ant, ABCDirection, AddSubJump,
Algebraic Programming Language, Alight, ArrowQueue, Ascenic, B-tapemark,
Back, Befunge, BFStack, Bitdeque, bit~, Blindfolded Arithmetic, Boolfuck,
brainfuck, BrainIf, Circlefuck, Circuit Diagram, Clockwise, Collatz
Multiverse, Container, Crement, CV(N)(C), Decleq, Dig, Dimensional, EGL,
FALSE, Fargo, Fish, Flowchart, Forbin, Forþ, FRACTRAN, Freestajlo, Home Row,
Hot, Inject, INTERCAL, Interprogck8, LaserFuck, Line, Malbolge, Minifuck,
Modulous, Packlang, Painfuck, Piet, Qoibl, RAM0, ROTfuck, S*bleq, SLOW ACV
MAMMALIAN, Smallfuck, SStack, Streetcode, Subleq, Suffolk, Taglate,
thisthat, Thue, Underload, Unlambda. Next by kept `[ablations]`: NOR machine
3, SendStuff 3, Smu 3, Unary 3, Balik 2, Basicfuck 2, Bitwise Cyclic Tag 2,
Bleh 2, Caballo 2, Codesick 2, Cyclic tag 2, Eval 2, Fackward 2, Minsky Swap
2, Pointless 2, Quassaunt 2, Sonata 2, Stisp 2, Super SNUSP 2, SwitchCase 2,
Unsquare 2.

<!-- PLAIN-REWRITE-AUDITS:END -->

- **Blind reimplementation of first implementations:** a clean-room
  interpreter written from the wiki page alone, diffed over the generated
  corpus.  With no outside interpreter, this is the only independent
  check a first implementation gets; the first fourteen found one spec
  contradiction (Tiangou halted on underflow), the rest spec gaps now in
  the docstrings.  Record one as `[audits] blind_reimplementation = <date>`.

<!-- BLIND-REIMPLEMENTATIONS:START -->

13 of the 89 first implementations: Aprknia, Balik, BASICER, Bleh,
Freestajlo, Hot, Kiss, lol waht i cant edit talk pages, Pilas, S*bleq,
Sonata, Stisp, SwitchCase.

<!-- BLIND-REIMPLEMENTATIONS:END -->
