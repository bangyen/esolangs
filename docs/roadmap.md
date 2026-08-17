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
None have I/O, so like Crement and A Painter Ant they can only be
self-contained interpreters without a generator; they would inherit the
no-output removal policy below.

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

## No-output interpreters (deferred removal)

**Deferred — not yet removed.**  Eight interpreters are for languages whose
wiki defines no I/O, so their only observable output is an interpreter-
invented state dump (the tape, registers, deque, or grid printed at halt to
make the run testable) — not a language output command.  They cannot
generate text, compute a boolean, be differentially verified, or step
through input, so by the admission criteria' "usable file-based I/O" test
they are the weakest additions.

| Language | Output |
| --- | --- |
| ArrowQueue | None; only halt-vs-hang, which expresses AND/OR-class boolean functions (see `docs/walls.md`). |
| A Painter Ant | Visited-grid bounding box (`#`/`.` raster); has a boolean generator (exact n <= 2). |
| Brainpocalypse | Final tape dump. |
| Kak | Final tape dump. |
| Minsky Swap | Final register dump. |
| RAM0 | Final state dump. |
| Stun Step | Final reached-cells dump. |
| Bitdeque | Final register/deque dump. |

**Candidate to remove, once decided.**  The roadmap's planned no-output
candidates (Point Break, State and Main, Crement, Your Time Is Up) would be
dropped under the same policy.  The I/O-capable interpreter-only languages
(Number Seventy-Four, Trash, Grapheme, Movesum, Lightlang)
are not in this tier.

**Generator story is mostly absent.**  None of the eighteen
interpreter-only languages has a text generator.  Six have boolean
generators (A Painter Ant, ABCDirection, Back, BF-PDA, Jaune, Lamfunc);
ArrowQueue realizes
the halt-vs-hang *termination* convention for AND/OR-class functions (a ring
template committed as its truth-machine example); and the other twelve
have no boolean story at all (each hits a documented wall in
`docs/walls.md`).  So the generator-story criterion is failed by most of the
interpreter-only set, and the distinction below is only how observable
their non-generator output is.

**Against removal (weighed, not decisive).**  Most of these are the *only*
implementation on the wiki (only this repo's interpreter is listed), so
removing them leaves the language with no implementation at all — which the
admission criteria treat as a genuine gap.  Of the eight, only Brainpocalypse
and Kak have external implementations (Ruby/Crystal/Python and Common
Lisp/Scratch/C respectively); the other six (ArrowQueue, A Painter Ant,
Minsky Swap, RAM0, Stun Step, Bitdeque) are Bangyen-only.  The tradeoff is
between "no I/O ⇒ cannot participate in the repo's verification machinery"
and "sole implementation ⇒ removing creates a gap"; the removal is recorded
here as a candidate to resolve deliberately rather than by default.

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
as distinct interpreters); only the redundant cross-checks went.  2 Bits 1
Byte's interpreter was itself removed later (see `docs/limitations.md`), on
top of its already-removed cross-check.

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

`esolangs.tools.booleans.a_painter_ant` expresses every one- and two-input
truth table exactly (answer = the origin's colour after a whole cycle, all
templates cycle-stable), and raises for `n >= 3`.

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
in `docs/walls.md`; a successful construction would lift the generator's
cap to arbitrary ``n``.
