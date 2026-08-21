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

**COD shipped**, including a boolean generator for any `n >= 1`
(`esolangs.tools.boolean.parameterized.cod`); the interpreter, VM adapter,
and generator are in the commit history.  The shipped construction differs
from the design this roadmap originally sketched: rather than a
branch-free `_`-gate decision tree, each input bit gets its own `+` fork
(one branch continues forward, the other peels off) with a short
`(...)<` gauntlet on each branch that only the matching value's copy
survives — the wiki's "two/three branches" rule for `+` makes this
deterministic, so it needs no seeded-randomness decision and never touches
COD's random-junction rule.  An initial `n <= 2` version (later `n <= 3`)
was superseded once every fork's routing got its own private grid cells
joined by plain concatenation, instead of sharing cells across forks via a
"sacrificial retrace" merge that could not be proven safe past `n == 3`;
see `docs/cod_boolean_generator.md` for the full construction, exhaustively
verified through `n == 3` (all 256 three-input tables) and sample-verified
at `n == 4`.

## Transpilers

A direct transpile between languages with no shared core is not a rewrite —
it needs a full runtime of one inside the other.  The transpilers that
shipped (the brainfuck family, `Decleq → S*bleq`, Dimensional → LaserFuck,
and the dropped silent-dropper/round-trip-only ones) are in the commit
history; the walls are in `docs/limitations.md`.  Nothing is tracked here as
remaining: the only candidates identified (a second Forth dialect ↔ Forþ,
Boolfuck ↔ ABCDrection/Minifuck) each need a *new* interpreter first, not
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
  Unsquare, 3x, %^2^-1, Painfuck, bit~, LaserFuck.
- **No cross-check (straight-line generators):** 6-5, Decleq,
  Dimensional, Qoibl, S*bleq, and the rest.

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
| Rust | Forþ, Basicfuck, Unsquare, 3x, Painfuck, LaserFuck (stacks, typed registers, 2D grids); %^2^-1 and bit~ keep corpus cross-checks but lost their straight-line text-generator fuzzes. |

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
specific bug motivates one.  Clockwise and 3D Brainfuck joined this list:
Clockwise's 2D routing is one fixed ring shape (only the ring size and the
parity pattern vary with the text), and 3D Brainfuck's generator is the
brainfuck generator's output with ``>``/``<`` renamed to ``n``/``s``, so
both sit in the brainfuck family's borderline class rather than the
complex-output one.

**Removed (did not meet the criterion).**  Seven cross-checks were removed
for having no generator or only a corpus-only cross-check; see
`docs/limitations.md` for the languages and reasoning.

## RISC-V assembly compilers

The compilers in `src/esolangs/compilers/` translate a program to
RISC-V Linux assembly, assembled and run under unicorn by
`scripts/verify_riscv_unicorn.py`; the eleven shipped (AddSubJump, BF-PDA,
BFStack, Collatz Multiverse, Decleq, Home Row, Jaune, RAM0, S*bleq,
Suffolk, Unsquare) are in the commit history, with addsubjump, bfstack,
collatz_multiverse, decleq, sbleq, suffolk, unsquare, and home_row
round-tripping their text generators.

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

**AddSubJump shipped**, but not as unrolled per-token blocks like the other
compilers: its jump target (`*c`) and even its operands are computed at
runtime from self-modifying memory, so no compile-time control-flow graph
exists to unroll.  The emitted assembly is instead a real
fetch-decode-execute loop over a `.data` array of 65536 `.dword` cells
(`mem:`), with `read_cell`/`write_cell` subroutines centralizing the
special-address dispatch (`-1` I/O via `read`/`write` syscalls, `-2..-5`
flags, `-6/-7/-8` constants, `-9` flag-update mode) that both operand fetch
and the write-back share.  The interpreter's unbounded, growing memory
becomes a fixed preallocated buffer, the same tradeoff RAM0's compiler
already makes for its 256-cell RAM.  See
`src/esolangs/compilers/addsubjump.py`.

