# Limitations and ruled-out ideas

What the generators cannot do, and the assessments that concluded an
approach is not viable (or only partially viable).  Completed work lives in
the commit history; this file records the walls, the negative results, and
the reasoning behind them.  Genuine future work is in `docs/roadmap.md`, and
the criteria for assessing a candidate language are in `docs/CONTRIBUTING.md`.

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
- **Execution is unbounded through the public API.**  `esolangs.run` has no
  step limit: interpreters run until the program halts naturally or loops
  forever.  Suffolk is the sole interpreter that ships with a fixed
  instruction limit, and callers cannot set one through the public API.
- **Recursion is uncapped except in Forbin's expression position.**
  Suptiftam, Forbin's statement-position calls, and all of Lamfunc's calls
  run on an explicit frame stack (`_Machine.frames`), so a terminating
  recursion of any depth completes.  Forbin's *expression-position* calls
  (`x = f(y)`, needing the result back synchronously) still recurse
  natively and hit Python's own limit; the language has no realistic
  program shape that recurses this way.  Infinite recursion is an uncaught
  hang — `run_until_halt_or_cycle` compares whole-machine snapshots, which
  a growing frame stack never repeats.  See [`docs/walls.md`](walls.md).

## Text generator blockers

| Language | Why it cannot emit arbitrary text |
| --- | --- |
| A Painter Ant | No I/O; prints the visited-grid bounding box (a `#` white / `.` black raster, with the ant's cell as `@` or `o`). Has a general (any-arity) boolean generator; no text generator. |
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
| 123 | **A generator ships; the cap is arity, not expressiveness.** It is parameterized (`2` at location -3 reads real stdin, so a decision tree cannot read its inputs) and answers with the termination convention — halt for 0, a proven loop for 1 — the same one ArrowQueue and Point Break use. All four one-input and all sixteen two-input tables are built. The fill is `1` for a one and `2` for a zero, which move the pointer in opposite directions, so displacement after the embeds is `(#zeros - #ones)` and the `-4 -> 0` wrap reduces it modulo four: a tail of `1`s decodes that counter, giving a function of popcount alone (XNOR at two ones, XOR at four), and `3`'s TRUE-backward re-run supplies the asymmetric tables. Three-input and wider tables are **rejected**, including those depending on only two of their inputs: an ignored input still has to be embedded, every fill moves the pointer, and the pointer phase *is* the computed value, so a trailing inert embed shifts the very quantity the plan decodes. Whether a wider construction exists is open; see [`docs/walls.md`](walls.md). |
| %^2^-1 | Only control flow is `t` (rewind on a nonzero accumulator); a whole-program while loop that cannot count passes. No program that *reads* its inputs computes any two-input function (proved in Lean), but the shipped generator is parameterized and builds all sixteen: it embeds the bits, composes one affine setter per input into a product-weighted accumulator, and prints with `l`, which spells the accumulator in decimal so `0`/`1` need no branch. The setters are derived from the table, not searched. Above two inputs a second construction takes over, the **subcube cascade**: the accumulator is loaded with 1 (`ips`) and passed through one setter per input — the identity (`pp`) where the bit matches the pinned literal, an erase (`'p`) where it does not — so it survives as 1 exactly when every pinned bit matches. Appending `ips` maps the result to `1 - r`, so complements cost three characters more. Both branches are two characters, so nothing leaks through `len()`, and a program is `2n + 4` characters (`2n + 7` complemented) at any arity. That covers every conjunction or disjunction of literals — AND-`n`, OR-`n`, NAND-`n`, NOR-`n` and every subcube — with no search: 48 of the 256 three-input tables and 154 of the 65536 four-input ones. Other tables are rejected rather than risking a wrong program. |

## Generator caps (shipped)

| Generator | Cap | Wall or liftable? |
| --- | --- | --- |
| NoComment | `n <= 11` | Liftable by host config, not a language wall: 255 bounds a single `s` skip, and skips compose, so past eight inputs the generator splits the index into byte-sized summands and walks one staircase each. What binds instead is the interpreter's tape, which the `2**n` output cells plus a guard apron exhaust at `n == 12` against the default 4096 cells — and the wiki requires the memory space to be static but never specifies a *size*. Both `run` and the generator take a `tape` argument: `n == 12` builds and runs at `tape=16384`, and the default stays 4096 because the size is observable through the wrap. Verified by exhaustive interpreter runs at `n == 9`, `10`, and `11`; instrumented runs show no skip amount and no written cell exceeding 255, so the chain is spec-legal. Full argument in [`docs/walls.md`](walls.md#nocomments-arity-cap-the-255-bounded-one-jump-not-a-composition). |
| Polynomial | instruction-count cap, not `n`-driven: a table needing more than 138 instructions under *both* constructions is rejected, so well-merging tables render at any width (parity through `n == 8` at 106 instructions) while random dense tables refuse from `n == 6` | Performance cap: the interpreter recovers instructions by factoring the polynomial, and that is what becomes impractical — so the bound is on instructions, not inputs. |
| %^2^-1 | all tables at `n <= 2`; conjunctions and disjunctions of literals at any `n` (48/256 at `n == 3`, 154/65536 at `n == 4`) | Partly lifted, and the rest is **open, not walled**.  The derived path composes one affine map per input into a shared value, which forces each cofactor to be constant or an affine image of one shared function — only 88 of the 256 three-input tables satisfy that.  The subcube cascade escapes that by making the *erase position* input-dependent.  What is not yet reached is tables needing an OR of several disjoint subcubes: chaining indicator gadgets needs a running total to survive a gadget that erases, and there is one register — an argument about one gadget shape, not a proof about the model.  Bounded searches over repeated setters reached about 100/256 at `n == 3` and were still climbing when stopped.  The printing tail is likewise only bounded: reset-free tails are affine hence injective and separate exactly two values, and a sweep of every tail to length 10 never separated more than two — but the over-3003 reset merges values into one class, and a longer tail that drives one class past the reset while landing another on 1 is not excluded.  %^2^-1's own NOT is 36 commands and a length-8 sweep missed it, which is why this sweep is not read as a wall. |
| 6-5 | `n <= 5` exact; past that, tables whose folded tree needs more than 35 branch labels are rejected (AND-6 and other well-folding tables *do* render) | Genuine wall, and the 35 is the **language's** number: the [wiki spec](https://esolangs.org/wiki/6-5) defines operands as "Numbers beyond 9 denoted using letters. (A=10, B=11 etc.)", and letters are `A..Z` — so `0..9A..Z` names 1..35 and an `8n` jump cannot address a marker past the 35th. Labels also cannot be reused: `8n` resolves its target by scanning the token list from the start for the n-th `4`, so a label is a global ordinal fixed by position, which makes the budget a total-standing-nodes count rather than a tree-depth one. The decision tree spends one label per internal node its constant-subtree fold leaves standing; the worst case is an alternating table, which folds nothing and spends `2**n - 1` — 31 at `n == 5`, so every table renders there; 63 at `n == 6`, so refusals begin. What survives past `n == 5` is tables that fold hard: ~1% of random `n == 6` tables, but structured ones like AND-`n` at any width. A lift built on operands past `Z` (`[` = 36, `{` = 68) was tried and **reverted**: those decode only through an unguarded fallthrough in this repo's interpreter, which is undefined behaviour rather than a language property — see the conformance gap below. |
| ZTOALC L | every table, bounded only by size: the anchor table reaches 1132 commands and the emitted program must stay under the `2**22` line gate | Not a capability wall. The generator constructs a branch-free array lookup — the row index is built by double-and-add (`s += s`; `s += x{i}`, no multiply needed), the table is one-hot encoded into a `2**n` array, and `t[s]` selects the answer — placed on a Collatz trajectory, which is collision-free because a trajectory visits distinct values until it reaches 1. Sparse tables reach further than dense ones, since the array init is one command per selected row. |
| Minifuck | every table at `n <= 3` (4/4, 16/16 and 256/256, interpreter-verified); wider tables fall through to the searches and may raise | Not a wall at `n <= 3`. The staged route *derives* the `(separator, settle count, suffix, accumulator)` choice rather than searching for it, and derives a whole arity in one pass — measured 0.7s for two inputs and 12s for three, so the first three-input table costs the arity and the other 255 are free. Selection reads the accumulator column **at the read**, not the cell holding the answer beforehand; the two differ because the walk out applies the running prefix-XOR. A table and its complement share a staging, the endgame trying both read polarities. One three-input table needs a stored exception, its suffix spelled by no bracket run. Past three inputs a missing staging degrades to the searches rather than raising outright; see [`docs/walls.md`](walls.md). |
| WII2D | `n <= 4` exact (exhaustive through three, sampled dense at four); symmetric tables of any arity via closed forms; dense non-symmetric sampled built at `n == 5` and `n == 6`, rejected from `n == 7` | **Cost guard, not a wall — liftable by paying build time and width.** The `n == 7` refusal is `_WII2D_MAX_INDEX_DOMAIN = 32`, checked against the decode domain `2 ** (n - 1)` before `_wii2d_decode` runs, so it never established that anything fails. It does not: with the constant raised to 64 a dense non-symmetric `n == 7` table builds in 1.54s, interpreter-verified on all 128 input combinations. What the guard buys is a bounded build — decode length grows sharply with the domain, and a sampled pattern at `D == 64` exceeded a 120s budget where its siblings took seconds. The tail, not the width, is why the default stays. A second knob: the fold squares, so peak `|acc|` reaches tens of thousands of bits on sampled `n == 7` decodes; the wiki states no accumulator bound and this interpreter uses arbitrary-precision integers, so wide builds rest on spec silence — though shipped `n == 5` already passes one byte. Symmetric tables never reach the check (majority-of-12 is 397 characters, instant). Completeness past the exhaustively-tested `D == 16` is open, not refuted. Measurements in [`docs/walls.md`](walls.md). |
| Factor | program-size cap, not `n`-driven: sparse tables stay under the cap well past the dense ones — constant-0/1 at any tested `n`, and AND-`n` (one `1` in the table) through `n == 5` — while dense tables refuse from XOR4 up | Liftable by host config: the encoded integer's decimal length is checked against `sys.get_int_max_str_digits()` (CPython's int-to-string DoS guard, default 4300 digits) before rendering — the Factor *interpreter* parses its program the same way, so a caller who raises the process-wide limit gets both the generator and the interpreter working past it. |

