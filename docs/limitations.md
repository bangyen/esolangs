# Limitations and ruled-out ideas

What the generators cannot do, and which approaches were assessed and
rejected — so a future agent does not re-assess a rejected language or
re-run a failed approach.  Genuine future work is in `docs/roadmap.md`; the
admission criteria for a candidate language are in `docs/CONTRIBUTING.md`.

The tables below name every blocker at a glance; the full structural
argument for each is in [`docs/walls.md`](walls.md).

## Interpreter conventions

The interpreters share a few behavioral conventions, so `esolangs.run` is
predictable across languages:

- **Empty programs are a no-op by default.**  An empty (or blank-only)
  program produces no output, unless the language structurally requires
  content to start — a Collatz seed line (ZTOALC L), or a program grid
  (Circlefuck, BF-PDA, Suffolk, Dig, Back, Clockwise) — in which case it is
  rejected with a clear `ValueError` (usually ``"... cannot be empty"``).
- **Exhausted input raises :class:`EOFError` by default.**  A program that
  reads past the end of `stdin` is almost always a bug, and the loud error
  surfaces it (and lets `,[.,]`-style cat loops terminate).  S*bleq reads
  `0` at EOF instead, per the wiki.  Malformed programs raise `ValueError`
  and runtime halts raise :class:`HaltError`, never a raw Python exception.
- **Byte input is line-delimited.**  ``io.input_char`` reads a whole input
  line and returns its first character (the rest of the line is discarded),
  so a byte-oriented program needs one line per byte: `,.,.` on ``"A\nB"``
  echoes ``"AB"``, while ``"AB"`` on one line supplies only ``A`` and the
  second `,` raises `EOFError`.
- **Recursion is uncapped except in Forbin's expression position.**
  Suptiftam, Forbin's statement-position calls, all of Lamfunc's calls,
  Forþ's stored scopes, Jaune subroutines, and Grapheme functions run on an
  explicit frame stack (`_Machine.frames`), so a terminating recursion of
  any depth completes.
  Forbin's *expression-position* calls
  (`x = f(y)`, needing the result back synchronously) still recurse
  natively and hit Python's own limit; the language has no realistic
  program shape that recurses this way.  `run_until_halt_or_ancestor` can
  prove an infinite recursion when a call re-enters an ancestor with the
  same entry state; calls whose bindings keep changing still need the
  wall-clock backstop.  `run_until_halt_or_cycle` compares whole-machine snapshots, which
  a growing frame stack never repeats.  See [`docs/walls.md`](walls.md).

## Text generator blockers

