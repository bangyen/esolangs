# Roadmap

Planned work, in priority order.  Language assessments, documented walls,
and ruled-out ideas live in `docs/limitations.md`; completed ideas live in
the commit history.  This file only tracks what is still on the table.

## New interpreters (in priority order)

Candidates from re-scanning the esolangs wiki's Category:Unimplemented and
from User:PythonshellDebugwindow's language list.  The scan is now fully
exhausted: every candidate with a usable file-based I/O protocol, a complete
specification, and a plausible generator or boolean story has an
interpreter, including COD (the last one on the table).  What shipped and
what was ruled out (Gravity, Earfuck, Conveyor, Chainlang, Binary ///,
Fourfuck, Aaargh++, Bitwise Cyclic Teast, and the languages already
implemented elsewhere) is in the commit history and `docs/limitations.md`.
Nothing is tracked here as remaining.

**COD shipped** with a two-input (`n <= 2`) boolean generator
(`esolangs.tools.boolean.parameterized.cod`); the interpreter, VM adapter,
and generator are in the commit history.  The shipped construction differs
from the design this roadmap originally sketched: rather than a
branch-free `_`-gate decision tree, each input bit gets its own `+` fork
(one branch continues forward, the other peels off) with a short
`(...)<` gauntlet on each branch that only the matching value's copy
survives — the wiki's "two/three branches" rule for `+` makes this
deterministic, so it needs no seeded-randomness decision and never touches
COD's random-junction rule.  `n == 1` reuses the same routing with its
second input fixed to a literal `0`.  Generalizing past `n == 2` (a
`2**n`-leaf layout) is unbuilt; see `docs/cod_boolean_generator.md` for the
full construction and what a general-`n` version would need.

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

A language becomes a candidate when it has real language-defined output but
no generator that uses it (no conditional to drive a boolean generator, or a
boolean cap too low to be interesting), or when its only boolean construction
would break a documented convention and its text generator is too thin to
stand alone — see `docs/limitations.md` for the removed cases and the
criteria.  The interpreter-only languages with no text generator but a
working, uncapped boolean generator (ABCDirection, Back, BF-PDA, Bitdeque,
Jaune, Lamfunc, Minsky Swap, RAM0, Grapheme, A Painter Ant, ArrowQueue) are
**not** candidates: they participate fully in the repo's verification
machinery via the boolean generator, and their only weakness is an
interpreter-invented state dump where the wiki defines no text output.

