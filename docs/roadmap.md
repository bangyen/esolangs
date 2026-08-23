# Roadmap

Planned work, in priority order.  Language assessments, documented walls,
and ruled-out ideas live in `docs/limitations.md`; completed ideas live in
the commit history.  This file only tracks what is still on the table.

## New interpreters (in priority order)

Candidates from re-scanning the esolangs wiki's Category:Unimplemented and
from User:PythonshellDebugwindow's language list.  What was ruled out
(Gravity, Earfuck, Conveyor, Chainlang, Binary ///, Fourfuck, Aaargh++,
Bitwise Cyclic Teast, and the languages already implemented elsewhere) is
in the commit history and `docs/limitations.md`.

Re-checking PythonshellDebugwindow's list against the admission criteria
surfaced a handful of languages worth recording as potential candidates.
The earlier draft of this section listed Jumplang, Eso2D, Minimal operation
language, brainfunc, and Yaren — all five are in fact wiki-categorized
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
would make the generator close to trivial to write by hand.

- **Streetcode** — a car drives on two-way, two-character-wide streets
  painted with instructions (`^`/`~` increment/decrement the current cell,
  `=`/`_` move the cell pointer, `I`/`O` char input/output, `U` U-turn, `;`
  halt).  At an ambiguous intersection the car takes the leftmost road if
  the current cell is zero, otherwise the second-leftmost — a direct
  Befunge-`_` analog, except the branch has to be built by laying out real
  street geometry rather than writing a condition.  Picked over the three
  below for having the cleanest, most complete spec (worked examples, a
  Turing-completeness proof) and a normal char-I/O model.  The interpreter
  and tests are done: initial heading, ordinary wall-hugging, genuine
  multi-way junction detection, and multi-cell-wide lane merging are all
  derived and confirmed against all four of the wiki's worked examples (two
  of which — the infinite loop and the larger infinite-cat example — turn
  out to contain genuine lane-bounded junctions themselves).  Landing after
  a junction turn onto a road with its own lanes drives to that road's
  right-hand lane before turning, rather than a plain single-cell step onto
  the first open neighbor (see the "Lane merging" bullet in
  `docs/streetcode.md`, and the same file for the hand-derived,
  user-confirmed trace this was built from).  Wired into `registry.py`,
  with a boolean generator
  (`tools/boolean/other.py`) that walks each input bit down to a bare 0/1
  and then drives a binary decision tree whose T-junctions apply the
  ambiguous-turn rule to fork on it; it takes arbitrary truth tables,
  uncapped, and is verified over every input combination up to 4 inputs.
  No text generator yet — that's the remaining follow-on work.
- **Flowchart** — literal flowchart nodes joined by lines; a `< >` switch
  node reads a bit register and routes the pointer left or right (straight
  through if the register is empty), directly analogous to Befunge's
  `_`/`|`.  Supports multiple concurrent pointers and deque-based memory;
  single-bit I/O.  Very new (2025) but the spec is complete, with a
  truth-machine, cat, and Kolakoski-sequence example.  The interpreter and
  tests are done: all sixteen nodes are tabulated by the wiki, so the work
  was the geometry (multi-character node tokenization, box-drawing line
  tracing) plus four spec gaps the page leaves implicit — the switch's
  left/right being relative to the pointer's heading (pinned by the truth
  machine), character-per-bit rather than Boolfuck byte-packed I/O (an
  eight-bit buffer would never flush for the truth machine), re-entry memory
  that disambiguates paths without suppressing node semantics (pinned by the
  cat's loops), and lock-step round-robin pointer interleaving in reading
  order.  Each is derived in the module docstring.  An empty register writes
  nothing rather than the spec sentence's zero, because the wiki's own cat
  would otherwise print a trailing bit it never read — an example-over-prose
  call worth revisiting if the author clarifies.  Wired into `registry.py`,
  with a boolean generator (`tools/boolean/other.py`) that draws the truth
  table as an actual decision tree: each level reads one bit with `/ /` and
  hands it to a `< >` switch whose sides are the halves of the table, and
  each of the `2**n` leaves sets the register to its digit, prints, and
  halts.  Uncapped, verified over every input combination up to 4 inputs.
  It is the cheapest of the repo's 2D boolean generators to build, because
  the language supplies a real conditional (no junction geometry to draw)
  and reads bare bits (no per-input decoding loop).

  **A text generator is impossible, and this is not a gap to close.**  The
  only output node emits one bit, and the byte-packing convention the other
  bit-output languages use (Clockwise buffers seven bits and flushes a
  character) cannot be applied here: the wiki's truth machine reads one
  bit, writes one bit, and halts, so under any packing its single output
  bit would never flush and the example would print nothing at all.
  Character-per-bit is therefore forced by the spec's own example, and it
  is what makes text output unreachable — so Flowchart belongs with the
  interpreter-only languages listed under deferred-removal, not on a list
  of languages awaiting a text generator.  That,
  and the Kolakoski example's exact output (the page states none, so the
  test pins current behaviour as characterization), are follow-on work.
  On that last point: the output's repeating tail was initially suspected
  to be an artifact of the unspecified pointer interleaving, but it is not.
  Creation order, reverse order, and per-step reading order all produce
  byte-identical output, and long consecutive runs per pointer only swap
  the first two bits.  Nor is it the two contested semantic calls: running
  the full matrix of {1 turns left, 1 turns right} x {empty register prints
  nothing, empty is zero} leaves Kolakoski period-4 in all four variants,
  and only the shipped combination (1 turns left, empty prints nothing)
  passes the truth machine and the cat at all — flipping the switch breaks
  the truth machine, and "empty is zero" breaks the cat, so the matrix
  independently re-derives both documented decisions.

  What actually happens is that the east pointer visits eleven nodes and
  halts: it emits a single `1` and reaches `(( ))`, so the repeating tail
  is entirely the south branch's.  The `( )` nodes mid-row are passed
  through as no-ops rather than forking, because the `─` run beneath them
  is the return rail *passing under* the row, not a path attached to them —
  the rail's two ends (`└` at column 29, `┘` at column 50) both turn
  upward, closing the loop at the switch and just past `(( ))`, and column
  50 of row 0 is blank.  The overlap is an artifact of drawing a long
  return path under a wide row of nodes, so declining to fork there is
  correct, and no re-entry or switch-routing change would alter it.
  The remaining possibility is that the diagram simply does not produce the
  Kolakoski sequence as drawn (the same never-executed caveat as the cat's
  trailing bit); confirming that would need the author, so the talk-page
  question is the cheapest next step.