Home Row and Minifuck's boolean generators were once dropped as trivial and
have both been rebuilt.  Home Row's is a closed-form construction
(binary-pack the inputs into an accumulator, then walk a linear equality
chain) with no `n` cap at all.  Minifuck's old cap was a property of
*reading* the inputs; embedding them instead lifts it.  See
[`docs/walls.md`](walls.md) for both.

The parameterized no-input generators embed every input exactly once rather
than re-embedding a bit at multiple decision nodes, mirroring how an
input-capable language reads each input once per run.  There are no
exceptions; the per-language reasoning is in [`docs/walls.md`](walls.md).

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

**Nothing shipped emits into that region.** The BF-to-6-5 transpiler used
to: it allowed 18 loops (36 markers), one past the 35 the spec names, so the
18th loop's end label came out as `8[`.  It is now capped at 17 loops (34
markers) by `_SIX_FIVE_MAX_LABEL`, derived from the operand alphabet rather
than hardcoded, and `_six_five_label` raises for any value outside `0..35`.
Both examples (`examples/hello-world/6-5.txt`, `examples/boolean/6-5.txt`)
conform with a maximum operand of 8, as do all 276 boolean programs the
generator emits at `n <= 3`.

What stays permissive is the interpreter's `num` itself, which still accepts
the undefined operands rather than rejecting them.  Whether a 6-5 program
using one should hard-error is a behaviour change for callers, not a bug
fix, so it is recorded here rather than made — nothing in the repo depends
on the answer now that the emitters are capped.

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

