# Roadmap

Future work only, in priority order.  Language assessments, documented
walls, and ruled-out ideas live in `docs/limitations.md` and
`docs/walls.md`; completed work — including sections removed from this
file — lives in the commit history.

## New interpreters (in priority order)

Candidates from the esolangs wiki's Category:Unimplemented (verified via
the category API), restricted to languages with a complete specification
and a boolean-generator capability (input, a value conditional, output).
Per-language verdicts on everything ruled out are in the
assessed-and-rejected ledger in `docs/limitations.md`.

- **function x(y)** — Turing-complete: functions with defaults, `[~]`/`` `~ ``
  input, `[a]`/`` `a `` output, comparison operators, a ternary, recursion; a
  boolean generator branches on a comparison and prints 0/1.
- **CV(N)(C)** — Turing-complete: every command is an IPA syllable;
  fricatives do character/integer I/O, approximants do while loops and
  gotos on the accumulator, vowels do arithmetic.  The page's truth-machine
  (`soθɰ̊oθʋi`) is the boolean-generator seed.
- **DINAC** — `IN` reads an aschar or wubyte, `OUT` prints, IF-ELSE and
  WHILE on zero/nonzero, truth-machine example.  Bounded-storage machine,
  so the boolean generator is the whole story.
- **Fargo** — one input number per run with bit access (`@ x`), one output
  number with bit writes (`% x y`), conditional `: x y`, base-10 output `$`.
  Unknown computational class, but the bit interface is ideal for a
  parameterized generator.
- **Packlang** — Turing-complete: packages with the built-in IO package
  (`charGet`/`charPut`), `If`/`While`, XOR/`!`; the truth-machine example
  branches on `input ^ 48`.
- **Inject** — Turing-complete: label blocks, `readto`/`send` for line I/O,
  `skipq`/`skipif`/`skip` for control flow; the truth-machine example
  compares the input block against a `0` block.
- **Algebraic Programming Language** — Turing-complete: executed lines print
  their result and their variables read user input; `&`/`|` short-circuit
  with `IF(x, c) = x & c()` and a `WHILE` function give the generator its tree.
- **Interprogck8** — weaker candidate: `u` input, `div` output, and IFT/IFQ
  conditionals make a truth-machine, but the `[a b]` random range and `~`'s
  10% side effect need the seeded-randomness judgment call, and the
  function-based conditional is convoluted.

No 2D/grid candidates remain open: the `Category:Two-dimensional` ×
`Category:Unimplemented` pass produced Streetcode, Flowchart, Line, and
Circuit Diagram, all implemented.

## Transpilers

The only candidates identified (a second Forth dialect ↔ Forþ,
Boolfuck ↔ ABCDirection/Minifuck) each need a *new* interpreter first, so
they belong under "New interpreters" if that language is ever added.

## Deferred-removal candidates

A language becomes a candidate when it has real language-defined output but
no generator that uses it, or when its only boolean construction would break
a documented convention and its text generator is too thin to stand alone
(criteria and removed cases: `docs/limitations.md`).  Interpreter-only
languages with a working, uncapped boolean generator are **not** candidates.

**No language is currently a candidate.**  The standing argument for when
one reappears: most interpreter-only languages are the *only* implementation
on the wiki, so removal leaves a gap the admission criteria treat as real.
Resolve that tradeoff deliberately, not by default.

## Extra implementations (cross-checks)

`extra/assembly` holds RISC-V ports of already-interpreted languages, fuzzed
against the Python by `scripts/verify_differential.py`.  `extra/line` is a
different category — the only implementation of its language, kept out of
`registry.py` because its programs are PNGs — not an integration gap.

Two admission rules govern new cross-checks:

- **Fuzzability.** The generator's output must be complex enough to fuzz —
  branching, loops, or 2D routing.  A straight-line generator is already
  fully covered by the round-trip test.
- **Toolchain follows the model.** RISC-V fits machine-model languages
  (tape/pointer/counter → cells/registers/jumps).  Semantic languages
  (stacks, typed registers, 2D grids) have no cross-check toolchain, and
  RISC-V cross-checks are no-input only: the fuzzer feeds the *program* to
  the ELF's stdin.

Every audited candidate is either semantic, input-reading, or has
fixed-pattern output, so **none has a route today**.  Circuit Diagram is the
one unassessed case: its output genuinely varies with the table, but its
generator is already replayed over each table's entire input space, so a
differential would mostly re-cover that ground.  Revisit only if a concrete
bug suggests the two implementations could disagree.

## RISC-V assembly compilers

The compilers in `src/esolangs/compilers/` translate a program to RISC-V
Linux assembly, run under unicorn by `scripts/verify_riscv_unicorn.py`.  The
no-input rule does not apply (a compiled program is embedded, leaving stdin
free), but the toolchain rule does.

