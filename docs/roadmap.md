# Roadmap

Planned work, in priority order.  Language assessments, documented walls,
and ruled-out ideas live in `docs/limitations.md`; completed ideas live in
the commit history.  This file only tracks what is still on the table.

## New interpreters (in priority order)

Candidates from re-scanning the esolangs wiki's Category:Unimplemented and
from a user-maintained language list on the wiki.  What was ruled out
(Gravity, Earfuck, Conveyor, Chainlang, Binary ///, Fourfuck, Aaargh++,
Bitwise Cyclic Teast, and the languages already implemented elsewhere) is
in the commit history and `docs/limitations.md`.

Checking that list against the admission criteria surfaces a handful of
languages worth recording as potential candidates.  Jumplang, Eso2D,
Minimal operation language, brainfunc, and Yaren are wiki-categorized
**Implemented** (each page documents external interpreters), so under the
"not already implemented elsewhere" criterion they are not candidates; the
record below is restricted to languages in the wiki's **Unimplemented**
category (verified via the category API), with a complete specification and
a boolean-generator capability (input, a value conditional, and output):

- **function x(y)** — complete spec, Turing-complete: functions with
  defaults, `[~]`/`` `~ `` input, `[a]`/`` `a `` output, comparison
  operators, a ternary, and recursion; a boolean generator branches on a
  comparison and prints 0/1.
- **CV(N)(C)** — complete spec, Turing-complete: every command is an IPA
  syllable; fricatives do character/integer I/O, approximants do while
  loops and gotos on the accumulator, vowels do arithmetic.  The page's
  truth-machine (`soθɰ̊oθʋi`) is the boolean-generator seed.
- **DINAC** — complete spec: `IN` reads an aschar or wubyte, `OUT` prints,
  IF-ELSE and WHILE on zero/nonzero, truth-machine example.  Bounded-
  storage machine, so the boolean generator is the whole story.
- **Fargo** — complete spec: one input number per run with bit access
  (`@ x`), one output number with bit writes (`% x y`), conditional
  `: x y`, base-10 output `$`; the truth-machine example is the
  boolean-generator seed.  Unknown computational class, but the bit
  interface is ideal for a parameterized generator.
- **Packlang** — complete spec, Turing-complete: packages with the built-in
  IO package (`charGet`/`charPut`), `If`/`While`, XOR/`!`; the truth-machine
  example branches on `input ^ 48`.
- **Inject** — complete spec, Turing-complete: label blocks, `readto`/`send`
  for line I/O, `skipq`/`skipif`/`skip` for control flow; the truth-machine
  example compares the input block against a `0` block, the boolean
  generator's branch.
- **Algebraic Programming Language** — complete spec, Turing-complete:
  executed lines print their result and their variables read user input;
  `&`/`|` short-circuit with `IF(x, c) = x & c()` and a `WHILE` function
  give the boolean generator its tree.
- **Interprogck8** — complete spec but a weaker candidate: `u` input, `div`
  output, and IFT/IFQ conditionals on a 84/81 compare make a truth-machine
  (documented on the page), but the spec's `[a b]` random range and `~`'s
  10% side effect need the seeded-randomness judgment call, and the
  function-based conditional is convoluted.

The remaining unimplemented-in-repo languages on that list were assessed
and ruled out (no input, no output, or non-char/line I/O; incomplete or
unstable specs; trivial reskins; or external implementations); the
per-language verdicts are in the assessed-and-rejected ledger in
`docs/limitations.md`.

## 2D/grid candidates (from Category:Two-dimensional)

A separate pass cross-referenced the wiki's `Category:Two-dimensional`
against `Category:Unimplemented` (109 overlaps) looking specifically for
languages whose control flow is genuine grid navigation — where a boolean
generator has to actually route an instruction pointer around cells based on
a value, the way Befunge's `_`/`|` or this repo's Dig/Back/Clockwise/A
Painter Ant do — rather than a language with a high-level `if`/`while` that
would make the generator close to trivial to write by hand.  Streetcode,
Flowchart, and Line came out of this pass and are implemented; what each
interpreter decided, and why, is in `docs/streetcode.md`, the Flowchart
module docstring, and `extra/line/WIP.md`.