## Transpiler walls

Most transpilers here exist where languages share a semantic core (through
brainfuck, and the direct pair `Decleq → S*bleq`).  Where no core is
shared, a program rewrite will not do it; what is needed is a full
runtime-in-a-language, which a target can only host if it has dynamic
dispatch.  `Decleq → S*bleq` is the pair where that turned out to be
available, and it is now an emulator rather than a rewrite:

- **OISC-to-OISC (Decleq ↔ AddSubJump).**  ASJ's only conditional is
  ``dest = dest ± op`` by a fixed operand, so it has no dispatch to build a
  fetch-decode-execute loop out of.

  This entry used to include `Decleq → S*bleq`, on the claim that "neither
  has dynamic instruction dispatch."  That was wrong about S*bleq, and the
  transpiler is now **total over programs**.  S*bleq's `c` operand is
  *indirect* (`ip = mem[c]`) and its `-1` special is a writable instruction
  pointer, which is dispatch; its code cells are ordinary memory, so a
  generated program can patch its own operand fields to reach an address it
  computed at runtime, which is indirect load and store.  Those are the
  pieces a runtime-in-a-language needs, so `decleq_to_sbleq` emits one: a
  fixed emulator loop over the Decleq image, which rides along as data in
  `[loop | scratch | image]` order, the image last so that Decleq's
  grow-on-write and read-past-the-end-as-zero coincide with S*bleq's.

  What that bought is the whole class the static rewrite rejected:
  self-modifying code (a write re-read as an operand), jump targets and
  program lengths that are not multiples of three, and negative operands.
  A static per-instruction rewrite cannot be total here for a reason worth
  naming: a computed target may land in the *interior* of a translated
  block, and only an emulator has no interiors to land in.  The cost is
  size and speed -- a fixed ~1250-cell loop, and a few hundred S*bleq steps
  per Decleq step -- not coverage.

  Two divergences remain, and both are properties of S*bleq's input
  primitive rather than of the translation.  Address `-2` is the only way
  an S*bleq program can read input, and it yields `0` both at end-of-input
  (where Decleq raises `EOFError`) and for an *empty* input line (where
  Decleq's reader yields `10`, the newline that ended it).  A `"\x00"` line
  also yields `0`, so two distinct inputs reach one value.  Every S*bleq
  computation is a function of the values it reads, so no S*bleq program
  whatsoever separates them -- this is a collision in the target language,
  not a gap in the rewrite, and it is asserted rather than hidden in
  `test_decleq_empty_input_line_is_a_target_language_collision`.  The
  interpreter's other error exits are not behaviour to reproduce: its
  `HaltError` is a harness step budget, and an out-of-range negative `b`
  crashes it with `IndexError`.
- **2D-to-2D: the store is shared, the control flow is not.**  This entry
  used to say no two 2D languages share a model.  That is wrong for
  Streetcode and LaserFuck, which hold the same thing -- a tape of
  unbounded signed cells under a pointer -- and whose instruction sets are
  the *same eight commands*: Streetcode's `^~=_IO` are brainfuck's
  `+-><,.` under other glyphs.  `Streetcode → LaserFuck` ships on that
  basis.

  What does not carry across is control flow, for a reason worth naming
  rather than asserting.  Streetcode has no loop command; the car branches
  by which exit of a junction it takes, and brainfuck's loop needs a state
  the program returns to once per lap to close its `[`.  A drawn ring does
  not give one:

  - A ring entered from a junction rejoins the road *past* that junction's
    square, returning under a different heading and different steering
    latches.  The state that decides the loop is never revisited, so there
    is no `[` to close.
  - A ring that does re-cross its test square crosses further gaps on the
    way, and [every gap crossing reads the CPth cell](streetcode.md).
    Those reads are junctions too, and showing they cannot steer means
    showing a cell stays nonzero across iterations -- value analysis, not a
    rewrite.  The counting loop in `tests/interpreters/test_streetcode.py`
    is the worked example: nine laps, and three junctions entangled in
    them.

  So the shipped class is the programs the tape never steers, and drawn
  control flow is rejected rather than mistranslated.

  **What that leaves in practice.**  The text generator emits a single
  straight street -- no branching at all -- so its output is in class, but
  only *unwrapped*: the default folds the line into a boustrophedon to save
  columns, and the fold is a ring the car steers around, which is not.
  Asked for a width wide enough to keep one row (`generate(..., width=N)`
  with a large `N`), texts transpile and round-trip.  This used to be
  limited to *one-character* texts, on the ground that a LaserFuck program
  prints its tape once and so carries a single `O`; that limit is gone --
  outputs are staged into a region the halt dump replays in order (see the
  Dimensional entry below), so `hi`, `abc` and `Hey` all round-trip.  The
  boolean generator's programs are still out on the tree argument above,
  and both checked-in `examples/` programs are wrapped.  So what bounds
  the in-class set now is control flow alone: unwrapped text generation of
  any length, and hand-drawn corridors.  Lowering the control-flow half
  would need scratch cells and a converged answer -- a compiler, which is
  what separates the two halves of this bullet.  The boolean generator's
  Streetcode programs are further out still: they are decision trees whose
  leaves each print.
- **Why each partial transpiler is partial.**  `Decleq → S*bleq` is the
  reason this entry exists: its wall was documented as structural and was
  not, so the remaining partial transpilers are worth separating by *what
  kind* of limit they have.  The split is not subtle once named.  A limit
  that is a **resource or observable mismatch** is structural and no
  cleverness reaches it.  A limit that is an artefact of the **rewrite
  being per-instruction or per-glyph** falls to simulation whenever the
  target has enough dispatch -- which is exactly what happened to Decleq.
  Two of the shipped restrictions are the first kind and two are the
  second; none of the liftable ones is built, and they are candidates here
  rather than claims.

  *Structural.*  `brainfuck → Circlefuck` is the strongest case, and the
  rejections it raises (below cell 0, drifting loops) name the wrong
  reason.  The real limit is finiteness: brainfuck's tape grows
  unboundedly rightward (the interpreter appends a cell on demand), while
  a Circlefuck tape *is the program*, wrapping modulo its fixed length.
  The witness is `,[[->+<]>-]`, which carries its counter one cell right
  per decrement and so touches `n + 1` cells for an input of `n` -- tape
  length 4, 9 and 21 for inputs 3, 8 and 20.  A translation must fix its
  size at transpile time, so by pigeonhole no fixed-length Circlefuck
  program holds every input's tape.  Markers could widen the class; they
  cannot make it total.  Separately, `→ LaserFuck` cannot represent a
  *non-terminating* program that produces output, LaserFuck having no
  output command at all -- `dump()` prints the tape when it halts, so a
  source that emits forever has no image.  That one is mostly moot under
  the repo-wide contract of agreeing on runs the reference completes.

  *Lifted.*  `brainfuck → 3D Brainfuck` used to reject programs that dip
  below cell 0, because brainfuck clamps `<` there and 3D Brainfuck's `s`
  walks negative.  A static shift of the origin does not fix it, the
  clamping being *load-bearing*: `+.<.` prints `\x01\x01` in brainfuck
  precisely because `<` was a no-op, and no starting offset turns a move
  into a non-move.  What works is a runtime guard, and 3D Brainfuck hands
  one over cheaply -- its array is a *three-dimensional* grid, so the
  sentinel goes on an axis brainfuck's tape never uses.  A prefix `su+dn`
  writes `1` at `(-1, 1, 0)`, and `<` compiles to `su[dnu]d`: step left,
  rise to the marker plane, and loop only if the sentinel is there, which
  happens exactly at the left edge and undoes the step.  No data cell is
  written, the sentinel is written once, and the guard's brackets nest
  with the program's own.  **The transpiler is now total**, and with no
  I/O residue at all -- unlike `Decleq → S*bleq`, every observable channel
  agrees, cells wrapping 0-255 in both, both growing on demand, both
  printing `chr(cell)` and raising `EOFError` on exhausted input.

  Two silent mistranslations died with it, and both are worth recording
  because the old entry claimed this transpiler *rejected* rather than
  mistranslated.  It did neither reliably.  The class check was a linear
  scan of the program text, so it missed dips that only happen on a
  loop's later laps: `++>+[<-].` passed the check and compiled to a
  program that never halts, where brainfuck prints `\x00`.  And comments
  were passed through unchanged, but brainfuck's comment characters
  include `n`, `s`, `e`, `w`, `u` and `d`, every one an array move in the
  target -- so an ordinary word silently moved the pointer, `+.hello.`
  printing `\x01\x00` against brainfuck's `\x01\x01`.  Only the eight
  brainfuck commands are emitted now, which also protects the guard: a
  stray `u` would leave the `y = 0` plane, where a later `+` could forge
  the sentinel.

  *Widened.*  `Dimensional → LaserFuck` used to allow a `.` only as the
  last command, on the ground that LaserFuck prints its tape once, when
  the last laser dies.  But equivalence is judged on the output a
  terminating run *captures*, so when a byte leaves the program is
  unobservable -- only its order survives.  Each `.` therefore copies its
  cell into an output region, and the halt dump replays the region in
  order.  A top-level op runs exactly once, so the slots fill in textual
  order, which is execution order, and the region is sized statically; it
  is laid out *last*, after the working cells and one temp, so it grows
  rightward into LaserFuck's unbounded tape with nothing to displace.  The
  epilogue drives the working cells negative to hide them and touches each
  slot with `+-` to keep it -- necessary because the dump skips cells
  nothing wrote, so a staged `\x00` would otherwise vanish rather than
  print.

  A print *inside a loop* is in class too, which needs more than numbered
  slots: the print count is not known until the loop runs, so the append
  finds its slot at runtime.  A slot holds `value + 1`, so an occupied
  slot is nonzero and an empty one is zero, and `[>]` walks to the first
  free one.  The biased encoding needs headroom above the values it
  carries, or the top of the range wraps onto the empty marker: a *byte*
  cell cannot host it, since `255 + 1` reads as empty, which is exactly
  why it was rejected for `brainfuck → 3D Brainfuck` above.  LaserFuck's
  cells are signed 32-bit per the wiki (unbounded in this interpreter),
  so a printed byte sits nowhere near the top.

  Cell 0 is kept permanently nonzero as a landmark, because a return walk
  has to stop somewhere.  The wiki gives LaserFuck "infinite cells in
  both directions", so there is no left edge to arrive at, and `[<]` halts
  on the first *zero* -- which every cell left of the working region is.
  Without the landmark the walk stops wherever it likes; with it, on a
  known address.  (This interpreter realizes the leftward half of that
  tape by inserting at the front of a list, so a walk that runs off the
  left also shifts which position each value occupies in the dump.)

  This is a widening, not a totality result: what it lifts is the output
  convention, and the rest of the class is untouched (the pointer
  hierarchy, the numeric readers, drift loops, below-cell-0).  One
  divergence is worth naming, since the byte-wrap case already documented
  above now shows differently: a negative cell makes the emitted program
  *hang* rather than answer, at a print and -- as before this change, for
  `-->0+.` -- in the epilogue.  Rejecting those would need a proof that a
  cell stays non-negative through arbitrary loops, which is the unsound
  static value analysis this module has twice removed.

  `Streetcode → LaserFuck` shares the assembler, so it was widened by the
  same change: multi-character generated text now round-trips, and its
  remaining limit is control flow alone.

  *Open.*  `brainfuck → 6-5` caps at 17 loops because its loop markers are
  single characters `0-9A-Z`, two per loop, and the region past `Z` is
  undefined behaviour rather than more labels (see the conformance note
  above).  The Decleq escape applies in principle, an interpreter's loop
  count being independent of its source's -- but the classic 423-byte
  `dbfi` self-interpreter needs 58 loops, 41 over budget.  That is
  evidence, not proof: it does not rule out a ≤17-loop interpreter, and
  6-5's cell semantics would have to be carried inside it.
  `Streetcode → LaserFuck`'s steering restriction is the heaviest and
  least certain; junction graphs compile to structured control flow in
  principle, and LaserFuck has conditional rings.

  Not partiality at all: `BFStack → bf` and `BIO → bf` only reject
  malformed input, `brainfuck → Painfuck` is total, and
  `Basicfuck → bf`'s gates are cell-range restrictions (`r=0~255`,
  constants within a byte) that other ranges would need multi-cell
  arithmetic to lift.