| Language | Why it cannot emit arbitrary text |
| --- | --- |
| A Painter Ant | No I/O; prints the visited-grid bounding box (a `#` white / `.` black raster, with the ant's cell as `@` or `o`). Has a general (any-arity) boolean generator; no text generator. |
| Algebraic Programming Language | The only datatype is a number and an executed line prints its *result*, so the output alphabet is digits (plus `.` and `-`) — the same wall as Jaune and COD. The wiki's own hello-world prints the ASCII values `72 101 108 …` rather than the characters, which is the spec conceding the point. Has an uncapped boolean generator; no text generator. |
| ArrowQueue | No output at all; the IP walks the grid and halts, printing nothing. |
| Back | Prints the tape as a number list. |
| BF-PDA | `.` prints the top bit as the `'0'`/`'1'` character, so the output alphabet is just the two digits. |
| Bitdeque | No I/O in the spec; this interpreter prints the deque contents as numbers when the program ends. |
| COD | The ``---`` sink prints the cod's value as a decimal integer with no separator, so only digits are spellable — the same output-alphabet wall as Jaune. Has a parameterized boolean generator; no text generator. |
| Circuit Diagram | The ``:`` output emits its gate's value as a bit string, so the output alphabet is just `'0'`/`'1'`, and nothing in the spec turns those bits into a byte. Has a boolean generator; no text generator. |
| Flowchart | The only output node emits one bit, and byte-packing cannot apply: the wiki's truth machine reads one bit, writes one bit, and halts, so under any packing it would never flush and the example would print nothing. Character-per-bit is forced by the spec's own example. Has an uncapped boolean generator; no text generator. |
| Grapheme | Strings cannot contain `E` (terminates stringmode) and there is no concatenation, so even "HELLO" is unspellable. |
| Jaune | `^` prints the current cell as a decimal integer, so only digits are spellable. |
| Lamfunc | `p` prints a number as binary, so the output alphabet is just `'0'`/`'1'`. |
| Minsky Swap | Prints the registers as numbers. |
| Point Break | No output at all; a program only halts or loops. Has a termination-convention boolean generator (halt for 0, loop for 1); no text generator. |
| RAM0 | Prints a state dump. |

The straight-line generators are also at their length floor — no
per-character encoding can be meaningfully shortened:

- **Sqrt-factorized** (BIO) builds each byte as ``a*b + r`` with ``a`` near
  ``sqrt(byte)``, so it is O(sqrt) not O(byte).
- **Delta- and cell-reuse** (brainfuck, Circlefuck) keep a running cell and
  emit only the difference, so consecutive close bytes cost a couple of
  tokens.
- **Literal-embed** (Taglate, Eval, Between, MyScript, Nevermind)
  put the text in the program directly (a string/queue literal); the text
  *is* the data.
- **Literal-load with no arithmetic** (Sophie, Dimensional) reload the byte
  each character because the language has no instruction to reuse across
  characters.
- **Decleq, S*bleq** store each byte as a literal data cell behind a 3-cell
  output instruction (4 cells per byte).  A delta-encoding was considered
  and rejected: both are OISCs whose only arithmetic is ``mem[a] -= mem[b]``
  with a ``<= 0`` branch, so adjusting a running cell costs a second 3-cell
  instruction per byte (6-7 cells total) — strictly worse than the literal.

## Boolean generator blockers

| Language | Why it cannot compute a truth table |
| --- | --- |
| 123 | Parameterized (only reads real stdin at one fixed location, so a decision tree cannot read its inputs); answers with the termination convention. All tables build through `n == 3` from stored plans, and the **constructed** route now covers that ground exhaustively too: all 276 tables through three inputs build through it and replay correctly. Its embed scrub, planned separation and endgame are total by argument; the verdict search is not, and `construct` tries two mark geometries in order (see [`docs/walls.md`](walls.md) for the parity law). Four inputs: 12/12 on a random sample, mostly 0.5-30s each, one table needing the second geometry at ~350s (the exhausted first attempt is the cost). Five inputs build for the first time — the sparse extreme in ~50s (91k characters) with its closing replay, and a random table through the model-validated build in ~10 minutes (840k characters; measured without awaiting the closing replay) — and six inputs is unmeasured: wall-clock cost, not any known structural wall, is what binds there. Budgets scale with the row count and bound divergence, not arity. |
| %^2^-1 | Only control flow is `t` (rewind on a nonzero accumulator), a whole-program loop that cannot count passes; no program that *reads* its inputs computes any two-input function (proved; [`docs/proofs.md`](proofs.md)). The shipped generator is parameterized and embeds instead — six constructions build every table at `n <= 4` and every table tried from five through eleven inputs. Construction-by-construction detail is in the `%^2^-1` row of the Generator caps table below. |

## Generator caps (shipped)

| Generator | Cap | Wall or liftable? |
| --- | --- | --- |
| NoComment | `n <= 11` | Liftable by host config, not a language wall: 255 bounds a single `s` skip, and skips compose, so past eight inputs the generator splits the index into byte-sized summands and walks one staircase each. What binds instead is the interpreter's tape, which the `2**n` output cells plus a guard apron exhaust at `n == 12` against the default 4096 cells — and the wiki requires the memory space to be static but never specifies a *size*. Both `run` and the generator take a `tape` argument: `n == 12` builds and runs at `tape=16384`, and the default stays 4096 because the size is observable through the wrap. Verified by exhaustive interpreter runs at `n == 9`, `10`, and `11`; instrumented runs show no skip amount and no written cell exceeding 255, so the chain is spec-legal. Full argument in [`docs/walls.md`](walls.md#nocomments-arity-cap-the-255-bounded-one-jump-not-a-composition). |
| Polynomial | instruction-count cap, not `n`-driven: a table needing more than 138 instructions under *both* constructions is rejected, so well-merging tables render at any width (parity through `n == 8` at 106 instructions) while random dense tables refuse from `n == 6` | Performance cap: the interpreter recovers instructions by factoring the polynomial, and that is what becomes impractical — so the bound is on instructions, not inputs. |
| %^2^-1 | all tables at `n <= 2`; conjunctions and disjunctions of literals at any `n`; **every table at `n == 3`** (256/256) and **`n == 4`** (65536/65536); **five through eleven inputs, closed by the fold** — every table tried plans and executes; the staged interleaved fold also builds and exhaustively replays the 12-, 13-, and 14-input XORs whose late ignored suffixes would make the all-row ladder exceed the workspace; a generic table past eleven inputs may still be refused | Raised, and the rest is **open, not walled**. Six constructions were built in sequence (affine setter, subcube cascade, composed-affine derivation, threshold ladder, deep band, fold), each lifting a bound the previous one hit. The staged interleaved fold now merges equal suffix cofactors between embedded inputs, escaping the all-row fold's 12-input workspace bound for compactable states; it is a bounded fallback, not yet a total generic construction past eleven inputs. Full construction-by-construction argument, including every measured number and the two prior "walls" that turned out to be padding/search artifacts, is in the `%^2^-1` entry of [`docs/walls.md`](walls.md) under "Assessed boolean candidates that fell through". |
| 6-5 | `n <= 5` exact; past that, tables whose folded tree needs more than 35 branch labels are rejected (AND-6 and other well-folding tables *do* render) | Genuine wall: 35 is the count of the spec's own operand alphabet (`0-9A-Z`), and labels cannot be reused, so the budget is total standing tree nodes, not depth. **Do not retry operands past `Z`** — that decodes only through an unguarded interpreter fallthrough (undefined behaviour, see the conformance gap below) and was reverted once already. Full argument in [`docs/walls.md`](walls.md). |
| ZTOALC L | every table, bounded only by size: the anchor table reaches 1132 commands and the emitted program must stay under the `2**22` line gate | Not a capability wall. The generator constructs a branch-free array lookup — the row index is built by double-and-add (`s += s`; `s += x{i}`, no multiply needed), the table is one-hot encoded into a `2**n` array, and `t[s]` selects the answer — placed on a Collatz trajectory, which is collision-free because a trajectory visits distinct values until it reaches 1. Sparse tables reach further than dense ones, since the array init is one command per selected row. |
| WII2D | `n <= 4` exact (exhaustive through four); symmetric tables of any arity via closed forms; dense non-symmetric sampled built at `n == 5` and `n == 6`, rejected from `n == 7` | **Cost guard, not a wall — liftable by paying build time and width.** `n == 7` trips `_WII2D_MAX_INDEX_DOMAIN = 32` before the chain is walked; it never established that anything fails. The chain (first legal junction pair from a fixed catalogue) is provably total; so is the fold algebra, by an injective-square-and-safe-fold induction. That proof's unary runs are doubly exponential, so it does not replace the shipped size-conscious decoder. The single best-fold rule is exhaustive at `D == 16` but **not total** under its fixed centre cap: `0 1**K 0 1` is a counterexample for every even cap `K`, including the actual 4096. Full argument and measurements in [`docs/walls.md`](walls.md). |
| Factor | program-size cap, not `n`-driven: sparse tables stay under the cap well past the dense ones — constant-0/1 at any tested `n`, and AND-`n` (one `1` in the table) through `n == 5` — while dense tables refuse from XOR4 up | Liftable by host config: the encoded integer's decimal length is checked against `sys.get_int_max_str_digits()` (CPython's int-to-string DoS guard, default 4300 digits) before rendering — the Factor *interpreter* parses its program the same way, so a caller who raises the process-wide limit gets both the generator and the interpreter working past it. |