**One residual question, on Flowchart.**  The wiki's Kolakoski example
states no expected output, so the test pins current behaviour as
characterization, and the output's repeating tail traces to the diagram
rather than to any interpreter choice: pointer interleaving is
byte-identical across creation, reverse, and per-step reading order, and
the full {1 turns left, 1 turns right} x {empty prints nothing, empty is
zero} matrix leaves the tail period-4 in all four variants (only the
shipped combination passes the truth machine and the cat at all).  The
remaining possibility is that the diagram simply does not produce the
Kolakoski sequence as drawn; confirming that needs the diagram's author, so
a talk-page question is the cheapest way to settle it.

**Circuit Diagram is implemented**, interpreter and boolean generator both,
their judgment calls derived in the module docstrings of
`src/esolangs/interpreters/grid_based/circuit_diagram.py` and
`src/esolangs/tools/boolean/circuit_diagram.py`.  Four findings are worth
keeping here.

**The page's prime tester is drawn with five characters missing.**  Its only
worked example has two OR gates whose second input no gate drives, so as
drawn it prints nothing for every input.  The repair is derived rather than
guessed and is unique: the circuit is a product of sums, not the sum of
minterms its caption implies, and requiring the whole to be primality over
0-15 forces the two missing signals to `b` and `~c`.  The page itself shows
where they belong — for `~c` it already draws the two `=` crossovers that
the missing diagonal would cross, so the diagram carries a diagonal's
crossings without the diagonal itself.  Both the repaired circuit (replayed
over all sixteen inputs against the primes) and the as-drawn silence are
pinned in `tests/interpreters/test_circuit_diagram.py`.  Reporting this on
the talk page is the cheapest way to settle it, as with Flowchart's
Kolakoski example.

**The obvious execution model is falsified by the page's own flip-flop.**
Reading wirings as holding their value until overwritten, and halting once
nothing changes, cannot produce the `1N1N1N...` the page states — a sticky
wiring never shows a Null after a 1.  Values are therefore events lasting
one generation, and gates bridge them with a latch per input slot, which is
what the spec's "the gate waits until the other input comes" sentence asks
for.  All three of the page's circuits work under that model.

**The generator is a real gate network, and its geometry is the work.**  A
truth table is the language's native idiom, so the boolean generator emits
a sum of minterms — one `-` input line per bit, a bus per literal, an `a`
chain per minterm, an `o` chain combining them, `:` printing the answer —
rather than the decision tree the other 2D generators build.  Three
constraints govern the layout:

- **Crossings are the idiom, not a hazard.**  A network where every input
  feeds every minterm is not planar, so wires must cross; a layout that
  bans `=` cannot be made to work at any spacing.  The spec's
  crossover connects "opposite wires", so one `=` carries a horizontal and
  a vertical signal past each other in separate wirings — confirmed against
  the interpreter.  The generator therefore models wire segments and
  renders each cell from its coverage, rather than painting in draw order.
- **A gate's columns must be clear of every bus.**  A bus running down
  through a gate's input junction carries that gate's own output back to
  its input, and a wiring may not touch both, so gates reserve their input,
  glyph, and output columns together.
- **Fan-out is free; driving twice is not.**  A bus tapped by many gates is
  still one wiring with one driver, so each input's `~` is computed once
  and shared.  A second *driver* would XOR into the value and make `:`
  print again, so the tests assert every run prints exactly one character —
  the cheapest detector for both a double drive and two junctions merging
  through the eight-way `.`.

The generator is verified by replaying its output through the interpreter
over each table's whole input space: all sixteen two-input functions, all
four one-input ones, five three-input tables, and the four-input primality
table — the same function the wiki's hand-drawn prime tester computes,
reached as a sum of minterms rather than its product of sums, so the two
constructions agree on all sixteen inputs.