A compiler is worth building for **verification value** (a complex-output
generator exercised through a compile-then-fuzz differential) or **intrinsic
value** (genuine lowering — control flow, calls, memory, dispatch — rather
than per-command transliteration).  No candidate currently clears either bar.

**Harness note.**  A fuzz-dependent, input-reading compiler would first need
fixed stdin cases via `run_elf` or a compile-then-fuzz differential; the
current differential never compiles and the unicorn cases feed empty stdin.
Intrinsic-value compilers need none of that.

## Forbin's expression-position recursion

Forbin's *expression-position* calls (`x = f(y)`) recurse natively, bounded
only by Python's default recursion limit.  Closing this needs `_eval` itself
extended into a resumable continuation stack (the `_EvalTask` design,
rejected in `docs/walls.md`), and Forbin has no realistic program shape that
recurses this way.  **Not pursued unless a concrete program needs it.**

## Hanging-test optimization via state-cycle detection

State-cycle detection (`esolangs.vm.run_until_halt_or_cycle`) has replaced
wall-clock timeouts for step-capable deterministic machines; see
`docs/limitations.md` for coverage.  What remains:

- Painfuck's `y`, WII2D's `?`, and LaserFuck's random heading are
  non-deterministic and stay on the wall-clock backstop.
- **Recursion follow-up.**  `run_until_halt_or_ancestor` compares each
  newly-pushed frame's entry state (function, bindings, input position)
  against the frames beneath it.  Built for Forbin; **Suptiftam and Lamfunc
  also recurse and are the obvious follow-up**, each needing a
  `frame_entry_key` matching its own frame shape.
- **Branching cycle detection for `y`/`?` — considered, not started.**
  Forking at every random decision would prove "hangs no matter how the coin
  lands", but each decision doubles the live branches, a branch can still
  hang via unbounded growth, and the common case (hangs under *some* flips)
  is proved neither way.  Only worth building if that guarantee is needed.

## Input reordering (remainder)

Generators build under every input order and keep the shortest.  Seventeen
have landed; `docs/generator-optimizations.md`'s "Not yet done" carries the
screen figures, the hoist caveat, and the frame-mapping trap.

- **Unexamined, no layout work** — sbleq, brainif, three_x, taglate,
  minsky_swap, bio, decleq, nocomment, painfuck, rotfuck, bfstack.  Each
  screen figure is a **lower bound**: it prices the reorder alone, so a
  generator whose reads sit at its nodes gains the hoist too (AddSubJump
  screened 16.7%, delivered 31.7%).
- **Blocked on 2D layout surgery** — Dig, Flowchart, Streetcode, LaserFuck,
  Back, Clockwise, WII2D, and ArrowQueue (whose queue-fed template needs
  re-enqueue gadgets).  The bar: the emitted program changes and still
  consumes its inputs in the same order.

## Mutation-testing sweep

Every language is measured; a whole-repo sweep costs a few minutes, so
re-running one is the regression check for anything touching an interpreter.
The weakest suites:

| language | score | survivors |
| --- | --- | --- |
| AddSubJump | 80.2% | 23 |
| WII2D | 80.2% | 33 |
| Point Break | 80.4% | 94 |
| Painfuck | 80.9% | 49 |
| Basicfuck | 82.8% | 119 |
| 3x | 83.4% | 29 |
| Dimensional | 83.5% | 56 |

Basicfuck, Streetcode (98) and Suptiftam (93) now carry the most survivors
in absolute terms.

Two of these figures have been re-measured since the harness commits
`800f071` and `86c89b9`, which were only ever validated one language at a
time: AddSubJump came back at exactly 80.2% / 23, and Forbin at exactly
81.4% / 216 before the work below.  A full re-sweep of all 59 is still
outstanding.

LaserFuck has left this table.  It was the outlier at 66.7% / 82; the four
commits ending at `0a5f42b` took it to 76.0% / 59, and categorising all 59
of those survivors -- each run against the mutated bundle, so that every
claim is executed rather than read off the source -- turned most of them
into tests.  It now scores **91.1%, 22 survivors**, and what remains is
close to the equivalent-mutant floor: a dead attribute (`self.pos`, written
three times and read nowhere in the repository), flags only ever tested for
truth, and identities that no input can distinguish -- `(d + 2) % 4` is
`(d - 2) % 4`, and `rfind` is `find` on a string whose characters are
unique.  Three real gaps are left open deliberately: the two-laser
scheduler needs three simultaneous beams doing order-dependent work, and
one command-set mutant can only be caught by a program that *hangs*, which
is worse as a test than the gap it closes.

