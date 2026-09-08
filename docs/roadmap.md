# Roadmap

Only live work belongs here. Completed findings, negative results, and
conditional ideas stay in [`docs/walls.md`](walls.md) and
[`docs/limitations.md`](limitations.md).

## New interpreters

Candidates are prioritized by a complete specification and an uncapped,
testable boolean-generator route. The assessed-and-rejected ledger is in
[`docs/limitations.md`](limitations.md).

- **DINAC:** ordinary nested IF/ELSE tree; indentation-sensitive parsing and
  defined EOF sentinels are the main interpreter work.
- **Alight:** indexed string-table lookup; 2D walking and function semantics
  are the cost. Its boolean construction is derived, not supplied by a wiki
  truth-machine.
- **function x(y):** recursive expression language. Choose native recursion
  with a documented ceiling or an explicit evaluation-frame stack before
  implementation.
- **Packlang:** C-like blocks and namespaces; its boolean generator reuses
  the existing ANF construction. Resolve the wiki's conflicting literal-base
  examples.
- **Interprogck8:** establish whether `DownAccLines` can route a full
  decision tree through its single current-function slot.
- **Pinyin:** re-audit and price a real two-input program before scheduling;
  required phonetic command triples and routing semantics are still unpinned.

## Research

- **Lower drawn control flow.** Lower arbitrary Streetcode programs and the
  boolean generator's printed-leaf decision trees. This is a compiler or
  source-machine emulator, not command transliteration. It needs a constructed
  Streetcode-program corpus/fuzzer and resolution of the reference
  interpreter's junction and post-corner gaps.
- **Scale Line boolean drawings.** The standalone Line generator has
  end-to-end measurements through seven inputs, while its regression suite
  reaches five; eight and above are unmeasured. Establish the renderer →
  extractor → simulator frontier with an all-leaf-reaching corpus, then only
  pursue subtree sharing or a denser layout if that measurement finds a real
  resource limit.
## Conditional follow-up

- **ArrowQueue reusable drain.** Ship the verified deep-fold drain only if a
  proof makes folding meaningfully testable at `n >= 5`; current coverage does
  not reach its crossover.
- **Reorder ArrowQueue inputs.** A three-input screen leaves 12.4% headroom,
  but its queued inputs cannot be renamed in place. Find a re-enqueue and
  grid-routing construction, then compare emitted, executed programs against
  the current template; abandon it if the routing spends the apparent gain.
- **`%^2^-1` fourteen inputs.** The staged fold's endgame strands its last
  duplicated cofactor pairs: rank order is steerable (pulsed doubling), but a
  merge needs the pair's value gap `d` inside a wipe window, and diving the
  partner maps `d -> amount - d` with the amount free in the window -- a
  derived, unbuilt alignment controller. Build it only if a ~20x-thirteen
  build cost (~430k plan ops, ~8MB templates, ~226 ops per merge) is
  acceptable; the walls around it are recorded in
  [`docs/walls.md`](walls.md).