Home Row and Minifuck's boolean generators were once dropped as trivial and
have both been rebuilt.  Home Row's is a closed-form construction
(binary-pack the inputs into an accumulator, then walk a linear equality
chain) with no `n` cap at all.  Minifuck's old cap was a property of
*reading* the inputs; embedding them instead lifts it, and the generator is
now **total** — no arity and no table it declines, pinned by
`test_no_arity_is_gated` on a fully-essential six-input table.  What bounds
a caller is cost, not expressiveness: the template grows about fourfold per
arity.  See [`docs/walls.md`](walls.md) for Home Row, and
[`docs/minifuck_generator.md`](minifuck_generator.md) for the arguments
behind Minifuck's totality and the mechanisms refuted along the way.

The parameterized no-input generators embed every input exactly once rather
than re-embedding a bit at multiple decision nodes, mirroring how an
input-capable language reads each input once per run.  There are no
exceptions; the per-language reasoning is in [`docs/walls.md`](walls.md).
The rule has survived a real test: a Minifuck route that re-embedded input
`i` at `2**i` cells would have closed four inputs with far less machinery
(and passes the slot-order test, which only requires non-decreasing names),
and was rebuilt on single embeds instead — the embed already carries the
whole row identity, so re-reading the tape substitutes for re-embedding it.

## Interpreter conformance gaps

Known places where an interpreter here is more permissive than its language's
spec.  These are **not** capability findings: a generator must not build on
them, because behaviour outside the spec is undefined rather than available.

### 6-5: `num` accepts operands the spec does not define

