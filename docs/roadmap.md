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

- **Plain-rewrite audits are one-off:** Streetcode and LaserFuck were each
  audited once -- write the plain canonical construction, price every
  bespoke trick against it, and remove the ones whose saving is a fixed
  amount rather than a genuine percentage (see
  [CONTRIBUTING](CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping)):
  Streetcode's lift and tail overlap, LaserFuck's sized leaf retirement and
  Dig's default banded tree came out this way, and four of SStack's six
  sharing routes (2026-10-21), 6-5's copy node and Minifuck's dead lookup
  threshold (2026-10-22), and BrainIf's leaf trampoline and odd-n loop step
  and ThisThat's DAG single-arm router (2026-10-27). Flowchart, Circlefuck,
  Circuit Diagram, Clockwise and Back kept every trick and Ascenic has none. Line, Alight, Polynomial, Slow ACV
  Mammalian, APL, INTERCAL and Packlang are inventoried (2026-10-22): their
  unrecorded mechanisms are width/balance layout or core-construction
  constants, not default-path tricks. The audit is repeatable per generator.
  Eight of the thirteen audited lost a trick. Next by kept `[ablations]`
  (2026-10-27): Smallfuck 8, 3x 7, Boolfuck 7, and 6 each for S*bleq,
  Subleq, Brainfuck, BFStack, CVNC and AddSubJump.
- **Blind reimplementation of first implementations:** 14 of the 81 have a
  clean-room interpreter written from the wiki page alone and diffed over
  the generated corpus (2026-10-27): Aprknia, Balik, BASICER, Bleh,
  Freestajlo, Hot, Kiss, lol waht, Pilas, S*bleq, Sonata, Stisp,
  SwitchCase, Tiangou. They found one contradiction of the spec (Tiangou
  halted on underflow); the other disagreements were spec gaps, now
  recorded in the docstrings. With no outside
  interpreter, this is the only independent check the rest get.