- **Line** — implemented, in `extra/line/` (deliberately not wired into
  `registry.py`: the wiki spec is hand-drawn curve *images* with no text
  format, so its programs are PNGs, not files the registry's text pipeline
  can carry).  A cursor follows drawn curves and each curve shape it passes
  through is itself the instruction (a diagonal increments/decrements the
  current cell, a specific kink moves the tape pointer, a T-branch is a
  conditional turn keyed on the current cell being zero) -- brainfuck-
  equivalent semantics encoded entirely in path geometry.  What exists: a
  renderer whose kink shapes were measured pixel-by-pixel from the wiki's
  reference images, a pixel-based extractor and runtime simulator verified
  against the wiki's own hand-drawn fixtures, a direct boolean generator
  (`line_boolean.py`, every input combination through 3 inputs plus 5-input
  parity), and a brainfuck compiler (`bf_to_line.py`) whose loop-backs are
  constructed geometrically rather than route-searched, making nesting
  depth unbounded (round-tripped through depth 12).  See
  `extra/line/WIP.md` for the full implementation record.

- **Circuit Diagram** — an ASCII circuit: named logic gates (`a` AND, `A`
  NAND, `o` OR, `O` NOR, `x` XOR, `X` XNOR, `~` NOT) wired by `-`/`|`/`/`/`\`
  with `.` junctions and `=` crossovers, evaluated as a cellular automaton
  where a gate fires once both its left inputs are non-null.  Verified
  `Category:Two-dimensional languages` and `Category:Unimplemented` via the
  category API, with no external interpreter documented on the page.  Picked
  up after Gate fell through, and it is the stronger candidate on exactly the
  axis Gate failed: its sole worked example (a 4-bit prime tester) exercises
  every load-bearing symbol — input (`-4-`), output (`:`), gates, the `<`/`>`
  multi-wire splitter/combiner, and `=` crossovers — where Gate's `+` and `(`
  appeared in none of its nine.  The example is also a real acceptance test:
  its minterm formula was checked to be exactly the primes in 0-15 with `a`
  as the MSB, so an interpreter can be replayed over all 16 inputs, and since
  only that bit assignment yields primality the example pins its own input
  ordering.  Signals are three-valued (Null/0/1) with a defined multi-driver
  rule (a wiring driven by several non-null values takes their XOR), and the
  connection rules are stated symmetrically (`-|` and `.|` are explicitly
  *not* connections).  A boolean generator is the language's native idiom —
  a truth table becomes a sum-of-minterms gate network, which is what the
  example already is.

  Three judgment calls to derive and document before building, in the
  Flowchart style:

  - **Print cadence and halting are unspecified.**  Execution is
    generational and the spec's own flip-flop oscillates `1N1N1N...`
    forever, so "when does `:` print, and when does a program stop?" has no
    prose answer.  The prime tester's gates run left-to-right into the final
    `a` feeding `:`, and gates read left and write right, so a feed-forward
    circuit settles — making "run until stable, print each `:` once, halt"
    derivable from the example.  A circuit *with* feedback (the flip-flop)
    never settles under that rule and needs its own wording (cycle detection
    or the wall-clock backstop).
  - **`t` returns the current time** (a 32-bit seconds-since-2000 wire),
    which is time-dependent output — the same judgment-call class as seeded
    randomness: tests would fix the clock, and the generator would never
    emit `t`.
  - **Multi-wire is not optional.**  The only example uses `-4-`, `<`, and
    `>`, so an "implement the scalar subset first" staging is not available;
    the `?` splitter/combiner magic has to be built up front.  Its behavior
    is at least enumerated in prose, unlike Gate's image-only `<` table.

  The main risk is the single example: one diagram is the entire
  behavioral corpus, where Flowchart had three.  Its computational class is
  also listed as unknown (the page notes circuits are complete for
  fixed-arity boolean functions, which is not Turing-completeness).

Considered and rejected in the same pass: **Highways** (excellent
roundabout/routing mechanic, but junction direction, sign execution order,
and crash tie-breaking are genuinely random with no seed — fails the
determinism criterion); **Dilemma** (no I/O commands at all, pure
maze/DFS); **TableLang**, **Marz**, **RingCode**, **GridScript** (a
high-level `if`/`while`/`SWITCH` construct makes the generator trivial, or
the spec is unstable); and **Gate**, which was read closely and rejected on
spec-completeness.  Its lack of an input command is not the blocker — output,
constants, and a value-testable branch are exactly the parameterized
(input-by-substitution) profile that Back, RAM0, and Minsky Swap are built on.
The blocker is that the page never exercises the two commands such a generator
needs: `+` (the branch) appears in none of the nine worked examples, and no
example emits output at all, so neither the branch geometry nor the output
path can be derived the way Flowchart's gaps were pinned by its examples (see
the assessed-and-rejected ledger in `docs/limitations.md`).  **Circuit
Diagram**, the alternative named in that genre, was assessed after Gate fell
through and is a live candidate — see its entry above.

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
working, uncapped boolean generator (ABCDirection, Back, BF-PDA, Bitdeque,
Jaune, Lamfunc, Minsky Swap, RAM0, Grapheme, A Painter Ant, ArrowQueue,
Streetcode, Flowchart) are
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
| Rust | AddSubJump (branch-and-goto OISC), Collatz Multiverse (runtime odd/even rules), Polynomial (integer roots encoding a command stream), Dig (2D mole grid with runtime segment counts), Container (threshold-rule firing), ZTOALC L (Collatz-trajectory-driven execution), Factor (a giant integer whose prime factors re-encode a looped brainfuck program), Back (2D beam reflection routing), A Painter Ant (2D cycle-stable routing), ABCDirection (2D grid + Boolfuck input), Bitdeque (deque + register + goto).  Those that read input — and the 2D grid models — belong in Rust under the no-input RISC-V rule above. |

**Judgment call (borderline).**  The generator is stateful or looped, but
its output is a fixed pattern the round-trip already covers, so a cross-check
would add little: brainfuck, BFStack, BrainIf, Minifuck, Modulous, SLOW
ACV MAMMALIAN, WII2D, Home Row.  These stay without a cross-check unless a
specific bug motivates one.  Clockwise and 3D Brainfuck sit in the same
class: Clockwise's 2D routing is one fixed ring shape (only the ring size
and the parity pattern vary with the text), and 3D Brainfuck's generator is
the brainfuck generator's output with ``>``/``<`` renamed to ``n``/``s``.

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
(an `_EvalTask`-per-expression design, sketched and rejected in
`docs/walls.md`'s history) — materially more machinery than the
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
- **Recursion stays cycle-undetectable.**  A call that never returns
  pushes one new frame per `step()` and none is ever popped, so a
  `snapshot()`'s frame tuple strictly grows and two whole-machine
  snapshots can never compare equal — unbounded growth, the same class
  `+[>+]` already falls into.  A separate, narrower check — comparing a
  newly-pushed frame's own local state against ancestor frames already on
  the stack, rather than whole-machine snapshots across time — could catch
  the common case of a call whose local state repeats exactly relative to
  an ancestor (e.g. an accidental unconditional self-call), but not every
  infinite recursion, and it doesn't fit the existing `snapshot()`
  protocol; not built, revisit only if a concrete program needs it.  See
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
  handles both languages correctly, so this is only worth building if a
  specific need for the "always hangs" guarantee comes up.

## Severely constrained boolean generators (remove or lift)

Each boolean generator with a low cap is tracked here so the decision is
deliberate rather than implicit: either lift the cap (an open construction)
or, where the language has no other generator story, remove it.  The caps
are documented in `docs/limitations.md` and `docs/walls.md`.

**No language is currently on this list.**

## Boolean example coverage (ABCDirection only)

`examples/boolean` holds one committed program per boolean generator that
can be verified end to end; `src/esolangs/tools/boolean/examples.py` is the
source of truth and `tests/test_examples.py` keeps the files in sync.
Coverage is 53 of 54 generators.  The bar is that the answer must be
*recoverable from what the program prints* -- not that the program prints
the answer and nothing else, since several of these languages have no output
instruction at all and dump their state at halt.

Every generator whose answer a program can report now has an example.  The
two that used to fall short were fixed rather than excluded, and both are
worked examples of what this section asks for:

- **Back**'s answer was the cell under the tape head, which the dump does
  not locate.  The generator now keeps a single answer cell that a 1-leaf
  writes with `-` before halting, so the dump reports the result directly.
  The payoff was larger than the example: the Back boolean tests had carried
  a complete second Back interpreter (32 lines) purely to find the head, so
  they never executed `tape_based.back`; that shadow implementation is now a
  call plus a field read.
- **A Painter Ant**'s answer is which of two painted leaf rings the ant
  rests in, and the raster drew painted cells only, so the ant was invisible
  and the rings identical.  `render` now uses four glyphs -- colour by
  ant-present -- with `o` for the ant on black and `@` on white.  The same
  change replaced `run`'s instruction `limit` with a `cycles` count: the
  language is an implicit infinite loop, and a raw step budget stops
  wherever it lands (the old default of 10,000 cut the AND2 program at 95.24
  cycles, mid-walk, reading a colour that is not the answer).  A whole cycle
  is the language's own unit, and these programs are cycle-stable fixed
  points, so one pass is enough.  This is a unit, not a safety limit -- a
  diverging program still runs as long as it is asked to.

ABCDirection is the one generator left, and not for that reason: its program
is a 1107-line, 377 KB grid needing several million steps, which is too slow
for the example suite and too large to review.  Making it committable means
making the *program* smaller, which is a generator-construction problem
rather than an output-recoverability one.

One caution for anyone re-surveying this: the example stems are display
names, not language ids, so a naive `id not in stems` check reports
BF-PDA as missing when it is filed under `bfpda`.  It has an example.

### Divergent expected outputs

Some committed examples expect something other than a bare `0`/`1`.  Several
that used to be on this list were cleaned up rather than explained away:

- **LaserFuck** printed `'\x00\x010'` -- the answer as a *character*, with
  the two input cells ahead of it.  Its dump has a decimal mode, selected
  simply by not putting a `\xff` in the first grid cell, and it skips cells
  holding a negative value.  So the leaves now write the answer as a number
  (one `+`, not `48 + result`) and subtract one more than each bit's value
  from the input cells on the way past, driving them out of the dump.  The
  output is exactly `"0"` or `"1"`, and the programs shrank by a third,
  since the 48-`+` runs were most of them.
- **Clockwise** printed `'\x00'`/`'\x7f'` -- the result bit seven times.  A
  leaf's seven `;` each print `acc % 2`, so emitting the ASCII digit instead
  is a matter of flipping the parity into the bits `0110000`/`0110001`,
  which differ by a single `+`.  The two leaves are padded to the same
  height (an `S` on an already-zero accumulator is a no-op) so every exit
  still lands on the shared bottom row.
- **Trailing newlines** (`bitdeque`, `cod`, `nevermind`) are gone.  None of
  the three specs asks for one -- Bitdeque's says "There is (currently) no
  I/O" at all, COD's says only "output the cod's value", and Nevermind's
  only "Outputs *text* to the screen", with a Hello-World example showing
  none -- so the newline was our interpreters' choice throughout.

  An earlier pass kept COD's and Nevermind's on the grounds that their print
  can fire repeatedly, so the newline was separating outputs, and without it
  `loop,3 / print,x / endloop` prints `xxx` just as `print,xxx` does.  That
  reasoning does not survive contact with the equivalent Python: a loop of
  `print("x", end="")` also produces `xxx`.  Programs are not obliged to be
  recoverable from their output, and treating that as a loss was reading a
  guarantee into a default.  All three now print without a separator.

What is left is divergent for reasons no *generator* change reaches:

- **state dump around the answer** (`back`, `minsky-swap`, `ram0`) -- no
  output instruction, so the answer arrives at a fixed position inside a
  dump of the machine.  Unlike LaserFuck, these have no way to suppress the
  rest: Back's cells are bits, and the register dumps print unconditionally;
- **a painted grid** (`a-painter-ant`) -- the grid *is* the output, and the
  answer is which leaf the ant rests in;
- **no output at all** (`arrowqueue`, `point-break`) -- the answer *is*
  termination: the program halts for a 0 and loops forever for a 1, so only
  the halting branch can be committed.

The notes on each example carry the explanation.