The [wiki spec](https://esolangs.org/wiki/6-5) defines operand notation as
"Numbers beyond 9 denoted using letters. (A=10, B=11 etc.)", so a `7n`/`8n`
operand is `0..9` or `A..Z` and its value is `0..35`.  The interpreter
instead decodes with an unguarded `ord(char.upper()) - 55` fallthrough and
validates nothing, which exceeds the spec three ways: values past 35 become
addressable (`[` is 36, `{` is 68, and the range continues); the decode is
not injective, since `.upper()` folds case and punctuation aliases onto
digit values (`num(":") == 3`); and it is unbounded below
(`num("\n") == -45`).  The interpreter's own docstring states a *narrower*
contract than the spec — "0-9 literal, A-F hexadecimal" — so the documented
contract, the spec, and the behaviour are three different things.

**Nothing shipped emits into that region.**  `_SIX_FIVE_MAX_LABEL` (now in
`esolangs/tools/boolean/six_five.py`, having moved there when the BF-to-6-5
transpiler was removed) is derived from the operand alphabet, and
`_six_five_label` raises for any value outside `0..35` — any future emitter
into this language must respect the same cap.

The interpreter's `num` itself stays permissive: it still accepts the
undefined operands rather than rejecting them.  Whether a 6-5 program using
one should hard-error is a behaviour change for callers, not a bug fix, so
it is recorded here rather than made.

## Compilers are bounded-agreement, not total, over unbounded values

The gaps above run one way — an interpreter accepting more than its spec.
This one runs the other: a *compiler* that is narrower than the interpreter
it reproduces.

Every compiler in `src/esolangs/compilers/` lowers a value to a
**fixed-width machine word** — 64-bit signed at the widest, and a byte in
BFStack, whose cells are byte-sized on both sides.  So where the
interpreter's value is an unbounded Python integer, the two agree only
while it stays inside that width: at the 64-bit ones, `-2**63 .. 2**63 - 1`.
Outside it the compiled word wraps and the answer is silently wrong — no
compiler diagnoses it, and the assembler accepts the truncation.

*Which* compilers this applies to is deliberately **not** listed here — the
list would go stale on any new compiler or interpreter change, and the rule
derives it in one read.  A compiler is exact when its **interpreter** is
itself bounded, and bounded-agreement when it is not:

- **Exact.** Forth's interpreter wraps every result through `_wrap32`, and
  BFStack's cells are `% 256`; the compiler reproducing that width is
  agreement, not a caveat.
- **Bounded-agreement.** Everything whose interpreter arithmetic runs on
  plain Python integers.
- **Not applicable.** Forbin, whose values are bits and tagged words rather
  than arithmetic; its docstring accordingly claims *acceptance* totality,
  which is the distinction this whole section turns on.

**CV(N)(C) adds a second axis**, and it is the reason this list is a rule
rather than a table: an unbounded *structure* bounds a compiler the same
way an unbounded value does.  Its interpreter's deque and its built
function are Python lists, so the compiled form fixes both at 4096 entries
alongside the 64-bit word — but the two axes fail differently.  A value
that overruns its width wraps silently, as above; a structure that overruns
its buffer **aborts**, because the push is range-checked and jumps to
`.halt`. A diagnosed stop is the better failure, and it is available here
only because a push is a call rather than an arithmetic result. Its word
is also *unsigned*, the interpreter being explicit that memory is unsigned,
so its wrap point is `2**64` and its subtractions floor at zero rather than
going negative.

CV(N)(C) carries a **third** narrowing, not about width: its `s` parses a
line with Python's `int()` after `str.strip()`, both Unicode-aware, where
the assembly is ASCII — `int("4_2")` is 42 (underscores legal between
digits) and `strip` removes any `str.isspace()` character including NBSP,
so `4_2` and `\xa042` read as 0 compiled and 42 interpreted. Every ASCII
form agrees, signs and leading zeros included. General lesson for any new
compiler: agreement can be narrowed by a *library function's* generality,
not only by a machine word's width.

Two measured boundary checks, both at the same place, one per shape of
entry:

- **Decleq** takes the value straight from the program text, so no
  arithmetic is needed to reach it: cell `2**63` is stored as
  `-9223372036854775808` and `2**64 + 5` as `5`.  Its sole instruction
  branches on `<= 0`, so a flipped sign redirects control flow at once.
- **Container** has to accumulate there across ticks, and its clamp changes
  the character of the failure: `max(res, 0)` **destroys** a wrapped-negative
  value instead of letting it wrap back, so the divergence is permanent once
  triggered — yet invisible while the value only feeds `OUT`, which is taken
  `% 128` on both sides.  Agreement holds through `2**63 - 1` and breaks at
  `2**63`.

**Nothing shipped approaches this.**  The largest integer any compiler emits
over the text generators' programs is **65536**, fourteen orders of
magnitude below the 64-bit bound.  CV(N)(C)'s boolean generator hits the
largest runtime value measured anywhere, **6,765,201**, still twelve orders
of magnitude inside it.  This bounds hand-written programs only.

### Why it is recorded rather than checked or widened

Both fixes were costed and declined; a future change should not re-attempt
either without addressing why.

**A per-site overflow check is unsound at the cheap granularity.**
Two's-complement addition is exact mod `2**64`, and Container's clamp reads
only the *committed* value's sign, so a rule sum may cross `2**63` mid-tick
and come back down with the right answer — a check firing at each `add`
would abort a program that is correct today.  A *sound* check needs to
track carries across the whole rule sum, which costs ~2x (Container's n=5
boolean program: 1472 → 2816 instructions).  Forbin's arena abort is not a
precedent: it is one site guarding a resource programs actually exhaust.

**Arbitrary precision would not buy totality either.**  No compiler here has
a heap — every one uses static `.data`/`.bss` at compile-time-known sizes —
so bignums mean inventing an allocator, ten times over, on a target with no
hardware multiply.  Values are not the only unbounded axis either: RAM0 and
Collatz Multiverse already ship a fixed window for unbounded *index* space,
so closing the value axis would leave that one open.

The one live alternative, if loud failure is ever wanted, is compile-time
rejection of an out-of-range **literal** in the program-text compilers
(Decleq's shape, reachable with no arithmetic at all).  It is unshipped
because it trades away acceptance parity: the interpreter runs `2**63 0 0`,
and a compiler that refuses it no longer accepts what the interpreter
accepts.

## Divergent example outputs

`examples/boolean` holds one committed program per boolean generator, and
the bar is that the answer must be *recoverable from what the program
prints* — not that the program prints the answer and nothing else, since
several of these languages have no output instruction at all and dump their
state at halt.  Three cases stay divergent for reasons no *generator* change
reaches:

- **state dump around the answer** (`back`, `minsky-swap`, `ram0`) — no
  output instruction, so the answer arrives at a fixed position inside a
  dump of the machine, and the rest cannot be suppressed;
- **a painted grid** (`a-painter-ant`) — the grid *is* the output, and the
  answer is which leaf the ant rests in;
- **no output at all** (`arrowqueue`, `point-break`) — the answer *is*
  termination: the program halts for a 0 and loops forever for a 1, so only
  the halting branch can be committed.

One caution for anyone re-surveying example coverage: the example stems are
display names lowercased with spaces as dashes (so `BF-PDA` → `bf-pda`), not
language ids (`bf_pda`), so a naive `id not in stems` check still reports
BF-PDA as missing.  It has an example.

## Assessed and rejected

Languages from the wiki that were assessed against the admission criteria
and did not make the repo — whether they were never implemented (the
roadmap's fell-through) or were removed after being implemented.  The
viable candidates are in `docs/roadmap.md`; the full rationale for each
verdict is in the commit history.  ``(removed)`` marks languages whose
interpreter, generator, and tests were deleted from the repo.

- **2 Bits 1 Byte** (removed): joke; single-byte program, no text or boolean generator, externally implemented.
- **2dFish** (removed): its `(...)*` capture-and-print makes its true generator floor a literal-embed, and its boolean generator was separately walled as affine-only with no total once-embedding construction — the same generator-story criterion The Temporary Stack was removed under.
- **Aaargh++**: 4D work-in-progress with a partial spec.
- **ABCDirection** (removed): its boolean generator was the suite's size outlier — 15,729 characters for a two-input XOR, 58x the median (270) and 3.5x the next largest. That was already the floor: four passes over the layout had taken it down from 377 KB with diminishing returns, and the remaining size is inherent to the donut grid and direction-dispatched command set rather than a tuning oversight, so a text generator would have landed in the same class. Do not re-add it expecting layout work to close the gap.
- **Albabet** (removed): straight-line two-register accumulator; no conditional at all, so no boolean generator.
- **ALT-4**: stack-based concurrent language with no input or output commands.  Baking input into the program is not disqualifying — it *is* the parameterized convention, and the wiki supplies both an infinite loop and a truth-machine, so a termination-convention generator is the natural fit.  What is unbuilt is the general construction: a single file's stack holds only zeroes, so it is one unary counter with an emptiness test, and an arbitrary table needs a decision tree over that.  Separately, `2` multithreads by *filename*, which is the file/OS-based I/O the criteria exclude — a generator can avoid `2`, an interpreter cannot.  Reopened as a candidate pending both.
- **ASCII art** (removed): brainfuck with an art alphabet; a trivial reskin.
- **Binary ///**: stub with no usable specification.
- **Bitwise Cyclic Teast**: work-in-progress, interpreter still in development.
- **Brainpocalypse** (removed): no input; invented dump and a one-bit halt-vs-loop wall; externally implemented.
- **Chainlang**: spec its own author describes as unfinished.
- **Conveyor**: stderr-only output, and no input command.  The output objection is not decisive — `HALT`, a jumper that otherwise loops back, and `IFEZ`/`IFGT` give the halt/loop distinction a termination-convention generator needs.  Rejected on spec stability instead: the page leaves its own ROT13 example unwritten and gates commands behind unexplained privilege tiers (`(Supervisor+)`).
- **Cortex language 3A**: its 8 real primitives are a clean brainfuck-like tape machine, but the `;`-prefixed commands are not composable — the wiki assigns them by table lookup to whole canned programs (`;&` is specified to *be* Hello World, `;$` a full brainfuck interpreter), so a faithful interpreter means hardcoding ~16 opaque special cases; treating `;` as a no-op contradicts the spec's own worked examples.
- **Crement**: self-modifying, no I/O.  Having no input to branch on is not the blocker — Crement is Turing complete on-page, branches with `JUMP` on a data field's sign, halts by running past the last address, and loops by jumping backward: Point Break's exact profile.  Unlike Point Break the wiki defines no truth machine, so adopting the convention here would extend that precedent rather than follow it.  Reopened as a candidate; no construction built.
- **Dotlang** (removed): its boolean generator was the only one that could not embed each input exactly once — Dotlang has no storage, value test, or arithmetic, so a decision tree has to re-embed every bit at every junction (2**i gates), and its text generator is a plain literal-embed.  Too thin to justify being the sole exception to the exactly-once rule; the fork-and-kill construction is recorded in [`docs/walls.md`](walls.md).
- **DSDLAI** (removed): trivial Dig reskin with a random death chance; non-deterministic.
- **Earfuck**: trivial brainfuck reskin (notes for instructions).
- **Eso2D**, **Jumplang**, **brainfunc**, **Minimal operation language**, **Yaren**, **2KWLang**: wiki-categorized Implemented with documented external interpreters; not a gap.
- **EXCON** (removed): straight-line 8-cell bit pool; no conditional at all, so no boolean generator.
- **Fourfuck**: incomplete, a stub with a couple of commands.
- **Gate**: a wire/logic-gate circuit whose spec does not define the two commands a generator needs.  Having no input command is *not* the blocker — it has real output, constants, and a value-testable branch (`+`).  The blocker is that the page never exercises either: `+` appears in none of the nine worked examples, so nothing pins the branch geometry a decision tree would rest on, and no example emits output at all.  The `<` operator is defined only by a self-referential image, and propagation order is unspecified.  Fails the complete-spec criterion; there is no talk page to resolve it.  **Circuit Diagram** is the alternative in the same genre.
- **Gravity**: non-computable evolution; nothing verifiable.
- **HaltJS**, **MangularJS**: JavaScript subsets; a faithful interpreter is a whole JS engine, not a file-based char/line interpreter.
- **Huf** (removed): straight-line two-register accumulator; no conditional, so no boolean generator.
- **Indent**: no input at all, so no boolean generator.
- **Jumpmin**: Jumplang's minimization removes I/O entirely, so no boolean generator.
- **Kak** (removed): no input; only the tape bit-string (an invented dump); externally implemented.
- **Keys** (removed): a two-line equality comparison; a gadget, not a language model.
- **Lightlang** (removed): boolean capability caps at the AND/OR class; only a single bit is ever printed.
- **LogicF---**: joke, non-deterministic and non-functional commands.
- **Movesum** (removed): no conditional at all, so no boolean generator; numbers-only output.
- **N Refine**: probabilistic self-rewriting OISC with no I/O; already implemented elsewhere.
- **Not Python**, **2001: An Esolang Odyssey**, **Stu**, **Bias**, **Writeover**: joke or vaguely specified, no usable spec or I/O.
- **Number Seventy-Four** (removed): string-rewriting with no input; output alphabet `0`/`1`/`H`.
- **Objects In Mirror Are Heavier Than They Appear**, **OpenStreetCode**, **Unary Filesystem**, **Phile**: file/OS-based, no portable file I/O.
- **PASM**: output is a 16x16 pixel screen; no char/line I/O.
- **PlusOrMinus**, **PlusIntMinus**: output-only accumulator with no input or conditional; no boolean generator.
- **Procedure**: only `the sum of ...` arithmetic is defined, so a faithful interpreter would have to invent the rest. Revisit if the wiki or Pure defines the operators.
- **Queuenanimous**: no I/O at all; externally implemented.
- **Regimin**: no I/O at all.
- **something positive**: explicitly uncomputable.
- **Stackint**: output is an optional interpreter dump, and input is a single number per run.
- **State and Main**: one `main` argument, no output, no conditional; a boolean generator could reach at most one input.
- **Stun Step** (removed): no input; invented dump and a one-bit halt-vs-loop wall; sole implementation removed anyway.
- **The Temporary Stack** (removed): its text generator is a literal-embed, and under the tightened generator-story criterion (a literal-embed text generator needs a boolean generator) that made it inadmissible.  **The boolean wall it was also removed under is refuted** — the drain condition `sum(stk[1:]) / 2 > stk[0]` *is* an input-dependent branch, and numeric mode prints `front - 1` as text so a front of 1 or 2 gives `'0'`/`'1'` directly.  What the language actually supports is a *partial* generator (9 of 16 two-input tables, roughly ArrowQueue's threshold class), since the four XOR-like tables need an input-gated silent death that does not exist.  Whether that clears the bar is an open judgement; see [`docs/walls.md`](walls.md).
- **Trash** (removed): advance-to-next-prime gadget; can never print `1`.
- **Uack**: total; no output.
- **Vandevelo**: input-only, no output at all — but a termination-convention generator needs no output, so that alone no longer settles it.  It is the strongest of the reopened cases: `Inp` is *real* input (no substitution needed), `::` is JavaScript `&&` and the `-!>`/`~!>` forms negate, so AND-with-NOT is functionally complete; the wiki's own truth-machine already answers by termination.  The open question is hang detection, not expressiveness: the loop is lazy self-reference rather than a revisited machine state, so state-cycle detection may not apply.  Reopened as a candidate; no construction built.
- **Varigen**: explicitly "uncomputable" joke language.
- **Welcome To...**: work-in-progress.
- **XENBLN**: 256 commands, most unassigned, with the command list split across a subpage; not a complete or stable spec.
- **Your Time Is Up**: random rule choice, no I/O; nondeterministic.
- **Zfuck**: I/O is the initial/final tape state, not char/line I/O.
- **｛｝**: family of eight levels; levels 1-2 are uncomputable, levels 3-7 have no I/O, and the only I/O-capable level (8) is a literal brainfuck reskin.

## Cross-check removals

The Rust and RISC-V cross-checks were all removed, along with the cargo
toolchain and `scripts/verify_extra_generators.py`.  Seven went for not
meeting the independent-and-broad bar — no generator, or a corpus-only
cross-check that added nothing over the round-trip tests.  Of the remaining
eight, six were written alongside the Python interpreters they
checked (so their agreement was not independent evidence), and retaining the
two that were genuinely independent would have kept the full toolchain cost
for a fraction of the coverage.  `extra/assembly` stays — it shares its
toolchain with the RISC-V compilers in `src/esolangs/compilers/`.  The
per-cross-check list is in
[`docs/walls.md`](walls.md#cross-check-removals-why-seven-were-dropped).

## Hang detection

Wall-clock timeouts (SIGALRM, instruction-count caps) bound hanging
programs by default; deterministic, step-capable machines instead get an
immediate cycle-detection proof (`esolangs.vm.run_until_halt_or_cycle`).
Which interpreters are covered, why a few stay on the timeout (random
headings, no `snapshot()` yet), and the `pytest --cov` deadlock this also
sidesteps are in
[`docs/walls.md`](walls.md#state-cycle-detection-coverage-hang-detection-without-a-wall-clock-timeout).

## Transpilers: the admission bar, and what it removed

Transpilers here are **total** over their source language: each accepts
every program that language's own interpreter accepts, and agrees with it
on every run the interpreter completes.  The five admission criteria live
in the module docstring of `esolangs/tools/transpilers.py`, which is what
an author of a new one reads.

Six of the ten transpilers this repo used to carry were partial and were
removed rather than annotated: a documented-but-unenforced subset gives a
caller no way to test whether their program is inside it (`bio_to_bf`
mistranslated silently despite naming its class in prose).  **Do not
re-add a transpiler that only rejects loudly or only documents its
subset — enforce totality, or don't ship it.**

**The four that remain, and the standing fact each one rests on.**

- **`Decleq → S*bleq`**: emits a fixed emulator loop over the Decleq image
  rather than a static per-instruction rewrite, because Decleq can jump into
  the *interior* of a block it just wrote — only an emulator has no
  interiors. **Standing collision, not a bug**: S*bleq's input address `-2`
  yields `0` for both end-of-input and an empty input line, so two distinct
  Decleq inputs (EOF vs. an empty line) become indistinguishable in the
  target language. `test_decleq_empty_input_line_is_a_target_language_collision`
  asserts this rather than trying to fix it — it cannot be fixed without
  changing S*bleq's own semantics.
- **`brainfuck → 3D Brainfuck`**: total via a runtime guard sentinel placed
  on the axis brainfuck's tape never uses, reproducing brainfuck's
  clamp-at-cell-0 behavior for `<` (3D Brainfuck's own `s` walks negative
  with no clamp). No residue.
- **`brainfuck → Painfuck`** and **`BFStack → brainfuck`**: total by
  construction — per-command rewrites over a strict superset target, no
  rejection path needed.

**The six removed, and why re-adding each needs a different fix than the
one that was tried.**

- **`BIO → brainfuck`** — the disqualifying case, and the reason criterion 4
  exists: a documented-but-unenforced register-range restriction let a
  program silently mistranslate (register hits 256, BIO loops forever,
  brainfuck's wrapped cell is 0 so it skips the loop).
- **`Basicfuck → brainfuck`** — gated on cell range, refusing legal
  Basicfuck (`r=0~127`, `r=0~65535`); enforced (not silent), but still an
  uncheckable subset.
- **`brainfuck → Circlefuck`** — structural, not fixable: a Circlefuck tape
  **is the program**, fixed at transpile time, while brainfuck's tape grows
  unboundedly; by pigeonhole no fixed-length Circlefuck program holds every
  input's tape.
- **`brainfuck → 6-5`** — capped at 17 loops (6-5's loop markers are
  `0-9A-Z`, two per loop, and past `Z` is undefined interpreter behaviour,
  not more labels — see the conformance note above). An interpreter-in-6-5
  would sidestep the cap the way Decleq's emulator did, but the classic
  423-byte `dbfi` self-interpreter needs 58 loops — evidence against, not
  proof.
- **`Dimensional → LaserFuck`** and **`Streetcode → LaserFuck`** — partial
  on LaserFuck's output convention (no output command; only a tape dump at
  halt) and, for Streetcode, on control flow. **Streetcode's control-flow
  wall is real and separate, and it recurs for any future rewrite target**:
  Streetcode has no loop command, so brainfuck's `[` needs a revisited
  program state to close on, but a ring re-entering the road past a
  junction returns under a different heading/steering-latch state — the
  state that would decide the loop is never revisited. Showing a ring
  *can* re-close would need proving a cell stays non-negative across
  arbitrary loops, i.e. value analysis, which this module's unsound static
  analysis attempt has already failed twice.
- **Earlier drops.**  `nocomment_to_bf` silently dropped commands; the
  `6-5 → bf` and `Circlefuck → bf` decoders only reversed the forward
  transpilers' canonical form (round-trip-only, not total).

## Proved facts (kept set)

Three facts the tests cannot establish were machine-checked in Lean 4 +
mathlib: SLOW ACV MAMMALIAN's generator search totality, Factor's
Dirichlet-based prime-search totality plus the encode/decode round-trip, and
the `%^2^-1` two-input boolean wall.  The proofs now live as prose in
[`docs/proofs.md`](proofs.md), which records each statement, the argument
behind it, and what the axiom audit reported; the Lean sources are in git
history at `528fe2c2`.  Every other proof (the ported interpreters, their
equivalence proofs, and the generator correctness proofs) had already been
dropped as redundant with the round-trip test suite.

Note the scope of the `%^2^-1` wall: the contract binds one program across
all four bit combinations and feeds the bits in through the machine's input
list, so the theorem is about programs that *read* their inputs.  The shipped
generator is parameterized and builds every two-input table, so the theorem
bounds the reading model, not the language.

No comparable Minifuck theorem is open: a reading construction builds and
verifies all sixteen two-input tables on the shipped interpreter (the
searches that once suggested a narrower reading model were length-bounded
well below the 88-148 characters it needs).  See [`docs/walls.md`](walls.md).
The shipped generator embeds its inputs instead and builds every table at
`n <= 3`.
