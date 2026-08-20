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
| COD | low | 2D concurrency-heavy cods; numeric output + value gates make a boolean generator plausible but unbuilt. |

**COD — the only candidate left.**  The other candidates were assessed and
ruled out; the assessments are in `docs/limitations.md`.  COD's only output
is numbers, so it can never have a text generator — but a single 0/1
printed as the cod's value is a valid boolean output, so a boolean
generator is the live question: it would route one cod through the `_`
(reflect iff nonzero) and `<` (remove iff zero) value gates into a decision
tree, laid out branch-free so the cod never hits a random junction.  That
is a heavy, unbuilt 2D construction, and the interpreter needs a
seeded-randomness decision first (the LaserFuck precedent), so COD stays
low-priority and risky rather than ruled out.

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

**No language is currently on this list.**  A language becomes a candidate
when it has real language-defined output but no generator that uses it (no
conditional to drive a boolean generator, or a boolean cap too low to be
interesting) — see `docs/limitations.md` for the removed cases and the
criteria.  The interpreter-only languages with no text generator but a
working, uncapped boolean generator (ABCDirection, Back, BF-PDA, Bitdeque,
Jaune, Lamfunc, Minsky Swap, RAM0, Grapheme, A Painter Ant, ArrowQueue) are
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
- **No cross-check (straight-line generators):** 6-5, Decleq,
  Dimensional, Qoibl, and the rest.

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

**Removed (did not meet the criterion).**  Seven cross-checks were removed
for having no generator or only a corpus-only cross-check; see
`docs/limitations.md` for the languages and reasoning.

## VM / debugging interface (remaining work)

`esolangs.make_vm` (step-and-inspect wrappers) and `esolangs.make_debugger`
(breakpoints and watches over the VM) cover most of the interpreter
registry.  What remains:

- **More step-capable interpreters.**  Convert the rest of the registry to
  a step()/halted state object: the boolean-parameterized machines without
  a state object yet, and the remaining tape/stack OISCs.

## Hanging-test optimization via state-cycle detection

Hanging programs are bounded with wall-clock timeouts (SIGALRM in the
robustness tests and on the differential fuzzer's Python side, and
instruction-count caps on the native references) except where state-cycle
detection (`esolangs.vm.run_until_halt_or_cycle`) has replaced them for
step-capable, deterministic machines — see `docs/limitations.md` for which
interpreters are covered and why the wall-clock backstop remains for the
rest.  What remains:

- **Extend state-cycle detection to more interpreters.**  Only step-capable
  machines can be checked; converting more of the registry (see the VM
  section above) grows this set too.
- Painfuck's `y` and WII2D's `?` are non-deterministic, so both stay on
  the wall-clock backstop regardless of how far the conversion goes.
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

**No language is currently on this list.**  ZTOALC L was assessed and kept:
its tree-shaped construction is walled past dense, non-symmetric `n == 3`
(re-verified in `docs/walls.md`, not just the original argument), so lifting
the cap is closed, but the generator still covers every `n <= 3` table plus
popcount-symmetric tables at any `n` — materially more than the two
generators removed under this section's precedent (Home Row at `n <= 2`,
Minifuck's `n <= 3` 0-preserving-only), so it stays.
