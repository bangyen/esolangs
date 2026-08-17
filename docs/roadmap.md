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

**Deferred — not yet removed.**  Five languages have no usable text or
boolean generator — either none at all, or one so severely constrained it is
effectively absent for any non-trivial use — so they cannot be round-trip or
differentially verified and are the weakest additions.  They are grouped
together regardless of I/O; the presence of usable I/O is an argument
*against* removal, so the no-output ArrowQueue is the strongest candidate
and the I/O-capable Grapheme, Lightlang, and Movesum are weaker ones.

| Language | Output | Why it is on the list |
| --- | --- | --- |
| ArrowQueue | None (no I/O) | no text or boolean generator; only the halt-vs-hang convention (AND/OR-class, see `docs/walls.md`). |
| A Painter Ant | No I/O; visited-grid bounding box (`#`/`.` raster) | no text generator; boolean generator was removed as trivial (`n <= 2`), so no boolean generator at all. |
| Grapheme | I/O-capable, but text is unspellable (no `E`, no concatenation) | no text generator; boolean wall. |
| Lightlang | Prints only the single bit as a number | no text generator; boolean wall (AND/OR-class only). |
| Movesum | Prints numbers space-separated with no trailing space | no text generator; no conditional, so no boolean generator. |

The I/O-capable members (Grapheme, Lightlang, Movesum) were previously
excluded from this tier as "I/O-capable" — they stay on the list because
they still fail both generator gates, but their real language-defined output
counts against removing them.  A Painter Ant was here because its boolean
generator only covered one- and two-input tables (`n <= 2`); that generator
has since been **removed** as trivial (see the constrained-generators
section below), so A Painter Ant now has no generator at all — it sits in
the same fully-generator-less tier as ArrowQueue.  No
text generator is severely constrained — even the most restricted ones
(Dig's letter/digit/``.,!?`` alphabet, MyScript's printable ASCII) still
cover a substantial output range, so no language is added on the text side.
The other interpreter-only languages
(ABCDirection, Back, BF-PDA, Bitdeque, Jaune, Lamfunc,
Minsky Swap, RAM0) all have a working boolean generator with no severe cap,
so they are **not**
deferred-removal candidates; their only weakness is an interpreter-invented
state dump where the wiki defines no text output.

**Candidate to add, once decided.**  The roadmap's planned no-output
candidates (Point Break, State and Main, Crement, Your Time Is Up) would be
dropped under the same policy.

**Against removal (weighed, not decisive).**  Most of these are the *only*
implementation on the wiki (only this repo's interpreter is listed), so
removing them leaves the language with no implementation at all — which the
admission criteria treat as a genuine gap.  ArrowQueue, A Painter Ant,
Grapheme, Lightlang, and Movesum are all Bangyen-only sole implementations
with no external implementations.  ArrowQueue and A Painter Ant are each
Turing-complete (ArrowQueue via Tag/Cyclic tag/Minsky machine translations;
A Painter Ant via a compiled Exasperation Machine, both on the wiki).  (Kak
and Brainpocalypse, the two externally-implemented members, and Stun Step —
a sole implementation removed anyway, see `docs/limitations.md` — were
removed.)  The tradeoff is
between "no generator ⇒ cannot participate in the repo's verification
machinery" and "sole implementation ⇒ removing creates a gap"; the removal
is recorded here as a candidate to resolve deliberately rather than by
default.

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

## A Painter Ant: general n-input boolean generator (open)

The A Painter Ant boolean generator was removed (see the constrained-
generators section below) because it was capped at `n <= 2`.  This open
problem records what a *general* construction would need, should it be
re-added.

The removed generator expressed every one- and two-input truth table exactly
(answer = the origin's colour after a whole cycle, all templates
cycle-stable), and raised for `n >= 3`.

The cap is not "unreachable": a search-found *box-height* method extends
the range — each one-input makes the ant step one cell further north, so
its depth equals the input weight, and a paint/return section turns that
depth into a box height or its parity.  This is cycle-stable and expresses
**most** n == 3 tables (196 of 256 in a search, including AND3, OR3, XOR3
via parity, and majority); the ~60 unreachable ones are exactly the
balanced, non-monotone tables (e.g. equality).

**Goal: find a general construction such that for any ``n``, *every*
``n``-ary boolean function is expressible.**  The box-height method loses
the "which inputs" information (it only measures the weight), so it cannot
reach the balanced tables; a general solution needs to route on *which*
inputs are one, not just *how many* — e.g. a way to encode each of the
``2**n`` combos into a distinguishable ant state (position, painted pattern,
or box content) with a cycle-stable template.  This is the documented wall
in `docs/walls.md`; a successful construction would warrant re-adding the
generator.

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

Removed (constraints made them trivial): the boolean generators for A
Painter Ant (`n <= 2`, no text generator), Minifuck (`n <= 3`, only
0-preserving two-input tables), and Home Row (`n <= 2`) were dropped because
their low caps left them only able to express the four one-input and a small
fraction of the two-input boolean functions — too small a subset to be
interesting.  Their languages and text generators remain.

Borderline, kept for now: **ZTOALC L** raises for dense, non-symmetric
tables past `n == 3` but still covers symmetric and structured tables at
`n == 4`, so it is a candidate to revisit if a general construction or a
decision to drop it lands.