- **Dropped transpilers.**  `nocomment_to_bf` silently dropped NoComment's
  stack/jump/pointer commands (a silent mistranslation); the `6-5 → bf` and
  `Circlefuck → bf` decoders only reversed the forward transpilers' canonical
  form (round-trip-only).

## Lean proofs (kept set)

The Lean project keeps only the proofs of facts the tests cannot establish:
SLOW ACV MAMMALIAN's generator search totality, Factor's Dirichlet-based
prime-search totality plus the encode/decode round-trip
(`extra/lean/esolangs/Esolangs.lean`, `FactorCorrect.lean`), and the
`%^2^-1` two-input boolean wall (`PctBooleanWall.lean`, audited by
`PctWallCheck.lean`).  Every other proof (the ported interpreters, their
equivalence proofs, and the generator correctness proofs) was dropped as
redundant with the round-trip test suite.

Note the scope of the `%^2^-1` wall: `Computes` binds one program across all
four bit combinations and feeds the bits in through `start`'s input list, so
the theorem is about programs that *read* their inputs.  The shipped
generator is parameterized and builds every two-input table, so the theorem
bounds the reading model, not the language.

The default `lake build` target covers only the root `Esolangs.lean`, so a
proof outside it is checked by no automation — the gap that let
`BfMintermCorrect.lean` rot into 35 elaboration errors unnoticed before it
was removed (its subject, the branch-free `_bf_minterm` construction, had
itself been deleted when folding made it unreachable).

No comparable Minifuck theorem is open.  The candidate used to be a
characterization of its *reading* model — exactly the four one-input
functions plus the eight 0-preserving two-input tables — but that statement
is false: a reading construction builds and verifies all sixteen two-input
tables on the shipped interpreter, and the searches that suggested otherwise
were length-bounded well below the 88-148 characters it needs.  See
[`docs/walls.md`](walls.md).  The shipped generator embeds its inputs instead
and builds every table at `n <= 3`.