- **2dFish — deferred.**  Its text generator is a straight-line delta
  encoder (the thinnest computational category), and it has no total
  once-embedding boolean generator: the decision tree would need multiple
  embedding (the exactly-once exception Dotlang was removed for) and the
  once-embedding chain is affine-only (constants, XOR/XNOR, projections —
  see `docs/walls.md`).  It stays for now because the delta encoder is
  genuine arithmetic (the current criterion's line is literal-embed), but
  if the criterion is ever tightened to "real computation only"
  (branching/search, not straight-line deltas), it becomes the final
  removal — nothing else is thin.

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

**No input in RISC-V.**  RISC-V cross-checks are for no-input/output-only
languages only.  The fuzzer feeds the generated *program* to the RISC-V ELF
as its stdin (`scripts/verify_differential.py`), and the Python side reads
whole lines while the unicorn runner does raw byte reads, so an input-reading
port would need to rewire input-bit passing and match the line-delimited
`input_char` semantics.  Languages whose generators read input belong in the
Rust column, where the reference gets input bits directly.

| Toolchain | Languages |
| --- | --- |
| RISC-V assembly | NoComment (tape + stack with a byte-indexed skip), BF-PDA (bit stack + tape), RAM0 (register machine), BIO (three registers plus a loop stack, guards checked lazily to match the Python interpreter's control flow), Minsky Swap (two registers, a swap pointer, and a jump-on-zero `~`; each `~` keeps a fixed target across every visit via a token-indexed table, not a running execution-order cursor). |
| Rust | Forþ, Basicfuck, Unsquare, 3x, 2dFish, Painfuck, LaserFuck (stacks, typed registers, 2D grids); %^2^-1 and bit~ keep corpus cross-checks but lost their straight-line text-generator fuzzes. |

**Worth adding (audited).**  These languages have complex-output generators
(arithmetic encodings, branch-and-goto OISCs, runtime state carried across
characters) that a random differential fuzz would exercise beyond the
round-trip corpus, so a cross-check would add real verification.

| Toolchain | Languages |
| --- | --- |
| Rust | AddSubJump (branch-and-goto OISC), Collatz Multiverse (runtime odd/even rules), Polynomial (integer roots encoding a command stream), Clockwise (2D ring routing), Dig (2D mole grid with runtime segment counts), Container (threshold-rule firing), ZTOALC L (Collatz-trajectory-driven execution), 3D Brainfuck (tape + loops), Factor (a giant integer whose prime factors re-encode a looped brainfuck program), S*bleq (tape OISC with a `<= 0` branch), Back (2D beam reflection routing), A Painter Ant (2D cycle-stable routing), ABCDirection (2D grid + Boolfuck input), Bitdeque (deque + register + goto).  Those that read input — and the 2D grid models — belong in Rust under the no-input RISC-V rule above. |

**Judgment call (borderline).**  The generator is stateful or looped, but
its output is a fixed pattern the round-trip already covers, so a cross-check
would add little: brainfuck, BFStack, BrainIf, Minifuck, Modulous, SLOW
ACV MAMMALIAN, WII2D, Home Row.  These stay without a cross-check unless a
specific bug motivates one.

**Removed (did not meet the criterion).**  Seven cross-checks were removed
for having no generator or only a corpus-only cross-check; see
`docs/limitations.md` for the languages and reasoning.

## VM / debugging interface

`esolangs.make_vm` (step-and-inspect wrappers) and `esolangs.make_debugger`
(breakpoints and watches over the VM) now cover the whole interpreter
registry: every language has a step()/halted/snapshot() state object and a
VM adapter in `esolangs.vm._VM_ADAPTERS`.  The last conversions --
Jaune, SLOW ACV MAMMALIAN, ZTOALC L, Between, MyScript, Lamfunc, Forbin,
and Suptiftam -- are in the commit history; the recursive-tree-walker
ones (Lamfunc, Forbin, Suptiftam) needed an explicit resumable frame in
place of Python's own call stack, documented in `docs/walls.md`'s
state-cycle-detection section.  Nothing is tracked here as remaining.

## Forbin's expression-position recursion (remaining depth-cap gap)

Suptiftam's calls, Forbin's *statement-position* calls (`f(y);`), and all
of Lamfunc's calls were converted to an explicit frame stack, removing an
invented 250-level cap (or, for Lamfunc, Python's own default recursion
limit) as a correctness bug — a correct, terminating program recursing
deeper than that no longer halts wrongly.  Forbin's *expression-position*
calls (`x = f(y)`, where the assignment needs the callee's return value
back synchronously mid-expression) were deliberately left out of that
conversion and still recurse natively, bounded only by Python's own
default limit rather than a documented cap.  See `docs/walls.md`'s
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
rest.  Every step-capable interpreter (the whole registry, now that the VM
section above is complete) has a `snapshot()`, so state-cycle detection
coverage is as wide as it can get without weakening the non-determinism
exclusion below.  What remains:

- Painfuck's `y`, WII2D's `?`, and LaserFuck's random heading are
  non-deterministic, so all three stay on the wall-clock backstop
  regardless of `snapshot()` coverage.
- Suptiftam's calls, Forbin's statement-position calls, and all of
  Lamfunc's calls now run on an explicit frame stack (see the section
  above) instead of native Python recursion — confirmed while doing those
  conversions, this does *not* make infinite recursion cycle-detectable via
  `run_until_halt_or_cycle`.  A call that never returns pushes one new
  frame per `step()` and none is ever popped, so `snapshot()`'s frame
  tuple strictly grows and two whole-machine snapshots can never compare
  equal: unbounded growth, the same class `+[>+]` already falls into for
  that specific mechanism.  A separate, narrower check — comparing a
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

**No language is currently on this list.**  ZTOALC L was assessed and kept:
its tree-shaped construction is walled past dense, non-symmetric `n == 3`
(re-verified in `docs/walls.md`, not just the original argument), so lifting
the cap is closed, but the generator still covers every `n <= 3` table plus
popcount-symmetric tables at any `n` — materially more than the two
generators removed under this section's precedent (Home Row at `n <= 2`,
Minifuck's `n <= 3` 0-preserving-only), so it stays.