Two cautions about the measurement itself, both learned here.  A survivor
count is only trustworthy from a run with nothing else on the machine: the
per-test alarm fails a slow-but-passing test and scores it as a kill, so a
contended run reported 17 survivors where a solo run reports 22, the
difference being five mutants that are provably equivalent.  And a grid
containing `*` splits in a random direction, so any test built on one must
be symmetric about the split -- an asymmetric arm passes most runs and
fails the rest.

Three findings there generalise:

- **A default argument can hide a whole branch.**  Every test passed a
  heading because the suite's helper took `heading: int = 3`, so the branch
  that *draws* one at random was never executed -- not even by the test
  named for it, which loops `range(4)` and passes each value explicitly
  while its docstring says the grid "does not need to".  An edit making the
  draw raise on every call survived.
- **Widening a command literal is invisible without a test that uses a
  non-command character.**  Six survivors were of the form `"-"` becoming
  `"XX-XX"`.  The sharpest turned `"^v{}"` into a set containing `X`, after
  which `find` returns `-1` -- and a beam heading `-1` still moves rightward
  but answers the mirror guards backwards.
- **Command coverage is not branch coverage, twice over.**  Mirrors were
  only ever met head-on, and the pointer only ever moved at an edge, so the
  guards that refuse and the moves that do not grow the tape were both
  unexercised.

Forbin has left the table too, from 81.4% / 216 to **89.0% / 128** on
sixteen tests.  Its pool was nothing like a tape interpreter's: 843 lines
with a parser, and half the survivors were one shape -- an argument of
`_eval(node, frame, globals_, reader, depth)` replaced by `None` at one
call site.  That whole family is decidable rather than searchable, by
asking what *forces* each parameter (a top-level function name forces
`globals_`, an `in` forces `reader`, a local forces `frame`, a nested call
forces `depth`), and the forcing construct has to sit **at** the position:
assigning an `in` to a local and reading the local exercises `frame`, not
the reader.  94 killable mutants needed only 35 programs to witness, one
of which -- a two-wildcard iteration pattern -- accounts for fourteen.

Three cautions from that run, all of them about instrumentation rather
than about Forbin:

- **A probe whose own baseline moves reads as a witness for everything.**
  `_bound` interpolates `{value!r}`, and a `_Function` has no `__repr__`,
  so its message ends in an address that differs between processes.  The
  program that triggers it was recorded as the sole witness for 114
  mutants that were not killable at all; the honest count was 70, not the
  184 first reported.  Run the original battery twice in separate
  processes and diff it against itself before trusting any verdict.
- **Naming a dropped module in a docstring drops your test.**  The
  harness matches `esolangs.vm` and friends against the test's *text*, so
  a test written to cover `snapshot` without the VM was dropped for
  explaining why VM tests are dropped.  Watch the `dropped N` line.
- **"Never read" has to include "never operated on."**  `depth` is
  threaded everywhere and compared nowhere, which looked like a dead
  parameter; but `_call` does `depth + 1`, so eleven of the twenty-three
  `depth=None` mutants die on a `TypeError`.  Only the two that change the
  increment are equivalent.

Triaging one goes faster from the test file than from the diffs.  Six
shapes recur, and all six are mechanical:

## Dependency reduction

A table ignoring some inputs is a smaller table, and where a generator's cost
scales with *input count* rather than row count that beats any per-row
saving.  Taglate reduces (451 characters → 21).  What is open:

- **Taglate's gapped sets** (inputs 0 and 2 but not 1) need a discard between
  the reduced program's own reads, where the queue is not what the following
  reduce block assumes; output comes out arithmetically corrupted rather than
  permuted, so this is a real obstacle.  10 of the 40 reducible tables at
  `n == 3`.  **Odd-sized sets** are sidestepped by widening the window, which
  costs a tier back; narrowing properly needs the reduced program's own ghost
  handling suppressed.
- **Worth checking elsewhere.**  Any generator whose fixed cost scales with
  `n` admits the same reduction — decleq's `47n` normalize chains and
  clockwise's per-level rows are the obvious candidates, neither measured.

## Smaller open items

- **ArrowQueue's reusable drain** — a fixed-block leaf drain (rather than a
  staircase) is verified correct and written up in
  `docs/generator-optimizations.md`, but unshipped: it only wins from n≥5,
  past where anything exercises folding.  Worth revisiting if deep tables
  start mattering.
- **Streetcode evidence types** — carrying `_Machine._validate`'s five proofs
  in a chain of evidence classes would make the ordering checked rather than
  documented.  Deferred: it removes two correct `pragma: no cover` lines and
  nothing else, the ordering lives in one six-line method with one call site,
  and marker classes are erased at runtime.  Revisit only if the module is
  restructured anyway, or a validator lands whose ordering is non-obvious.
- **Severely constrained boolean generators** — caps are tracked so removal
  or lifting is deliberate.  No language is currently on this list.
