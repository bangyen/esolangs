# Roadmap

Planned work, in priority order.  Language assessments, documented walls,
and ruled-out ideas live in `docs/limitations.md`; completed ideas live in
the commit history.  This file only tracks what is still on the table.

## New interpreters (in priority order)

Candidates from re-scanning the esolangs wiki's Category:Unimplemented and
from User:PythonshellDebugwindow's language list.  The original scan is
exhausted: every candidate with a usable file-based I/O protocol, a complete
specification, and a plausible generator or boolean story now has an
interpreter.  What shipped and what was ruled out (Gravity, Earfuck,
Conveyor, Chainlang, Binary ///, Fourfuck, Aaargh++, Bitwise Cyclic Teast,
and the languages already implemented elsewhere) is in the commit history and
`docs/limitations.md`.

| Language | Priority | Why it is on the table |
| --- | --- | --- |
| Suptiftam | low | 2D tape-tapes; complete spec but undefined behaviors. |
| COD | low | 2D concurrency-heavy cods; numeric output + value gates make a boolean generator plausible but unbuilt. |

**Point Break shipped with the first termination-convention generator.**
Point Break has no output, so it would have inherited the no-output tier
below — but the wiki's own truth-machine (halt for 0, loop for 1) is the
*termination convention* the boolean tooling had never used, and the
language's Turing-complete arithmetic makes that convention a fully general
boolean generator (any arity, any table), not the structural ceiling the
convention hits elsewhere.  The interpreter and generator shipped; see
`docs/walls.md`.

**Suptiftam, COD — the only candidates left.**  The other four candidates
were assessed and ruled out; the assessments are in `docs/limitations.md`.
Procedure is deferred on its arithmetic spec gap (only `the sum of ...`
is defined, so a faithful interpreter cannot implement the rest without
inventing semantics); State and Main, Your Time Is Up, and Crement have no
I/O and no plausible generator (State and Main's single `main` argument
cannot express an arbitrary boolean function, Your Time Is Up's rule
choice is random, and Crement has no standard I/O at all).  Suptiftam's
spec is complete but has undefined behaviors and untested examples.  COD's
only output is numbers, so it can never have a text generator — but a
single 0/1 printed as the cod's value is a valid boolean output, so a
boolean generator is the live question: it would route one cod through the
`_` (reflect iff nonzero) and `<` (remove iff zero) value gates into a
decision tree, laid out branch-free so the cod never hits a random
junction.  That is a heavy, unbuilt 2D construction, and the interpreter
needs a seeded-randomness decision first (the LaserFuck precedent), so COD
stays low-priority and risky rather than ruled out.

## Transpilers

A direct transpile between languages with no shared core is not a rewrite —
it needs a full runtime of one inside the other.  The transpilers that
shipped (the brainfuck family, `Decleq → S*bleq`, Dimensional → LaserFuck,
and the dropped silent-dropper/round-trip-only ones) are in the commit
history; the walls are in `docs/limitations.md`.  The candidates still on
the table:

