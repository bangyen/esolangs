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
  surfaces it (and lets `,[.,]`-style cat loops terminate).  Languages whose
  spec defines EOF behavior follow the spec instead and document it: S*bleq
  reads `0` at EOF (per the wiki), and every other
  interpreter raises `EOFError`.  Malformed programs raise `ValueError` and
  runtime halts raise :class:`HaltError`, never a raw Python exception.
- **Byte input is line-delimited.**  ``io.input_char`` reads a whole input
  line and returns its first character (the rest of the line is discarded),
  so a byte-oriented program needs one line per byte: `,.,.` on ``"A\nB"``
  echoes ``"AB"``, while ``"AB"`` on one line supplies only ``A`` and the
  second `,` raises `EOFError`.
- **Execution is unbounded through the public API.**  `esolangs.run` has no
  step limit: interpreters run until the program halts naturally or loops
  forever.  Suffolk is the sole interpreter that ships with a fixed
  instruction limit, and callers cannot set one through the public API.
- **Forbin's expression-position recursion is still bounded by Python's own
  call stack.**  The wiki specifies no recursion limit.  Forbin's
  *expression-position* calls (`x = f(y)`, where the assignment needs the
  result back synchronously) recurse natively and hit Python's default
  limit — not a documented cap, but not literally unbounded either; the
  language has no realistic program shape that recurses this way (see
  `docs/walls.md`), so this is a narrow, low-impact gap.  **Suptiftam,
  Forbin's statement-position calls, and all of Lamfunc's calls are fully
  uncapped**: their call machinery was converted to an explicit frame
  stack (`_Machine.frames`, replacing native Python recursion for that
  path — see `docs/walls.md`), so a correct, terminating recursion of any
  depth now completes — confirmed by a 300-level chained-function test for
  Suptiftam/Forbin and a 2000-level one for Lamfunc, past Python's own
  default 1000-frame limit.  A genuinely infinite recursion becomes an
  uncaught hang (unbounded growth of `frames`, the same class as a
  brainfuck `+[>+]` tape loop) rather than a wrongly-early `HaltError` or a
  `run_until_halt_or_cycle` catch — that detector compares whole-machine
  snapshots, which a growing frame stack never repeats; see `docs/walls.md`
  for a narrower, unbuilt mechanism that could catch the common case.

## Text generator blockers

