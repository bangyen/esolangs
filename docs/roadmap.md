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

- **Malbolge:** generation at seventeen inputs is open (2026-10-26): a
  table cell cannot carry eight address-independent meanings (window
  conflict graph: independence number 8, twelve classes), lockstep
  adjacent-cell reads reach 110 of 512 triples a phase, and the
  seven-meaning build's 1,994 gotos have 2.77 cells each in the
  complement against a 3.6-cell annealed routing floor (certified
  at least 2.99). The composition routes priced since -- hub
  substrates in the shipped and re-addressed geometries, marching
  and data-initialized decoders, threaded and streaming emission,
  membership dispatch, the permutation families -- are closed in
  [limitations](limitations.md) on eligibility, mechanism or
  measured rates. Reopen only with a decoder variant whose
  word-mediated landing is realized in a full build that passes its
  gates (parity contract, per-row cases and a fresh census at the new
  window embedding, then placement and threaded rates inside the
  9,897-cell complement), or with new mathematics toward the 46,076
  bits an impossibility proof needs beyond counting.
  Lead (2026-10-27): a `p` or `*` run during the initial walk or a
  lockstep sweep deposits a full word for one source cell, against 25-30
  in the shipped label phase; its words fall in five value bands, so one
  window sweep places about 30 labels and leaves 29 of 94 residues
  uncovered. Untested: steering the sweep from words prepared in the
  window.
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

<!-- PLAIN-REWRITE-AUDITS:START -->

Audited (26): 3x, 6-5, Algebraic Programming Language, Alight, Ascenic,
Back, Boolfuck, BrainIf, Circlefuck, Circuit Diagram, Clockwise, Dig,
Flowchart, INTERCAL, LaserFuck, Line, Minifuck, Packlang, Polynomial,
S*bleq, SLOW ACV MAMMALIAN, Smallfuck, SStack, Streetcode, Subleq, thisthat.
Next by kept `[ablations]`: AddSubJump 6, BFStack 6, CV(N)(C) 6, Malbolge 6,
Container 5, Fargo 5, Forbin 5, Inject 5, ArrowQueue 4, B-tapemark 4,
brainfuck 4, Collatz Multiverse 4, Dimensional 4, FALSE 4, FRACTRAN 4,
Freestajlo 4, Painfuck 4, Piet 4, RAM0 4, ROTfuck 4, Suffolk 4.

<!-- PLAIN-REWRITE-AUDITS:END -->

- **Blind reimplementation of first implementations:** a clean-room
  interpreter written from the wiki page alone, diffed over the generated
  corpus.  With no outside interpreter, this is the only independent
  check a first implementation gets; the first fourteen found one spec
  contradiction (Tiangou halted on underflow), the rest spec gaps now in
  the docstrings.  Record one as `[audits] blind_reimplementation = <date>`.

<!-- BLIND-REIMPLEMENTATIONS:START -->

14 of the 81 first implementations: Aprknia, Balik, BASICER, Bleh,
Freestajlo, Hot, Kiss, lol waht i cant edit talk pages, Pilas, S*bleq,
Sonata, Stisp, SwitchCase, Tiangou.

<!-- BLIND-REIMPLEMENTATIONS:END -->