**Out of scope, and why.**  User-defined functions (`{name ... }`), the
constant sources `(` and `)`, the wire-removal function `{%`, the clock `t`,
and letter-labelled wires are specified but appear in *none* of the page's
examples, so there is no diagram to derive their geometry from — the same
gap that kept Gate out.  Each raises a `ValueError` naming it.  `t` would
additionally make output time-dependent.

Considered and rejected in the same pass: **Highways** (excellent
roundabout/routing mechanic, but junction direction, sign execution order,
and crash tie-breaking are genuinely random with no seed — fails the
determinism criterion); **Dilemma** (no I/O commands at all, pure
maze/DFS); **TableLang**, **Marz**, **RingCode**, **GridScript** (a
high-level `if`/`while`/`SWITCH` construct makes the generator trivial, or
the spec is unstable); and **Gate**, rejected on spec-completeness.  Its lack of an input command is not the blocker — output,
constants, and a value-testable branch are exactly the parameterized
(input-by-substitution) profile that Back, RAM0, and Minsky Swap are built on.
The blocker is that the page never exercises the two commands such a generator
needs: `+` (the branch) appears in none of the nine worked examples, and no
example emits output at all, so neither the branch geometry nor the output
path can be derived the way Flowchart's gaps were pinned by its examples (see
the assessed-and-rejected ledger in `docs/limitations.md`).  **Circuit
Diagram**, the alternative in that genre, is implemented (above).

## Transpilers

The only candidates identified (a second Forth dialect ↔ Forþ,
Boolfuck ↔ ABCDirection/Minifuck) each need a *new* interpreter first, not
just glue between two already-implemented languages, so they belong under
"New interpreters" if that language is ever added, not here.

## Deferred-removal candidates

A language becomes a candidate when it has real language-defined output but
no generator that uses it (no conditional to drive a boolean generator, or a
boolean cap too low to be interesting), or when its only boolean construction
would break a documented convention and its text generator is too thin to
stand alone — see `docs/limitations.md` for the removed cases and the
criteria.  The interpreter-only languages with no text generator but a
working, uncapped boolean generator (Back, BF-PDA, Bitdeque,
Jaune, Lamfunc, Minsky Swap, RAM0, Grapheme, A Painter Ant, ArrowQueue,
Streetcode, Flowchart, Circuit Diagram) are
**not** candidates: they participate fully in the repo's verification
machinery via the boolean generator, and their only weakness is an
interpreter-invented state dump where the wiki defines no text output.

**Against removal (the standing argument, for when a candidate reappears).**
Most interpreter-only languages are the *only* implementation on the wiki,
so removing them leaves the language with no implementation at all — which
the admission criteria treat as a genuine gap.  The tradeoff is between "no
generator ⇒ cannot participate in the repo's verification machinery" and
"sole implementation ⇒ removing creates a gap"; when a language has neither
a text nor a working boolean generator, that tradeoff should be resolved
deliberately rather than by default.

## Extra implementations (cross-checks)

`extra/` holds two different kinds of thing, and they are integrated
differently on purpose:

- **Cross-check ports** (`extra/rust`, `extra/assembly`) are second
  implementations of languages the package already interprets, so every one
  of them is in `registry.py`.  Being differentially testable against the
  Python is the whole reason they exist, so the root-level harnesses
  (`scripts/verify_differential.py`, `scripts/verify_riscv_unicorn.py`,
  `scripts/verify_extra_generators.py`) and two suites under `tests/` drive
  them directly.  The rest of this section is about these.
- **Unsupported-medium implementations** (`extra/line`) are the *only*
  implementation of their language, kept out of `registry.py` because their
  programs are not text the registry's pipeline can carry (Line's are PNGs).
  There is no in-package counterpart to differ against, so the cross-check
  harnesses do not apply; `extra/line` is self-contained, keeps its own
  pytest suites next to the code, and runs from CI's `line` job.  This is a
  different category, not an integration gap.