- **Forth-family ↔ Forþ.**  Forþ is Forth-like (single-char stack,
  arithmetic, ``(``/``[`` loops, ``;`` calls); adding a second Forth dialect
  (e.g. plain Forth) would share the stack+arithmetic+loop core and
  transpile directly.
- **Boolfuck ↔ ABCDrection / Minifuck.**  A Boolfuck (bit tape, little-endian
  byte I/O) shares ABCDrection's bit-tape model; Minifuck's
  flip-and-conditional-skip is further away.

## Deferred-removal candidates

**Deferred — not yet removed.**  One language has no usable text or
boolean generator — either none at all, or one so severely constrained it is
effectively absent for any non-trivial use — so it cannot be round-trip or
differentially verified and is the weakest kind of addition.

| Language | Output | Why it is on the list |
| --- | --- | --- |
| ArrowQueue | None (no I/O) | no text or boolean generator; only the halt-vs-hang convention (AND/OR-class, see `docs/walls.md`). |

Movesum and Lightlang were removed (see `docs/limitations.md`): both had
real language-defined output (numbers, and a single bit, respectively),
but Movesum has no conditional at all and Lightlang's boolean capability
caps at the AND/OR class, so neither had a generator beyond what the
output convention alone provides.  Grapheme has since been taken **off** this
list: its boolean wall was not a hard limit — the language is Turing-complete
with arithmetic and conditionals — and a working boolean generator now
exists (see the constrained-generators section below), so like the other
interpreter-only languages it is no longer a removal candidate even though
it still has no text generator.  A Painter Ant has likewise come **off** this
list: a working two-input boolean generator now exists (see the
constrained-generators section below), so like the other interpreter-only
languages it is no longer a removal candidate even though it still has no
text generator.  No
text generator is severely constrained — even the most restricted ones
(Dig's letter/digit/``.,!?`` alphabet, MyScript's printable ASCII) still
cover a substantial output range, so no language is added on the text side.
The other interpreter-only languages
(ABCDirection, Back, BF-PDA, Bitdeque, Jaune, Lamfunc,
Minsky Swap, RAM0, Grapheme, A Painter Ant) all have a working boolean
generator with no
severe cap,
so they are **not**
deferred-removal candidates; their only weakness is an interpreter-invented
state dump where the wiki defines no text output.

**Dropped.**  The planned no-output candidates (State and Main, Crement,
Your Time Is Up) were dropped and recorded in `docs/limitations.md`.

**Against removal (weighed, not decisive).**  Most of these are the *only*
implementation on the wiki (only this repo's interpreter is listed), so
removing them leaves the language with no implementation at all — which the
admission criteria treat as a genuine gap.  ArrowQueue is
a Bangyen-only sole implementation
with no external implementations and is
Turing-complete (ArrowQueue via Tag/Cyclic tag/Minsky machine translations,
on the wiki).  (Kak
and Brainpocalypse, the two externally-implemented members, Stun Step —
a sole implementation removed anyway, see `docs/limitations.md` — and
Movesum and Lightlang were
removed.)  The tradeoff is
between "no generator ⇒ cannot participate in the repo's verification
machinery" and "sole implementation ⇒ removing creates a gap"; the removal
is recorded here as a candidate to resolve deliberately rather than by
default.

**Redemption path (termination-convention generator).**  ArrowQueue has no
output, so its only boolean option is the termination-based convention
(documented in `docs/walls.md`): the program *hangs* iff the embedded inputs
satisfy the function.  The hang structure is a queue-sustaining ring that
survives iff its single sustainer cell is present, so each input adds a
"must be present" literal and one ring is one AND of literals; the OR and
NOR tables are expressible in other layouts (verified by search), but
multiple rings cannot be OR'd on the IP's single path, so XOR/XNOR are not —
the convention realizes the threshold/AND/OR-class, not arbitrary tables.

This is the only path that could take ArrowQueue off this list.  It would
still be a *permanently* constrained generator: unlike A Painter Ant's
n == 2 cap — which is not a language limit but an open construction
(generalizing the generator to higher arities is the active roadmap work,
see the A Painter Ant section below) — ArrowQueue's threshold ceiling is
supported only by a structural argument and a bounded 200,000-grid search
(see `docs/walls.md`), not a proof, so it may be a genuine wall or just an
undiscovered construction.  Adopting the convention
is also a real harness lift: the boolean tooling and tests read output
bytes, while the termination convention makes "does it halt?" the answer.
Point Break has since established that contract (verified by deterministic
state-cycle detection, see the hang-detection section below), but ArrowQueue would still
be stuck at the threshold class where Point Break expresses arbitrary
tables.  Recorded here so the
removal-vs-redemption call is deliberate rather than by default.

## Extra implementations (cross-checks)

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

- **Stay (complex-output generators, fuzzed):** NoComment, Forþ, Basicfuck,
  Unsquare, 3x, %^2^-1, 2dFish, Painfuck, bit~, LaserFuck.
- **No cross-check (straight-line generators):** 6-5, Albabet, Decleq,
  Dimensional, huf, Qoibl, and the rest.

**Toolchain follows the model.**  RISC-V assembly fits the machine-model
languages (a tape/pointer/instruction-counter maps 1:1 onto cells,
registers, and jumps); Rust fits the semantic ones (stacks, typed registers,
bit manipulation, 2D grids, where hand-written assembly would be unreadable).

| Toolchain | Languages |
| --- | --- |
| RISC-V assembly | NoComment (tape + stack with a byte-indexed skip). |
| Rust | Forþ, Basicfuck, Unsquare, 3x, 2dFish, Painfuck, LaserFuck (stacks, typed registers, 2D grids); %^2^-1 and bit~ keep corpus cross-checks but lost their straight-line text-generator fuzzes. |

**Worth adding (audited).**  These languages have complex-output generators
(arithmetic encodings, branch-and-goto OISCs, runtime state carried across
characters) that a random differential fuzz would exercise beyond the
round-trip corpus, so a cross-check would add real verification.

| Toolchain | Languages |
| --- | --- |
| RISC-V assembly | 3D Brainfuck (tape + loops), Factor (a giant integer whose prime factors re-encode a looped brainfuck program). |
| Rust | AddSubJump (branch-and-goto OISC), BIO (register counter loops), Collatz Multiverse (runtime odd/even rules), Polynomial (integer roots encoding a command stream), Clockwise (2D ring routing), Dig (2D mole grid with runtime segment counts), Container (threshold-rule firing), ZTOALC L (Collatz-trajectory-driven execution). |

**Judgment call (borderline).**  The generator is stateful or looped, but
its output is a fixed pattern the round-trip already covers, so a cross-check
would add little: brainfuck, BFStack, BrainIf, Minifuck, Modulous, SLOW
ACV MAMMALIAN, WII2D, Home Row.  These stay without a cross-check unless a
specific bug motivates one.

**Removed (did not meet the criterion).**  The seven cross-checks that were
removed — Kak, Trash, Number Seventy-Four (Rust) and Brainpocalypse, Stun
Step, 2 Bits 1 Byte (RISC-V) had no generator at all, so their differentials
were a hand-written 4-6 program corpus each, and the references were ports
of (or ported to) the Python, so agreement was not independent evidence.
123 had a generator but its RISC-V cross-check was corpus-only (4 generated
texts + 2 hand-written jumps, no fuzz) and verified programs the round-trip
test already covers.  All seven added little over the Python unit tests at
real toolchain cost (cargo + RISC-V cross-compiler + unicorn in CI); the
*languages* all stayed (they have generators or pass the admission criteria
as distinct interpreters); only the redundant cross-checks went.  The 2
Bits 1 Byte, Trash, Number Seventy-Four, Kak, Brainpocalypse, and Stun Step
interpreters were
themselves removed later (see `docs/limitations.md`), on top of their
already-removed cross-checks.

## VM / debugging interface (remaining work)

`esolangs.make_vm` (step-and-inspect wrappers for twelve interpreters:
brainfuck, S*bleq, Dimensional, Grapheme, Qoibl, Eval, Modulous, The
Temporary Stack, LaserFuck, Point Break, ArrowQueue, 123) and
`esolangs.make_debugger` (breakpoints and watches over the VM) shipped.
The medium-priority work that remains:

- **More step-capable interpreters.**  Convert more of the registry to a
  step()/halted state object, growing the VM set per state model.  Point
  Break, ArrowQueue, and 123 joined the set with the cycle-detection work
  below; the
  other grid languages (2dFish, Dotlang, A Painter Ant, ...) are the
  natural next batch: their position/direction is the ``ip``, as LaserFuck
  demonstrated.
- **A richer ``ip`` for the recursive languages.**  Grapheme's ``ip`` is
  currently the active call frame's cursor; a language with nested calls
  should expose the call stack, not fold it into one frame's position.

## Hanging-test optimization via state-cycle detection

Hanging programs are currently bounded with wall-clock timeouts (SIGALRM in
the robustness tests and on the differential fuzzer's Python side, and
instruction-count caps on the native references).  A deterministic,
step-capable machine that revisits an exact internal state has looped
forever, so a repeated state is a *proof* of a hang that can be reported
immediately instead of waiting out the timeout.

Scope and constraints:

- the snapshot must be the **complete** state — the machine's internal
  fields, not the VM's language-shaped ``ip``/``memory``/``stack`` view —
  including the input-cursor position, or a "repeat" is not a real cycle;
- deterministic machines only (LaserFuck's random heading is excluded);
- only interpreters with a ``step()``/``halted`` state object can be checked
  (the VM set; whole-program ``run()``s expose no internal state to hash);
- it catches *cycles*, not every hang — an unbounded-growth loop
  (``+[>+]``, the tape grows forever) never revisits a state, so the
  timeout stays as the backstop for that class.

Started for Point Break, ArrowQueue, 123, and brainfuck.
``esolangs.vm.run_until_halt_or_cycle`` — a shared step-and-hash helper (a
visited-state ``set``; Floyd/Brent two-pointer detection for O(1) memory
would be the follow-up) — steps a step-capable machine and returns
``False`` the moment a repeated snapshot proves it is looping, and
``True`` as soon as a step halts.  The four interpreters were made
step-capable (a ``_Machine`` state object each, with ``snapshot()``
including the input cursor) and every hand-written hang test in the suite
now decides the looping side deterministically — no wall-clock bound, no
subprocess, and no coverage-tracer exposure at all.

**Design rule: hand-written hang tests always use loops that revisit
state.**  Since the test chooses the program, it can pick a finite-state
cycle, and cycle detection is then complete (not just sound) for that
test.  ArrowQueue's sustaining truth-machine ring is a 12-state cycle,
123's state is bounded so every loop is a cycle, and brainfuck's ``+[]``
wraps its cell.  The "catches cycles, not every hang" caveat — e.g. an
unbounded-growth ``+[>+]`` whose tape grows forever — only bites when the
suite does *not* control the programs, i.e. the fuzzers, so the timeout
backstop stays there and is not a hazard for the hand-written tests.

Slots that remain to wire in: ``scripts/verify_differential.py``'s
termination checks and ``tests/test_interpreters_robustness.py``, which
still run whole-program ``run()``s for languages that are not yet
step-capable (see the step-capable-interpreters item in the VM section
above).

**Why the wall-clock backstop is also broken under ``pytest --cov``.**
Raising from the SIGALRM handler while the coverage C tracer is active can
deadlock the tracer: the exception unwinds through the tracer's C code
while it holds its internal lock, so the *next* traced run spins forever
instead of finishing.  An interpreter that evaluates a ``next(genexpr)`` in
its hot loop makes it near-deterministic — the signal lands inside the
suspended generator frame and leaves the lock held — while a genexpr-free
loop reduces it to a rare race (Point Break's ``test_interpreters/
test_point_break.py`` hung ~every run with a genexpr in the loop and ~1 in
12 without; brainfuck's ``+[]`` timeout test is stable only because it
raises once per process).  Point Break's loop side was at first verified
in untraced subprocesses, where the raise is safe; the cycle detector
replaced that entirely, and it is the reason the remaining hangs can rely
on the timeout backstop without the coverage-tracer deadlock becoming a
test-suite hazard again.  The one alarm that stays by design is
``test_api.py``'s ``+[]`` case: it is a feature test of ``esolangs.run``'s
``timeout`` parameter (the backstop for unbounded-growth loops), not a
hang-detection strategy, so it keeps raising from the handler once per
process.

## A Painter Ant: general n-input boolean generator (n >= 3 open)

A two-input boolean generator now ships
(:func:`esolangs.tools.boolean.parameterized.a_painter_ant`): it paints one leaf per
input combination (``P`` for a one table entry, a space — left unpainted —
for a zero, so only monotone ``P`` is ever used) and routes the ant to its
leaf.  The body paints a two-layer star around the output leaf and its
y-mirror, and on cycle 2 the ant dances on the pre-painted stars (the
"top-middle/middle-left ring rule": a leafward move would split the ants,
so only an ``S/s``-style dual may move leafward), making every instantiated
program a cycle-stable fixed point, read by a semantic grid model as the
**landing cell's colour** (the interpreter's own output is the
visited-cell bounding box, which carries no coordinates).  ``n == 1`` is
also supported, with a two-leaf head and the same star body.  This
construction resolved the ``n == 2`` case that the earlier, origin-colour
generator covered; the full construction is recorded in
`docs/a_painter_ant_generator.md`.

**n >= 3 is open.**  No construction is known that expresses *all* functions
of an arity; a leaf-paint n == 3 generalization is the active work (below).

A **leaf-paint n == 3 generalization is in progress** (see
`docs/a_painter_ant_generator.md`): a single-row eight-leaf construction is
exact for cycle 1 on all 256 tables but is not yet cycle-stable.  The
remaining blocker is now characterized precisely: the ant must land on the
output leaf for *both* output colours (a colour-dependent landing gives
the head two cycle-2 starts and no single dance works from both), which
forces a mixed-case closing walk that must run from a ring cell rather
than the leaf; the body walk that paints the lower ring cells then needs
``s`` moves that, evaluated from the N ring on cycle 2, fire a one-output
onto the leaf too early.  A step tracer and stability checker
(`esolangs.tools.boolean.a_painter_ant_trace`) ships and pinpoints the
first diverging instruction, and a complete 8-leaf head dance is designed
(see the doc).  Cycle-1 exactness was the easy part; extending the
star/ring dance to the n == 3 layout is the open work.

**Goal: find a general construction such that for any ``n``, *every*
``n``-ary boolean function is expressible.**  A general solution needs to
route on *which* inputs are one, not merely how many — e.g. a way to encode
each of the ``2**n`` combos into a distinguishable ant state (position,
painted pattern, or box content) with a cycle-stable template.  This is the
documented wall in `docs/walls.md`; a successful construction would lift the
cap.

## Severely constrained boolean generators (remove or lift)

Each boolean generator with a low cap is tracked here so the decision is
deliberate rather than implicit: either lift the cap (an open construction)
or, where the language has no other generator story, remove it.  The caps
are documented in `docs/limitations.md` and `docs/walls.md`.

| Language | Boolean cap | Also has text generator? | Resolution |
| --- | --- | --- | --- |
| 123 | one input only | yes | lift (structural wall, single data byte); has a text generator so not a removal candidate. |
| NoComment | `n <= 8` | yes | lift (genuine wall, byte-indexed skip); cap is high enough for practical use. |
| Polynomial | `n <= 4` | yes | lift (performance cap on exact factorization); cap is high enough for practical use. |
| A Painter Ant | `n == 2` | no | lift (open at `n >= 3`); the two-input leaf-paint construction is exact and cycle-stable, a leaf-paint n == 3 generalization is in progress, and no general method for all functions of an arity is known yet (see the open-problem section above). |

Removed (constraints made them trivial): the boolean generators for
Minifuck (`n <= 3`, only
0-preserving two-input tables), and Home Row (`n <= 2`) were dropped because
their low caps left them only able to express the four one-input and a small
fraction of the two-input boolean functions — too small a subset to be
interesting.  Their languages and text generators remain.

Borderline, kept for now: **ZTOALC L** raises for dense, non-symmetric
tables past `n == 3` but still covers symmetric and structured tables at
`n == 4`, so it is a candidate to revisit if a general construction or a
decision to drop it lands.

Resolved: **Grapheme's** boolean "wall" was a stale note from an incomplete
decision-tree construction, not a hard limit.  A total generator
(`esolangs.tools.boolean.stack.grapheme`) now evaluates the table as an
arithmetic sum of minterms (`A`/`B`/`S`/`T`, no jumps), reading each input
from a two-character alphabet, and Grapheme has come off the
deferred-removal list.