| Language | Why it cannot emit arbitrary text |
| --- | --- |
| A Painter Ant | No I/O; prints the visited-grid bounding box (a `#` white / `.` black raster, with the ant's cell as `@` or `o`). Has a general (any-arity) boolean generator; no text generator. |
| ArrowQueue | No output at all; the IP walks the grid and halts, printing nothing. |
| Back | Prints the tape as a number list. |
| BF-PDA | `.` prints the top bit as the `'0'`/`'1'` character, so the output alphabet is just the two digits. |
| Bitdeque | No I/O in the spec; this interpreter prints the deque contents as numbers when the program ends. |
| COD | The ``---`` sink prints the cod's value as a decimal integer with no separator, so only digits are spellable — the same output-alphabet wall as Jaune. Has a parameterized boolean generator (its leaves print a single `0`/`1`, which the digit alphabet does spell); no text generator. |
| Circuit Diagram | The ``:`` output emits its gate's value as a bit string, so the output alphabet is just `'0'`/`'1'` — Flowchart's wall, reached by a different route: here the bits are a whole generation's worth per output rather than one per node, but nothing in the spec turns them into a byte. Has a boolean generator; no text generator. |
| Flowchart | The only output node emits one bit, and the byte-packing convention the other bit-output languages use (Clockwise buffers seven bits and flushes a character) cannot apply: the wiki's truth machine reads one bit, writes one bit, and halts, so under any packing its single output bit would never flush and the example would print nothing at all. Character-per-bit is forced by the spec's own example, and it is what makes text output unreachable. Has an uncapped boolean generator; no text generator. |
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
| 123 | The `3`-jump is nearest-match, not bracket-matched, so TRUE always re-runs the segment already executing rather than reaching an independent branch target — and `1` flips the bit under the pointer before moving, so navigating from the post-read position (0) to the write position (-2) corrupts the byte's MSB en route. Only the four one-input functions are reachable via runtime `,` reads (too trivial to keep as a generator); a structured search found no two-input function under either bit-encoding. A parameterized generator (embedding each input at compile time, as WII2D's does) was assessed and is also walled, on a third mechanism: it does clear both mechanisms above and reaches real input-dependent behavior (an AND by emission), but location 0 is both the byte's MSB and the only cell the pointer wrap returns to, so the loop that builds a byte is the one that would have to be stopped to print once, and `3` cannot stop it -- no program over `1`/`2` to length 8 prints exactly `"0"` or `"1"`. Full argument in `docs/walls.md`. |
| %^2^-1 | Only control flow is `t` (rewind on a nonzero accumulator); a whole-program while loop that cannot count passes. No program that *reads* its inputs computes any two-input function (proved in Lean), but the shipped boolean generator is parameterized and builds all sixteen: it embeds the bits, composes one affine setter per input into a product-weighted accumulator, and prints with `l`, which spells the accumulator in decimal so `0`/`1` need no branch. The setters are derived from the table (each column's slope is read off it, and the offsets are then solved) rather than searched. Total at `n <= 2`.  Above two inputs a second construction takes over, the **subcube cascade**: the accumulator is loaded with 1 (`ips`) and passed through one setter per input, the identity (`pp`) where the bit matches the pinned literal and an erase (`'p`) where it does not, so the accumulator survives as 1 exactly when every pinned bit matches; inputs the conjunction does not mention are the identity on both branches.  Appending `ips` again maps the 0/1 result to `1 - r`, so complements are three characters more.  Both branches are two characters, so nothing leaks through `len()`, and a program is `2n + 4` characters (`2n + 7` complemented) at any arity.  This lifts the old `n <= 2` cap for every conjunction or disjunction of literals -- AND-`n`, OR-`n`, NAND-`n`, NOR-`n` and every subcube -- with no search: 48 of the 256 three-input tables and 154 of the 65536 four-input ones, against the nothing the cap allowed before.  Other tables are still rejected rather than risking a wrong program. |

## Generator caps (shipped)

| Generator | Cap | Wall or liftable? |
| --- | --- | --- |
| NoComment | `n <= 8` | Genuine wall: the `s` skip is byte-indexed, capping every jump at 255. |
| Polynomial | instruction-count cap, not `n`-driven: a table needing more than 138 instructions under *both* constructions is rejected, so well-merging tables render at any width (parity through `n == 8` at 106 instructions) while random dense tables refuse from `n == 6` | Performance cap: the interpreter recovers instructions by factoring the polynomial, and that is what becomes impractical — so the bound is on instructions, not inputs. This row used to claim `n <= 4`, which measured the wrong thing: the old `n`-gate refused parity from `n == 5` even though it costs only 13 instructions per input. Adding the residual-merge state machine alongside the decision tree (the shorter of the two wins) made the real bound visible. |
| %^2^-1 | all tables at `n <= 2`; conjunctions and disjunctions of literals at any `n` (48/256 at `n == 3`, 154/65536 at `n == 4`) | Partly lifted, and the rest is **open, not walled**.  The derived path composes one affine map per input into a shared value, which forces each cofactor of the table to be constant or an affine image of one shared function -- only 88 of the 256 three-input tables satisfy that, which is why it capped at two.  The subcube cascade escapes that constraint by making the *erase position* input-dependent, a branch realised arithmetically in a language whose only jump target is 0.  What is not yet reached is tables needing an OR of several disjoint subcubes: chaining indicator gadgets needs a running total to survive a gadget that erases, and there is one register -- but that is an argument about one gadget shape, not a proof about the model.  Bounded searches over repeated setters reached about 100/256 at `n == 3` and were still climbing when stopped (window `|acc| <= 5..8`, offsets `+/-3`, depth `<= 3`), so the true reachable set is larger than what ships.  The printing tail is likewise only bounded, not settled: reset-free tails are affine hence injective and so separate exactly two values, and a sweep of every tail to length 10 over inputs `[-30, 30]` never separated more than two -- but the over-3003 reset merges values into one class, and a longer tail that drives one class past the reset while landing another on 1 is not excluded.  Reaching the reset needs about seven doublings before any adjustment, so such a tail would live past length 10 if it exists.  %^2^-1's own NOT is 36 commands and a length-8 sweep missed it, which is the precedent for not reading this sweep as a wall. |
| 6-5 | `n <= 5` exact; past that, tables whose folded tree needs more than 35 branch labels are rejected (AND-6 and other well-folding tables *do* render) | Genuine wall, and the 35 is the **language's** number, not the generator's encoder: the [wiki spec](https://esolangs.org/wiki/6-5) defines operand notation as "Numbers beyond 9 denoted using letters. (A=10, B=11 etc.)", and letters are `A..Z` — so `0..9A..Z` names 1..35 and an `8n` jump cannot address a marker past the 35th. Labels also cannot be reused: `8n` resolves its target by scanning the token list *from the start* for the n-th `4`, so a label is a global ordinal fixed by position, never a scoped name a finished subtree could free — which makes the budget a total-standing-nodes count rather than a tree-depth one. The decision tree spends one label per internal node its constant-subtree fold leaves standing; the fold's worst case is an alternating table, which folds nothing and spends `2**n - 1` — 31 at `n == 5`, so every table renders there; 63 at `n == 6`, so refusals begin. What survives past `n == 5` is tables that fold hard: ~1% of random `n == 6` tables, but structured ones like AND-`n` at any width (they need only `n` labels). The former arithmetic fallback was retired — it needed the table as a single buildable integer, which confines the ones to low indices, which leaves the rest constant, which folds well inside the budget, so it never covered a table the tree could not. A lift built on operands past `Z` (`[` = 36, `{` = 68) was tried and **reverted**: those decode only through an unguarded `ord(c.upper()) - 55` fallthrough in this repo's interpreter, which is undefined behaviour rather than a language property — see `docs/walls.md` and the conformance gap below. |
| ZTOALC L | every table, bounded only by size: the anchor table reaches 1132 commands and the emitted program must stay under the `2**22` line gate | Not a capability wall. The generator constructs a branch-free array lookup -- the row index is built by double-and-add (`s += s`; `s += x{i}`, no multiply needed), the table is one-hot encoded into a `2**n` array, and `t[s]` selects the answer -- placed on a Collatz trajectory, which is collision-free because a trajectory visits distinct values until it reaches 1. The former "dense non-symmetric `n >= 4`" wall fell with the tree it was a property of; see `docs/walls.md`. Sparse tables reach further than dense ones, since the array init is one command per selected row. |
| Minifuck | `n == 2` complete (all 16 tables, interpreter-verified); `n == 3` partial -- eight of the fourteen orbits, the other six raising after about two minutes | Liftable, and the weakest generator here: it is a *search* over three routes and two embed separators, so the reach is set by its depth caps rather than by an argument, and the n == 3 failures are cap exhaustion rather than unreachability. Structured tables (constants, AND, OR, parity, majority) do build, so hand-picked samples overstate coverage badly. The route a fix would take is a *construction* in wii2d's shape -- see `docs/walls.md` for which piece of it does not yet compose. |
| WII2D | `n <= 4` exact (exhaustive through three, sampled dense at four); symmetric tables of any arity via closed forms; dense non-symmetric sampled built at `n == 5` and `n == 6`, rejected from `n == 7` | **Cost guard, not a wall — liftable by paying build time and width.** The `n == 7` refusal is `_WII2D_MAX_INDEX_DOMAIN = 32`, a constant compared against the decode domain `2 ** (n - 1)`, and it fires *before* `_wii2d_decode` is ever called — so the refusal never established that anything fails. It does not: sampled 64-point decodes fold correctly, and with the constant raised to 64 a dense non-symmetric `n == 7` table builds in 1.54s (13372 characters, 8 rows x 6673 columns) and is **interpreter-verified on all 128 input combinations**. What the guard actually buys is a bounded build: at the shipped beam width, five random patterns per domain measured median/worst decode lengths of 51/96 cells at `D == 16`, 1245/2686 at `D == 32`, and 46385/131433 at `D == 64` — where four of five patterns took 0.7-17s but the fifth exceeded a 120s budget. The tail, not the width, is the reason to keep the default: raising it trades a clean refusal for an occasional multi-minute build. A second knob a caller should weigh: the fold squares, so peak `|acc|` over all input combinations was 9 bits for a sampled dense `n == 5` table and 16 for a sampled `n == 6` one, but ranges from 27 to 45766 bits across five sampled `n == 7` decodes (tracking decode length, not arity; the interpreter-verified build reaches 1840). The wiki spec states no accumulator bound and this interpreter uses arbitrary-precision integers, so wide builds rest on spec silence rather than on ground truth — though the dependence is not new at `n == 7`, since shipped `n == 5` already passes one byte. Symmetric tables never reach the check (majority-of-12 is 397 characters, instant). The earlier "counting bound rules out representing every table" claim is withdrawn — it bounded a fixed *pool* of short op strings, while the fold *builds* a decode of whatever length the pattern needs; completeness past the exhaustively-tested `D == 16` is open, not refuted. |
| Factor | program-size cap, not `n`-driven: sparse tables stay under the cap well past the dense ones — constant-0/1 at any tested `n`, and AND-`n` (one `1` in the table) through `n == 5` — while dense tables refuse from XOR4 up | Liftable by host config: the encoded integer's decimal length is checked against `sys.get_int_max_str_digits()` (CPython's int-to-string DoS guard, default 4300 digits) before rendering — the Factor *interpreter* parses its program the same way, so a caller who raises the process-wide limit gets both the generator and the interpreter working past it. |

Removed for being trivial: the boolean generators for Home Row (`n <= 2`) and
Minifuck (`n <= 3`, 0-preserving two-input only) were dropped — their caps
left them able to express only a small fraction of the two-input boolean
functions.  Their languages and text generators remain; see `docs/roadmap.md`.
Both were later rebuilt.  Home Row's is a closed-form construction
(binary-pack the inputs into an accumulator, then walk a linear equality
chain) with no `n` cap at all.  Minifuck's is parameterized: the old cap was
a property of *reading* the inputs, and embedding them instead lifts it, so
the generator now builds every two-input table rather than the 0-preserving
half.  See `docs/walls.md` for both.

The parameterized no-input generators embed every input exactly once rather
than re-embedding a bit at multiple decision nodes, mirroring how an
input-capable language reads each input once per run.  `nocomment` and
`bfpda` were previously counted as exceptions (embedding each input's
complement too), but neither actually needed it — `nocomment` computes the
complement from the bit at runtime, and `bfpda`'s second push is a
bit-independent constant, not a complement.  The per-language reasoning
is in [`docs/walls.md`](walls.md).

## Interpreter conformance gaps

Known places where an interpreter here is more permissive than its language's
spec.  These are **not** capability findings: a generator must not build on
them, because behaviour outside the spec is undefined rather than available.

### 6-5: `num` accepts operands the spec does not define

The [wiki spec](https://esolangs.org/wiki/6-5) defines operand notation as
"Numbers beyond 9 denoted using letters. (A=10, B=11 etc.)", so a `7n`/`8n`
operand is `0..9` or `A..Z` and its value is `0..35`.  The interpreter
instead decodes with an unguarded arithmetic fallthrough and validates
nothing:

```python
def num(char: str) -> int:
    if char.isdigit():
        return int(char)
    return ord(char.upper()) - 55
```

Three ways that exceeds the spec:

- **Values past 35 become addressable.** `[` decodes as 36, `{` as 68, DEL
  as 72, and the range continues indefinitely.  Nothing in the language
  defines a 36th marker as a jump target.
- **The decode is not injective.** `.upper()` folds case, so
  `num("a") == num("A") == 10`; punctuation aliases onto digit values too,
  with `num(":") == 3`.  Two distinct program texts become the same program.
- **It is unbounded below.** `num("\n") == -45` and `num(" ") == -23`, and
  no check rejects them.

The interpreter's own docstring meanwhile states a *narrower* contract than
the spec — "Decode a 6-5 operand digit: 0-9 literal, A-F hexadecimal" — so
the documented contract, the spec, and the behaviour are three different
things.

**Audit of what we actually ship.** Both examples
(`examples/hello-world/6-5.txt`, `examples/boolean/6-5.txt`) conform, with a
maximum operand of 8; all 276 boolean programs the generator emits at
`n <= 3` conform, also topping out at 8; and `bf_to_six_five` conforms
through 17 loops.  The **one** shipped path that depends on the
non-conforming region is the BF-to-6-5 transpiler at exactly 18 loops: it
allows "18 loops (36 markers total)", but only 35 markers are addressable,
so the 18th loop's end label is emitted as `8[` (operand 36) and the jump
executes whenever that loop is entered.  Its cap is therefore off by one
against the spec — the conforming maximum is **17 loops**.  (This corrects an
earlier note in this repo's history claiming that cap was *liftable* by
reading operands past `Z`; it is the reverse — the cap is already one too
generous.)

**Why no fix is applied here.** A conforming `num` would reject anything
outside `0..9A..Z`, which is a contained guard, but it cannot land alone:
it would immediately break the 18-loop transpile above.  The two changes are
one unit, and a fix would touch the loop-count constant and the "18 loops
(36 markers total)" docstring in `src/esolangs/tools/transpilers.py`, the
guard in `num` plus its docstring in
`src/esolangs/interpreters/tape_based/six_five.py`, and
`test_six_five_loop_cap` in `tests/tools/test_transpilers.py` (whose
rejection threshold moves from 19 loops to 18).  Deciding whether 6-5
programs using undefined operands should hard-error is a behaviour change
for callers, not a bug fix, so it is recorded here rather than made.

## Divergent example outputs

`examples/boolean` holds one committed program per boolean generator, and
the bar is that the answer must be *recoverable from what the program
prints* -- not that the program prints the answer and nothing else, since
several of these languages have no output instruction at all and dump
their state at halt.  Three cases stay divergent for reasons no
*generator* change reaches:

- **state dump around the answer** (`back`, `minsky-swap`, `ram0`) -- no
  output instruction, so the answer arrives at a fixed position inside a
  dump of the machine.  These have no way to suppress the rest: Back's
  cells are bits, and the register dumps print unconditionally;
- **a painted grid** (`a-painter-ant`) -- the grid *is* the output, and
  the answer is which leaf the ant rests in;
- **no output at all** (`arrowqueue`, `point-break`) -- the answer *is*
  termination: the program halts for a 0 and loops forever for a 1, so
  only the halting branch can be committed.

The notes on each example carry the explanation.

One caution for anyone re-surveying example coverage: the example stems
are display names lowercased with spaces as dashes (so `BF-PDA` →
`bf-pda`), not language ids (`bf_pda`), so a naive `id not in stems`
check still reports BF-PDA as missing.  It has an example.

## Assessed and rejected

Languages from the wiki that were assessed against the admission criteria
and did not make the repo — whether they were never implemented (the
roadmap's fell-through) or were removed after being implemented.  The
viable candidates are in `docs/roadmap.md`; the full rationale for each
verdict is in the commit history.  ``(removed)`` marks languages whose
interpreter, generator, and tests were deleted from the repo.

- **2 Bits 1 Byte** (removed): joke; single-byte program, no text or boolean generator, externally implemented.
- **2dFish** (removed): its `(...)*` capture-and-print makes its true generator floor a literal-embed (not the shipped delta-encoder, which only disguised this), and its boolean generator was separately walled as affine-only with no total once-embedding construction; both together match the same criterion The Temporary Stack was removed under.
- **Aaargh++**: 4D work-in-progress with a partial spec.
- **Albabet** (removed): straight-line two-register accumulator; no conditional at all (only reset/increment/copy/multiply/print), so no boolean generator.
- **ALT-4**: stack-based concurrent language with no input or output commands at all.  Baking input into the program is not disqualifying — it *is* the parameterized convention, and the wiki supplies both an infinite loop (`00110`) and a truth-machine (`01010`, prepend `0` for input 1), so a termination-convention generator is the natural fit, on the same footing the Point Break exception cites (a wiki-defined truth machine).  What is unbuilt is the general construction: a single file's stack holds only zeroes, so it is one unary counter with an emptiness test, and an arbitrary table needs a decision tree over that.  Separately, `2` multithreads by *filename*, which is the file/OS-based I/O the criteria exclude — a generator can avoid `2`, an interpreter cannot.  Reopened as a candidate pending both.
- **ASCII art** (removed): brainfuck with an art alphabet; a trivial reskin.
- **Binary ///**: stub with no usable specification.
- **Bitwise Cyclic Teast**: work-in-progress, interpreter still in development.
- **Brainpocalypse** (removed): no input; invented dump and a one-bit halt-vs-loop wall; externally implemented.
- **Chainlang**: spec its own author describes as unfinished.
- **Conveyor**: stderr-only output, and no input command.  The output objection is not by itself decisive — `HALT`, a jumper that otherwise "loops back to the conveyor", and `IFEZ`/`IFGT` give the halt/loop distinction a termination-convention generator needs, which uses no output at all.  Still rejected, on spec stability rather than I/O: the page leaves its own ROT13 example unwritten and gates commands behind unexplained privilege tiers (`(Supervisor+)`).
- **Cortex language 3A**: its 8 real primitives (`&`/`$`/`*`/`~`/`'`/`:`/`[`/`]`) are a clean brainfuck-like tape machine, but the language's `;`-prefixed commands are not composable — the wiki assigns them by table lookup to whole canned "popular problem" programs (`;&` is literally specified to *be* Hello World, `;'` a truth-machine, `;$` a full brainfuck interpreter reading its program from user input, `;[` a Mandelbrot set, etc.), so a faithful interpreter would mean hardcoding ~16 opaque special cases rather than a general computational model; treating `;` as a no-op instead contradicts the spec's own worked examples (`;&` would reduce to a bare `&`, not a working Hello World).
- **Crement**: self-modifying, no I/O.  Having no input to branch on is not the blocker — the parameterized generators embed the bits instead of reading them, and Crement is Turing complete on-page (a two-counter Minsky reduction), branches with `JUMP` on a data field's sign, halts by running past the last address, and loops by jumping backward: Point Break's exact profile (arithmetic + conditional + halt/loop, no output).  It is also step-capable, so the looping side would be decided by state-cycle detection rather than a timeout.  Unlike Point Break the wiki defines no truth machine, so adopting the convention here would extend that precedent rather than follow it — a judgment call to make deliberately.  Reopened as a candidate; no construction built.
- **Dotlang** (removed): its boolean generator was the only one that could
  not embed each input exactly once — Dotlang has no storage, value test, or
  arithmetic, so a decision tree has to re-embed every bit at every junction
  (2**i gates) and its text generator is a plain literal-embed; the
  convention-breaking re-embedding (and the ``{Ci}`` complement placeholder
  it needed) was the workaround for that lack of state, so the language was
  too thin to justify being the sole exception to the exactly-once rule.
  The fork-and-kill construction that made it work is recorded in the
  `docs/walls.md` ledger entry.
- **DSDLAI** (removed): trivial Dig reskin with a random death chance; non-deterministic.
- **Earfuck**: trivial brainfuck reskin (notes for instructions).
- **Eso2D**, **Jumplang**, **brainfunc**, **Minimal operation language**, **Yaren**, **2KWLang**: wiki-categorized Implemented with documented external interpreters; not a gap.
- **EXCON** (removed): straight-line 8-cell bit pool; no conditional at all (only reset/flip/pointer/print), so no boolean generator.
- **Fourfuck**: incomplete, a stub with a couple of commands.
- **Gate**: a wire/logic-gate circuit whose spec does not define the two commands a generator needs.  Having no input command is *not* the blocker — it has real output (`(`), constants (`#`/`_`), and a value-testable branch (`+`), which is the profile the parameterized (input-by-substitution) generators are built for, and the letter labels would satisfy the once-embedding rule.  The blocker is that the page never exercises either command: `+` appears in **none** of the nine worked examples, so nothing pins the branch geometry a decision tree would rest on (where the signal resumes after going up/down, and what becomes of the wire it left), and no example emits output at all — the only two `(` occurrences on the page are prose (`not(A)`, `NOT(NOR)`).  The `<` operator is defined only by an image whose entries are self-referential (`&` yields `B & B-1`, `X` yields `B X (B X B)`, with `B` undefined), propagation and gate-evaluation order are unspecified, and OSC's `1010...` is the sole stated output, so there is nothing to derive the gaps from in the way Flowchart's examples pinned its four.  Fails the complete-spec criterion, not the generator-story one; there is no talk page to resolve it.  **Circuit Diagram** is the alternative in the same genre.
- **Gravity**: non-computable evolution; nothing verifiable.
- **HaltJS**, **MangularJS**: JavaScript subsets; a faithful interpreter is a whole JS engine, not a file-based char/line interpreter.
- **Huf** (removed): straight-line two-register accumulator; no conditional at all (only reset/increment/multiply/print), so no boolean generator.
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
- **The Temporary Stack** (removed): its text generator is a literal-embed (the text is pushed as a `*` string literal), and its boolean generator was walled — the auto-drain's `front - 1` output can't be `'0'`/`'1'` and there is no input-dependent branch. Under the tightened generator-story criterion (a literal-embed text generator needs a boolean generator), that made it inadmissible; the full wall argument is in `docs/walls.md`.
- **Trash** (removed): advance-to-next-prime gadget; can never print `1`.
- **Uack**: total; no output.
- **Vandevelo**: input-only, no output at all — but a termination-convention generator needs no output, so that alone no longer settles it.  It is the strongest of the reopened cases: `Inp` is *real* input (no substitution needed), `::` is JavaScript `&&` and the `-!>`/`~!>` forms negate, so AND-with-NOT is functionally complete and there is no affine ceiling of the kind that walled 2dFish; the wiki's own truth-machine already answers by termination, using the self-referential `2 -> 2?` as its loop.  The open question is hang detection, not expressiveness: the loop is lazy self-reference rather than a revisited machine state, so state-cycle detection may not apply and the wall-clock backstop would have to carry it.  Reopened as a candidate; no construction built.
- **Varigen**: explicitly "uncomputable" joke language.
- **Welcome To...**: work-in-progress.
- **XENBLN**: 256 commands, most unassigned, with the command list split across a subpage; not a complete or stable spec.
- **Your Time Is Up**: random rule choice, no I/O; nondeterministic.
- **Zfuck**: I/O is the initial/final tape state, not char/line I/O.
- **｛｝**: family of eight levels; levels 1-2 are uncomputable, levels 3-7 have no I/O, and the only I/O-capable level (8) is a literal brainfuck reskin.

## Cross-check removals

Seven `extra/` cross-checks (Rust and RISC-V ports) were removed for not
meeting the independent-and-broad bar — no generator, or a corpus-only
cross-check that added nothing over the round-trip tests.  The languages
themselves mostly stayed; the full reasoning and the per-cross-check list
is in [`docs/walls.md`](walls.md#cross-check-removals-why-seven-were-dropped).

The remaining eight Rust cross-checks were then removed outright, along
with the cargo toolchain and `scripts/verify_extra_generators.py`: six
were written alongside the Python interpreters they checked (so their
agreement was not independent evidence), and retaining the two that were
genuinely independent would have kept the full toolchain cost for a
fraction of the coverage.  `extra/assembly` stays — it shares its
toolchain with the RISC-V compilers in `src/esolangs/compilers/`.

## Hang detection

Wall-clock timeouts (SIGALRM, instruction-count caps) bound hanging
programs by default; deterministic, step-capable machines instead get an
immediate cycle-detection proof (`esolangs.vm.run_until_halt_or_cycle`).
Which interpreters are covered, why a few stay on the timeout (random
headings, no `snapshot()` yet), and the `pytest --cov` deadlock this also
sidesteps are in
[`docs/walls.md`](walls.md#state-cycle-detection-coverage-hang-detection-without-a-wall-clock-timeout).

## Transpiler walls

Transpilers exist where languages share a semantic core (through brainfuck,
and the one direct pair `Decleq → S*bleq`).  Direct transpilation between
languages with no shared core is a full runtime-in-a-language, not a program
rewrite:

- **OISC-to-OISC (S*bleq → Decleq; Decleq ↔ AddSubJump).**  Both
  self-modifying-memory OISCs share the "≤ 0 branch", and `Decleq → S*bleq`
  ships, but neither has dynamic instruction dispatch in general: S*bleq
  cannot express Decleq code that re-reads a written cell as an operand
  (self-modifying code; rejected), and ASJ's only conditional is
  ``dest = dest ± op`` by a fixed operand.  A general total transpiler is
  therefore not expressible; the partial classes would be silent-droppers.
  Documented as research-level future work in `docs/roadmap.md`.
- **2D-to-2D.**  No two 2D languages share a model: Dimensional is a
  pointer-hierarchy tape, LaserFuck mirror-driven control, ABCDrection a
  Boolfuck bit tape with a queue.  Even the two bf-tape ones (Dimensional,
  LaserFuck) differ in control flow.
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

Note the scope of the `%^2^-1` wall, which is the same scope the Minifuck
statement carries: `Computes` binds one program across all four bit
combinations and feeds the bits in through `start`'s input list, so the
theorem is about programs that *read* their inputs.  The shipped generator
is parameterized and builds every two-input table, so the theorem bounds the
reading model, not the language, and it needed no change when that generator
landed.

`BfMintermCorrect.lean` was removed for both reasons at once: its subject,
the branch-free `_bf_minterm` construction, was itself deleted when folding
made it unreachable (`brainfuck` is now just `bf_tree`), and the file had
rotted into 35 elaboration errors -- reaching the main theorem -- because
nothing built it.  The default `lake build` target covers only the root
`Esolangs.lean`, so a proof outside it is checked by no automation; that is
the gap the removal exposed rather than the proof's own failing.

The one open theorem, if more Lean work is ever wanted, is the Minifuck
boolean reachability characterization: a language-power statement (exactly
the four one-input functions plus the eight 0-preserving two-input tables),
not a generator-correctness proof -- the same shape as the `%^2^-1` wall,
which is the worked precedent for it.  Note the scope: that statement is
about programs that *read* their inputs.  The shipped generator is
parameterized and builds every two-input table, so the theorem bounds the
reading model, not the language.