The `extra/` cross-checks (Rust and RISC-V ports of the interpreters, run
against the Python ones by `scripts/verify_differential.py`) earn their keep
only where they are *broad* and *independent*: the reference is written from
the spec rather than ported from the Python, and the differential can fuzz
hundreds of random programs rather than a hand-picked handful.

**The fuzzability test.**  Having a text or boolean generator is necessary
but not sufficient — what matters is whether the generator's output is
*complex enough to fuzz meaningfully*: a generator that emits branching,
loops, or 2D routing produces programs a random differential can exercise
beyond what the fixed round-trip corpus covers, while a straight-line
generator (a per-character program mirroring the text) is already fully
verified by the round-trip test, so a second implementation would find
nothing new.

**Toolchain follows the model.**  RISC-V assembly fits the machine-model
languages (a tape/pointer/instruction-counter maps 1:1 onto cells,
registers, and jumps); Rust fits the semantic ones (stacks, typed registers,
bit manipulation, 2D grids, where hand-written assembly would be unreadable).

**No input in RISC-V.**  RISC-V cross-checks are for no-input/output-only
languages only.  The fuzzer feeds the generated *program* to the RISC-V ELF
as its stdin (`scripts/verify_differential.py`), and the Python side reads
whole lines while the unicorn runner does raw byte reads, so an input-reading
port would need to rewire input-bit passing and match the line-delimited
`input_char` semantics.  Languages whose generators read input belong in the
Rust column, where the reference gets input bits directly.

**Worth adding (audited).**  These languages have complex-output generators
(arithmetic encodings, branch-and-goto OISCs, runtime state carried across
characters) that a random differential fuzz would exercise beyond the
round-trip corpus, so a cross-check would add real verification.

| Toolchain | Languages |
| --- | --- |
| Rust | AddSubJump (branch-and-goto OISC), Collatz Multiverse (runtime odd/even rules), Polynomial (integer roots encoding a command stream), Dig (2D mole grid with runtime segment counts), Container (threshold-rule firing), ZTOALC L (Collatz-trajectory-driven execution), Factor (a giant integer whose prime factors re-encode a looped brainfuck program), Back (2D beam reflection routing), A Painter Ant (2D cycle-stable routing), Bitdeque (deque + register + goto).  Those that read input — and the 2D grid models — belong in Rust under the no-input RISC-V rule above. |

**Judgment call (borderline).**  The generator is stateful or looped, but
its output is a fixed pattern the round-trip already covers, so a cross-check
would add little: brainfuck, BFStack, BrainIf, Minifuck, Modulous, SLOW
ACV MAMMALIAN, WII2D, Home Row.  These stay without a cross-check unless a
specific bug motivates one.  Clockwise and 3D Brainfuck sit in the same
class: Clockwise's 2D routing is one fixed ring shape (only the ring size
and the parity pattern vary with the text), and 3D Brainfuck's generator is
the brainfuck generator's output with ``>``/``<`` renamed to ``n``/``s``.

**Circuit Diagram is unassessed on this axis.**  Its generator's output is
not a fixed pattern — the gate network's shape, its crossovers, and its
fan-out all vary with the truth table — so it does not belong in the
borderline class above, and on the toolchain rule a 2D grid model would go
to Rust.  What holds it back from the worth-adding table is that its
verification is already unusually strong without one: the generator is
replayed through the interpreter over each table's *entire* input space, so
a random differential would mostly re-cover ground the exhaustive replay
already covers.  Worth revisiting only if a concrete bug suggests the two
implementations could disagree somewhere the replay does not reach.

## RISC-V assembly compilers

The compilers in `src/esolangs/compilers/` translate a program to
RISC-V Linux assembly, assembled and run under unicorn by
`scripts/verify_riscv_unicorn.py`.

