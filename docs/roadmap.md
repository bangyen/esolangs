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

- **Malbolge n = 14..16 layout:** n <= 13 now ends at its highest live cell
  (13,144 characters); 14..16 still emit the 59,049-cell image.
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
  check a first implementation gets; the first fourteen found one spec
  contradiction (Tiangou halted on underflow), the rest spec gaps now in
  the docstrings.  Record one as `[audits] blind_reimplementation = <date>`.

<!-- BLIND-REIMPLEMENTATIONS:START -->

53 of the 91 first implementations: 1 + i, 3x, 6-5, A Painter Ant,
ABCDirection, AddSubJump, Algebraic Programming Language, Alight, Aprknia,
ArrowQueue, Ascenic, B-tapemark, Back, Balik, BASICER, Basicfuck, Between,
BFStack, Bitdeque, bit~, Bleh, Blindfolded Arithmetic, BrainIf, Caballo,
CARP, Circlefuck, Clockwise, Codesick, Collatz Multiverse, Container,
CreativeScript v2, Decleq, Dig, Dimensional, DINAC, EGL, Eval, Fackward,
Fargo, Flowchart, Freestajlo, Hot, Kiss, lol waht i cant edit talk pages,
Monotonic Boolfuck, Movesum, Nandypants, Pilas, Qrain, S*bleq, Sonata,
Stisp, SwitchCase.

<!-- BLIND-REIMPLEMENTATIONS:END -->
