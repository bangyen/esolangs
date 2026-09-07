# Roadmap

Only live work belongs here. Completed findings, negative results, and
conditional ideas stay in [`docs/walls.md`](walls.md),
[`docs/limitations.md`](limitations.md), and
[`docs/generator-optimizations.md`](generator-optimizations.md).

## New interpreters

Candidates are prioritized by a complete specification and an uncapped,
testable boolean-generator route. The assessed-and-rejected ledger is in
[`docs/limitations.md`](limitations.md).

- **DINAC** — ordinary nested IF/ELSE tree; indentation-sensitive parsing and
  defined EOF sentinels are the main interpreter work.
- **Alight** — indexed string-table lookup; 2D walking and function semantics
  are the cost. Its boolean construction is derived, not supplied by a wiki
  truth-machine.
- **function x(y)** — recursive expression language. Choose native recursion
  with a documented ceiling or an explicit evaluation-frame stack before
  implementation.
- **Packlang** — C-like blocks and namespaces; its boolean generator reuses
  the existing ANF construction. Resolve the wiki's conflicting literal-base
  examples.
- **Interprogck8** — establish whether `DownAccLines` can route a full
  decision tree through its single current-function slot.
- **Pinyin** — re-audit and price a real two-input program before scheduling;
  required phonetic command triples and routing semantics are still unpinned.

## Research

- **Lower drawn control flow.** Lower arbitrary Streetcode programs and the
  boolean generator's printed-leaf decision trees. This is a compiler or
  source-machine emulator, not command transliteration. It needs a constructed
  Streetcode-program corpus/fuzzer and resolution of the reference
  interpreter's junction and post-corner gaps.
- **Lift the `%^2^-1` generic-table frontier.** The shipped packed ladder
  covers sampled tables through eleven inputs, but its twelve-input limit is
  workspace geometry, not a language wall. Develop a total planner that
  interleaves embedding and folding; the existing verified ten-input route is
  an experiment, not a general construction.

## Conditional follow-up

- **ArrowQueue reusable drain.** Ship the verified deep-fold drain only if a
  proof makes folding meaningfully testable at `n >= 5`; current coverage does
  not reach its crossover.