The cross-checks' no-input rule does not apply here: a cross-check reference
receives its program via stdin, but a compiled program is embedded in the
emitted assembly, so the ELF's stdin is free for the program's own input —
Suffolk's `,` already emits a `read` syscall.  Candidates are still bound
by the toolchain rule (RISC-V fits machine-model languages), just not by
the input rule.

A compiler is worth building for either of two reasons: **verification
value** (a complex-output generator exercised through a compile-then-fuzz
differential, the rationale above) or **intrinsic value** (the emitted code
does genuine lowering — control flow, calls, memory, dispatch — rather than
per-command transliteration, or the language is notable enough that the
artifact stands alone).  The candidates below are on the intrinsic axis;
their round-trip and hand cases are their verification, so they are not
blocked on the harness note below.

- **ZTOALC L stays in the Rust column.**  Heterogeneous int-or-array
  values, arrays-of-arrays, bounds checks, and trajectory-driven dispatch
  are the semantic class the toolchain rule sends to Rust; even on the
  intrinsic axis, the one genuinely interesting piece (computed-goto
  dispatch over the Collatz trajectory) is a small fraction of the emitted
  code — the bulk would be an expression interpreter over heterogeneous
  arrays, so emitting that in assembly would be strictly harder and no more
  verifiable than the Rust port already on the worth-adding table.

**Harness note (build only if a fuzz-dependent candidate lands).**  The
differential (`scripts/verify_differential.py`) never compiles, and the
compiler cases in `scripts/verify_riscv_unicorn.py` feed an empty stdin, so
an input-reading compiler whose value depends on fuzzing needs either fixed
stdin cases via `run_elf` or a compile-then-fuzz differential feeding the
program's input to the compiled ELF.  Intrinsic-value compilers do not need
that machinery, so this is not a prerequisite for any candidate above.

## Forbin's expression-position recursion (remaining depth-cap gap)

Forbin's *expression-position* calls (`x = f(y)`, where the assignment
needs the callee's return value back synchronously mid-expression) recurse
natively, bounded only by Python's own default recursion limit rather than
a documented cap (the statement-position conversion that removed the
invented 250-level cap is in the commit history).  See `docs/walls.md`'s
state-cycle-detection section for the full reasoning: Forbin has no
realistic program shape that recurses this way (`return` exits a call
immediately, so there is no return-value-threading idiom that would
produce deep expression-position recursion in practice), which is why this
was scoped out rather than built as part of the original conversion.

**Not pursued unless a concrete program needs it.**  Closing this gap
would mean extending `_eval` itself into a resumable continuation stack
(an `_EvalTask`-per-expression design, recorded and rejected in
`docs/walls.md`) — materially more machinery than the
statement-position conversion for a case with no known real-world Forbin
program that hits it.  Worth revisiting only if a program surfaces that
needs deep expression-position recursion and Python's default limit is
insufficient.

## Hanging-test optimization via state-cycle detection

Hanging programs are bounded with wall-clock timeouts (SIGALRM in the
robustness tests and on the differential fuzzer's Python side, and
instruction-count caps on the native references) except where state-cycle
detection (`esolangs.vm.run_until_halt_or_cycle`) has replaced them for
step-capable, deterministic machines — see `docs/limitations.md` for which
interpreters are covered and why the wall-clock backstop remains for the
rest.  What remains:

- Painfuck's `y`, WII2D's `?`, and LaserFuck's random heading are
  non-deterministic, so all three stay on the wall-clock backstop.