**Collatz Multiverse shipped.**  Every line's target and operands are
statically known (unlike AddSubJump's self-modifying memory), so each line
compiles to a labelled block that falls through to the next; the only
runtime indirection is a `lineNumber` assignment, dispatched through a
linear compare-and-branch scan over `1..n` (the same table-scan shape as
Jaune's `.switch`) that lands on `.halt` when the computed target falls
outside the program.  Named scalars get a compile-time symbol table (one
`.dword` slot apiece); named arrays get a fixed 256-slot window per name,
direct-indexed with a wrapping bitmask (`_ARRAY_SIZE` is a power of two, so
the mask alone reproduces Python's `%` for negative indices too, without
needing the M extension) — the same fixed-window tradeoff RAM0's compiler
makes for its RAM.  `input` parses a whole stdin line as a signed decimal
integer one byte at a time (unlike Suffolk's single-byte read), halting on
EOF before any digit but still returning a value for a final line with no
trailing newline.  The Collatz rule's signed multiply needed its own
shift-add routine that negates both operands to a non-negative magnitude
before shifting (a plain arithmetic-shift loop on a negative multiplier
never terminates), and the compiler discovered that late `.data` references
compile to `gp`-relative addressing under linker relaxation, so `_start`
now sets `gp` from `__global_pointer$` up front — bare-metal `_start` has no
libc to do it.  See
`src/esolangs/compilers/collatz_multiverse.py`.

**S*bleq and Decleq shipped.**  Both are Subleq-family OISCs: the
interesting lowering is the self-modifying memory (an in-place
subtract-and-branch for S*bleq, a decrement-and-branch for Decleq), which
becomes a real fetch-decode-execute loop over a `.data` cell array — the
same shape AddSubJump's compiler already uses, since both languages'
jump targets are runtime values, not statically known.  The memory-mapped
I/O addresses (S*bleq's `-3`/`-2`, Decleq's `-2`/`-1`) emit syscalls the
way AddSubJump's `-1` does; Decleq's `-1` read additionally halts the
program at EOF rather than reading zero, matching the interpreter's
`EOFError` (which unwinds the whole run).  Their text generators are
straight-line mirrors, so the fuzz axis adds nothing — the artifact is the
point; both round-trip their generators through
`scripts/verify_riscv_unicorn.py` and pass the interpreters' own test
cases compiled and run under unicorn.

Two interpreter memory-model quirks are not reproduced, the same tradeoff
already accepted for AddSubJump: writes past the compile-time program
length grow the interpreters' Python-list memory (moving their halt
boundary outward) but not the compilers' fixed 65536-cell buffer, and
Decleq's write path has no negative-index guard, so a negative `b` hits
Python's negative-index wraparound on the interpreter's list rather than
being treated as out-of-range like every other special address — an
accident of the list-backed implementation, not documented language
behavior, and not a shape any real countdown-idiom program produces (found
by fuzzing adversarial random operands, not by any hand-written example).
See `src/esolangs/compilers/sbleq.py` and
`src/esolangs/compilers/decleq.py`.

**Forþ shipped, intrinsic value only.**  Unlike the self-modifying-memory
OISCs above, Forþ's `(`/`[`/`{` bodies are lexically delimited and matched
at compile time exactly the way the interpreter matches them at run time
(nesting counts only the same open character, so a `(` inside a `[...]`
body does not affect the `[`'s match), so this compiles to a real call
graph instead of a fetch-decode-execute loop: each bracketed body becomes
its own labelled subroutine reached through `call`/`ret`, mirroring the
interpreter's explicit call-stack of frames.  `;` is the one genuinely
dynamic construct — `{` stores a body keyed by whatever runtime value is on
top of the stack, and `;` looks a body up by a popped runtime value — so it
lowers to a small runtime association list (a `.bss` array of `(key,
address)` pairs) scanned backward on lookup so the most recent `{` for a
given key wins, matching the Python dict's overwrite semantics; a key with
no entry is the interpreter's `table.get(key, "")`, an empty scope that
returns immediately.  An empty-stack pop is fatal at any nesting depth (a
direct jump to the halt label, matching `HaltError` unwinding every
frame), while every other invalid operation (a binary op or `c` with too
few operands, division/modulo by zero) aborts only the innermost scope (an
early `ret`).  rv64i has no M extension, so `*`/`/`/`%` are software
(shift-add multiply, sign-adjusted repeated-subtraction divide truncating
toward zero to match `_trunc_div`/`_trunc_mod`), and every arithmetic
result is re-truncated to a sign-extended 32-bit word to match `_wrap32`.
The one correctness trap: every subroutine that itself issues a `call`
(the generated per-scope bodies, the binary-op dispatchers, `table_call`'s
indirect `jalr`) must save and restore `ra` around it, or a nested call's
return address clobbers the caller's own — RISC-V's `call`/`ret`
pseudo-ops both target the same link register, so this is silent until
the outer routine returns to the wrong place.  It already has a fuzzed
Rust cross-check, so this is artifact-only — it adds no differential value
and should not duplicate the Rust reference's job.  See
`src/esolangs/compilers/forth.py`.
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
popcount-symmetric tables at any `n` — materially more than Minifuck's
`n <= 3` 0-preserving-only generator, removed under this section's
precedent — so it stays.  Home Row's original `n <= 2` generator was also
removed under this precedent, but a later closed-form construction (packing
the input bits into a binary accumulator and walking a linear equality
chain, rather than routing a beam to `2**n` distinct grid cells) lifted the
cap entirely — see `docs/walls.md` — so it is no longer an example of a
removed generator.
