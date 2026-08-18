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
| Procedure | medium | Turing-complete pseudonatural English; deferred on a spec gap (see below). |
| Point Break | low | Four commands simulating Minsky machines; no output at all. |
| State and Main | low | `main` + numbered states; truth-machine is explicitly "No output". |
| Your Time Is Up | low | Binary string-rewriting; random rule choice, no I/O. |
| COD | low | 2D concurrency-heavy cods; random branches; has I/O. |
| Suptiftam | low | 2D tape-tapes; complete spec but undefined behaviors. |
| Crement | low | Self-modifying ADDRESS/DATA/JUMP; no I/O. |

**Procedure — deferred on a spec gap.**  The only arithmetic operator the
wiki defines is `the sum of ...` (in the ``addthree`` example); there is no
documented subtraction, multiplication, or division.  A faithful interpreter
cannot implement the comparisons and GOTOs that make it Turing-complete
without inventing arithmetic semantics the spec never gives, and the English
parser is heavy enough that the arithmetic question should be settled before
that work starts.  Revisit if the wiki (or its successor Pure) defines the
rest of the operator set.

**Point Break, State and Main, Your Time Is Up, Crement — no-output tier.**
None have I/O, so they can only be self-contained interpreters without a
generator; they would inherit the deferred-removal policy below (no text or
boolean generator, with the absence of I/O strengthening the case).

**COD, Suptiftam — heavier, riskier.**  COD's random branches (like
LaserFuck) make output non-deterministic but the interpreter can still be
faithful to the spec.  Suptiftam's spec is complete but has undefined
behaviors and untested examples.

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

**Deferred — not yet removed.**  Three languages have no usable text or
boolean generator — either none at all, or one so severely constrained it is
effectively absent for any non-trivial use — so they cannot be round-trip or
differentially verified and are the weakest additions.  They are grouped
together regardless of I/O; the presence of usable I/O is an argument
*against* removal, so the no-output ArrowQueue is the strongest candidate
and the I/O-capable Lightlang and Movesum are weaker ones.

| Language | Output | Why it is on the list |
| --- | --- | --- |
| ArrowQueue | None (no I/O) | no text or boolean generator; only the halt-vs-hang convention (AND/OR-class, see `docs/walls.md`). |
| Lightlang | Prints only the single bit as a number | no text generator; boolean wall (AND/OR-class only). |
| Movesum | Prints numbers space-separated with no trailing space | no text generator; no conditional, so no boolean generator. |

The I/O-capable members (Lightlang, Movesum) were previously
excluded from this tier as "I/O-capable" — they stay on the list because
they still fail both generator gates, but their real language-defined output
counts against removing them.  Grapheme has since been taken **off** this
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

**Candidate to add, once decided.**  The roadmap's planned no-output
candidates (Point Break, State and Main, Crement, Your Time Is Up) would be
dropped under the same policy.

**Against removal (weighed, not decisive).**  Most of these are the *only*
implementation on the wiki (only this repo's interpreter is listed), so
removing them leaves the language with no implementation at all — which the
admission criteria treat as a genuine gap.  ArrowQueue, Lightlang, and
Movesum are all Bangyen-only sole implementations
with no external implementations.  ArrowQueue is
Turing-complete (ArrowQueue via Tag/Cyclic tag/Minsky machine translations,
on the wiki).  (Kak
and Brainpocalypse, the two externally-implemented members, and Stun Step —
a sole implementation removed anyway, see `docs/limitations.md` — were
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
bytes, while the termination convention makes "does it halt?" the answer,
and no generator uses that contract yet.  Recorded here so the
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

`esolangs.make_vm` (step-and-inspect wrappers for nine interpreters:
brainfuck, S*bleq, Dimensional, Grapheme, Qoibl, Eval, Modulous, The
Temporary Stack, LaserFuck) and `esolangs.make_debugger` (breakpoints and
watches over the VM) shipped.  The medium-priority work that remains:

- **More step-capable interpreters.**  Convert more of the registry to a
  step()/halted state object, growing the VM set per state model.  The
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
- deterministic machines only (LaserFuck's random heading and Lightlang's
  ``@`` are excluded);
- only interpreters with a ``step()``/``halted`` state object can be checked
  (the VM set; whole-program ``run()``s expose no internal state to hash);
- it catches *cycles*, not every hang — an unbounded-growth loop
  (``+[>+]``, the tape grows forever) never revisits a state, so the
  timeout stays as the backstop for that class.

Not started.  A shared step-and-hash helper (a visited-state ``set``, or
Floyd/Brent two-pointer detection for O(1) memory) would slot into
``scripts/verify_differential.py``'s termination checks and
``tests/test_interpreters_robustness.py``.

## A Painter Ant: general n-input boolean generator (n >= 3 open)

A two-input boolean generator now ships
(:func:`esolangs.tools.booleans.parameterized.a_painter_ant`): it paints one leaf per
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
`docs/a_painter_ant_generator.md`): a two-row eight-leaf construction is
exact for cycle 1 on all 256 tables but is not yet cycle-stable (the head
is origin-relative and the ant starts cycle 2 at the output leaf).  Cycle-1
exactness was the easy part; extending the star/ring dance to the n == 3
layout is the open work.

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
(`esolangs.tools.booleans.stack.grapheme`) now evaluates the table as an
arithmetic sum of minterms (`A`/`B`/`S`/`T`, no jumps), reading each input
from a two-character alphabet, and Grapheme has come off the
deferred-removal list.