- **Recursion stays cycle-undetectable, but is now separately checkable.**
  A call that never returns pushes one new frame per `step()` and none is
  ever popped, so a `snapshot()`'s frame tuple strictly grows and two
  whole-machine snapshots can never compare equal — unbounded growth, the
  same class `+[>+]` already falls into.  `run_until_halt_or_ancestor` is
  the narrower check that class allows: it compares each newly-pushed
  frame's entry state (function, bindings, input position) against the
  frames already beneath it, rather than whole-machine snapshots across
  time, so a frame about to replay an ancestor proves the recursion cannot
  terminate.  Built for Forbin, which had no hang test at all before it.
  The input position carries the soundness — a recursion whose base case
  waits on an unread byte enters with identical bindings every lap, and
  keyed on bindings alone would be called a hang one read from returning.
  It still does not catch every infinite recursion (bindings that
  genuinely never repeat), so the wall-clock backstop stays for that
  class, and it costs O(depth) per push against the cycle detector's
  O(1) — affordable only because it runs once per call, not per step.
  Suptiftam and Lamfunc also recurse and are the obvious follow-up; each
  needs a `frame_entry_key` matching its own frame shape.  See
  `docs/walls.md` for the full argument.
- **Branching cycle detection for `y`/`?` (considered, not started).**
  Forking the walk at every random decision and requiring *every* branch to
  prove a cycle would soundly prove "this program hangs no matter how the
  coin lands" without faking determinism (unlike forcing `y`/`?` to a fixed
  outcome, which would prove things about a different, deterministic
  program instead of the real one).  Not pursued: each random decision
  doubles the live branches, undoing the O(1)-memory point of Brent's
  algorithm; a branch can still hang via unbounded growth (the class cycle
  detection already can't catch), so the branch tree needs its own bound
  and doesn't fully replace the wall-clock backstop; and the common case —
  hangs under *some* coin flips, halts under others — isn't proved either
  way, only the all-branches-hang case is.  The wall-clock backstop already
  handles both languages correctly, so this is only worth building if the
  "always hangs" guarantee is specifically needed.

## Boolean generators that still emit a full decision tree

A generator "folds" when a subtree whose table rows all agree becomes a
leaf instead of branching on bits that cannot change the answer.  Most of
the tree generators do; the ones below still spend a branch per level on
every path, and each is recorded with what it would take, because the
reason differs per language and reasoning from the shape of the code
proved unreliable — Between, LaserFuck, BrainIf, Dig, Modulous, Unsquare
and Nevermind were each written off on structural grounds and each folded
once actually probed.

The rule that did hold: folding pays when a folded leaf's cost does not
scale with the depth it skipped.  Where a leaf has to make up work per
skipped level, the fold cancels.

**Still open, in rough order of promise.**

- **Circlefuck** (and `circlefuck_byte`) — the closest.  A folded leaf
  must clear the cell the skipped `[[-]` would have cleared and make up
  the `<` moves those levels walked; adding the clear alone fixes `n == 1`
  and leaves `n >= 2` wrong, so the pointer bookkeeping needs a real trace
  of the interpreter rather than another guess.
- **Streetcode** — the tree itself folds (`_streetcode_tree` recurses on
  table halves, and a constant slice is a leaf).  Two things break: the
  hall that joins two subtrees is sized `height * 2` from `len(top)` and
  assumes both children are the same height, and a folded leaf arrives
  with CP short by the `=` each skipped hall would have spent, since the
  leaf prints from the loader loop's cell.  Compensating the CP inside the
  leaf widens it, and `_streetcode_combine` pads blocks to a common height
  but assumes a uniform width, so the collapsed tree then misaligns
  against the input loops beside it.  Wants the hall and the combine
  reworked together.
- **Decleq** — folds correctly with a one-line change, and gains 1.3%.
  Its size is dominated by fixed data cells and the read preamble rather
  than by the tree, so the saving is real but not worth the change on its
  own.

**Ruled out, with the reason.**

- **Clockwise** — its reads are *inside* the tree: `S` plus seven `.` down
  a column, nine rows per level.  A folded leaf still has to consume the
  inputs it skipped, at nine rows each, which is exactly what the
  branching cost.  The cancellation is arithmetic, not a layout artifact.
- **Forþ** — each level does two paired things: consumes an input bit
  through the dispatch arithmetic, and pops one definition index with
  `;`, which is the only way to pop and also dispatches.  The stack holds
  the definition indices, so a folded node leaves both a bit unread and an
  index unpopped and the next dispatch reads the wrong value.
- **Eval** — a node's code *is* its heap index: `~=~?` then `i + 1`
  semicolons.  Dropping a node renumbers every node after it.
- **6-5** — the `n <= 5` path is the non-folding tree, but above that the
  generator already delegates to `six_five_arithmetic`, which folds.

The generators that are not decision trees at all — the sum-of-minterms
group (bit~, Suptiftam, Suffolk, Collatz Multiverse, Qoibl, Point Break,
Circuit Diagram), Container's per-row enumeration, Taglate's table-as-data,
the arithmetic-index cascades (BFStack, COD, Minsky Swap, Home Row), A
Painter Ant's grid placement, and WII2D's searched op-chain — have no
constant subtree to fold and are not candidates.

## Severely constrained boolean generators (remove or lift)

Each boolean generator with a low cap is tracked here so the decision is
deliberate rather than implicit: either lift the cap (an open construction)
or, where the language has no other generator story, remove it.  The caps
are documented in `docs/limitations.md` and `docs/walls.md`.

**No language is currently on this list.**

## Evidence types through Streetcode's validators (deferred)

`_Machine._validate` proves five things about a grid in a fixed order —
width, enclosure, wall shape, glyph pairing, connectivity — and later code
relies on those proofs.  Two of the reliances are already typed: `_Halt`
keeps a deliberate stop apart from a wedged street, and `_ReachableCell`
gates `_block`'s unchecked three-by-three read behind the enclosure proof
(see the type comments in `streetcode.py`).

The unbuilt third step is to carry the whole pipeline in the types: a chain
of evidence classes, each minted only by the validator that proves it and
demanded by the next.

```python
class WalledGrid: ...      # >=1 wall character, >1 open cell
class TwoWide: ...         # + every reachable cell is two-wide
class Enclosed(TwoWide): ...   # + no reachable cell on the border
class WellFormed(Enclosed): ...  # + walls, glyphs, connectivity

def _flood(g: WalledGrid, start: tuple[int, int]) -> TwoWide | WallLess: ...
def _check_enclosed(w: TwoWide) -> Enclosed: ...
def _check_walls(e: Enclosed) -> WellFormed: ...
```

That would make the ordering a checked fact rather than a docstring, and
`_validate_width`'s `set | None` return would become two named outcomes —
the `None` arm being the wall-less grid whose `U` raises `HaltError`, which
is easy to overlook as "no cells" today.

**Deferred deliberately.**  The cost-benefit does not currently justify it:

- It removes two `pragma: no cover` lines in `_validate_walls`, and nothing
  else.  Both are already correctly pragma'd.
- The ordering it would enforce is set in one six-line method with a single
  call site.  The bug it prevents — calling `_check_walls` before the flood
  fill — is not one this code is positioned to commit.
- `NewType` and marker classes are erased at runtime, so this buys
  provenance under mypy, not a guarantee.  The runtime check would still
  have to live in the smart constructor and still have to raise.
- The validator docstrings currently explain *why* each invariant holds
  ("a wall that stops short leaves a one-wide stub, which the width check
  catches as a dead end").  A signature asserts the ordering but cannot
  carry that reasoning, so the rewrite trades explanation for enforcement
  across the most carefully reasoned prose in the module.

Worth revisiting only if the module is restructured for another reason, or
if a validator is added whose ordering is genuinely non-obvious.

### What types cannot reach here

Recorded so a future attempt does not over-promise: the value-dependent
halts — `_` at CP 0, `O` on a non-code-point cell, `I` at end of input —
are runtime semantics, not geometry.  No grid invariant touches them, and
`_probe` deliberately does not model them.  Likewise the `U`-without-a-lane
`HaltError` and `step`'s no-graph fallback are contract, not defensive
guards: the first is documented behaviour for wall-less grids, the second
is what lets the interpreter's own wall-shape fixtures disable `_validate`.
Any redesign has to keep both.
