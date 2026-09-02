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
| 123 | **A generator ships; the cap is arity, not expressiveness.** It is parameterized (`2` at location -3 reads real stdin, so a decision tree cannot read its inputs) and answers with the termination convention — halt for 0, a proven loop for 1 — the same one ArrowQueue and Point Break use. All four one-input, all sixteen two-input and all 256 three-input tables are built. The fill is `1` for a one and `2` for a zero, which move the pointer in opposite directions, so displacement after the embeds is `(#zeros - #ones)` and the `-4 -> 0` wrap reduces it modulo four: a tail of `1`s decodes that counter, and `3`'s TRUE-backward re-run supplies the tables the counter cannot reach on its own. At three inputs the bare counter carries only popcount *parity*, which is why `01111110` — TRUE unless all three inputs agree — was the last table to build and needed the `3` gadget. Four-input and wider tables are **rejected**, including those depending on fewer of their inputs: an ignored input still has to be embedded, every fill moves the pointer, and the pointer phase *is* the computed value, so a trailing inert embed shifts the very quantity the plan decodes. Whether a wider construction exists is open; see [`docs/walls.md`](walls.md). |
| %^2^-1 | Only control flow is `t` (rewind on a nonzero accumulator); a whole-program while loop that cannot count passes. No program that *reads* its inputs computes any two-input function (proved in Lean), but the shipped generator is parameterized and builds all sixteen: it embeds the bits, composes one affine setter per input into a product-weighted accumulator, and prints with `l`, which spells the accumulator in decimal so `0`/`1` need no branch. The setters are derived from the table, not searched. Above two inputs a second construction takes over, the **subcube cascade**: the accumulator is loaded with 1 (`ips`) and passed through one setter per input — the identity (`pp`) where the bit matches the pinned literal, an erase (`'p`) where it does not — so it survives as 1 exactly when every pinned bit matches. Appending `ips` maps the result to `1 - r`, so complements cost three characters more. Both branches are two characters, so nothing leaks through `len()`, and a program is `2n + 4` characters (`2n + 7` complemented) at any arity. That covers every conjunction or disjunction of literals — AND-`n`, OR-`n`, NAND-`n`, NOR-`n` and every subcube — with no search: 48 of the 256 three-input tables and 154 of the 65536 four-input ones. A third construction, the **composed-affine derivation**, catches tables that are no subcube: it composes one affine setter per input as the two-input derivation does, and solves them the same way. After two setters the accumulator holds four values that the third maps by one branch per value of the last input, so the even and odd rows are two affine images of one vector — the shared-cofactor law, read backwards. The vector's partition is forced by which rows the table agrees on, two points fix each branch of the last setter, and the first two invert by division. An enumeration over branch pairs stood here until it was replaced by the derivation: it reached the same 86 tables but cost 6.4 seconds for the arity against 0.8, and its programs were longer (median 46 against 39, and no table's is longer now).  What survives of it is the equal-width spelling, since a setter's two branches must share a width or the program leaks its inputs through `len()`. That second point was the binding constraint: `_pad_pair` pads with `pp` and so refuses an odd width gap, and parity-3's witness wants branches of width 6 and 5. A fourth construction, the **threshold ladder**, is the only one that computes *with* the over-3003 reset rather than keeping clear of it: it weights the inputs into a negative accumulator and lets the reset read the weighted sum as a threshold, which is what builds majority-3.  A fifth, the **deep band**, makes three *and* four inputs total by changing the printing command: `l` spells the accumulator in decimal and so needs it to *be* 0 or 1, while `e` prints `chr(acc & 0xFF)`, so a row need only be congruent to 48 or 49 mod 256.  With residues as the target the reset serves once per run of the table rather than once in total — weights are multiples of 256 so every row starts congruent, sorting by the weighted sum turns the table into runs, and each stage wipes a run and parks the survivors back under the limit.  It drops two assumptions a *positive*-ladder band makes. Its ladder is built by *subtraction*, so the whole order sits below zero where the reset cannot fire and the unit budget that stopped the band at three inputs does not exist. And a cut *erases* — every row it wipes lands on zero together, whatever the gaps between them — so only the boundaries *between* runs need a full residue system, which lets rows of one class collide and prices a table by its run count rather than by `2**n`. Collisions admit the popcount ladder, every weight one, on which parity spans `n` units instead of `2**n - 1`. (A positive-ladder band shipped alongside the deep band for a while and was removed once measured: it served no table the deep band does not — 0 of 256 at three inputs, the only arity it reached — and its programs were about four times longer, median 11492 characters against 3144, so it was dominated on both axes.) A sixth, the **fold**, closes five inputs by dropping the weighting altogether: rows start on a rigid ladder, each use of the reset relocates a group by exactly 3004 plus a slack bounded by the gap to its nearest survivor, the doubling `m` regrows gaps past 3004 (without it every wipe caps the spread at 3003 and the groups' cyclic order is provably invariant, so any table whose runs alternate four or more times would be out of reach), and rows of one class merge by landing on a shared value. Only the final two-point gap carries a residue requirement, and its window spans a full residue system. The plan is searched over the relative geometry; the emitted program is mirrored on every row and asserted rather than trusted. Together they build **all 256** three-input tables, **all 65536** four-input ones, and every five-input table tried -- large random samples, parity, every threshold, and the fully alternating 32-run worst case -- each executed on the interpreter on all its inputs at equal fill length; parity is verified through six inputs. Tables no construction covers are rejected rather than risking a wrong program. |

## Generator caps (shipped)

| Generator | Cap | Wall or liftable? |
| --- | --- | --- |
| NoComment | `n <= 11` | Liftable by host config, not a language wall: 255 bounds a single `s` skip, and skips compose, so past eight inputs the generator splits the index into byte-sized summands and walks one staircase each. What binds instead is the interpreter's tape, which the `2**n` output cells plus a guard apron exhaust at `n == 12` against the default 4096 cells — and the wiki requires the memory space to be static but never specifies a *size*. Both `run` and the generator take a `tape` argument: `n == 12` builds and runs at `tape=16384`, and the default stays 4096 because the size is observable through the wrap. Verified by exhaustive interpreter runs at `n == 9`, `10`, and `11`; instrumented runs show no skip amount and no written cell exceeding 255, so the chain is spec-legal. Full argument in [`docs/walls.md`](walls.md#nocomments-arity-cap-the-255-bounded-one-jump-not-a-composition). |
| Polynomial | instruction-count cap, not `n`-driven: a table needing more than 138 instructions under *both* constructions is rejected, so well-merging tables render at any width (parity through `n == 8` at 106 instructions) while random dense tables refuse from `n == 6` | Performance cap: the interpreter recovers instructions by factoring the polynomial, and that is what becomes impractical — so the bound is on instructions, not inputs. |
| %^2^-1 | all tables at `n <= 2`; conjunctions and disjunctions of literals at any `n`; **every table at `n == 3`** — 256/256, was 106, was 86, was 48 — **every table at `n == 4`** — 65536/65536, was 496 — and **five inputs, closed by the fold** — every table tried plans and executes, against the 496 the weighted constructions reach there | Raised, and the rest is **open, not walled**.  The two-input derivation reads one slope per column and does not generalise; the cascade builds only subcubes.  The composed-affine search reaches neither's limit and builds XOR3, which is no subcube.  **What had been binding was not the language but the padding**: both branches of a setter must be the same width or the program leaks its inputs through `len()`, and `_pad_pair` pads with `pp`, closing only *even* gaps.  Parity-3's witness wants widths 6 and 5, so it was refused for an odd shortfall.  Spelling both branches at a shared width instead closes it — 99 of the 100 maps in the grid have spellings of both parities.  The affine path alone reaches 86/256, and that number is **stable** against the parameters (it moved from 84 only when the *witness selection* was fixed, not by widening anything): widening the multipliers (to `±4`, since `mp` is `-2` and `mmp` is `-4`), the offsets (`±12` to `±16`), the spelling depth (7 to 9) and the witness count (4 to 16) each reach no further table.  The path is now **characterized exactly at three inputs**: a table is reachable iff its cofactors on the *last* input are equal, complementary or constant (the shared-cofactor law) and it is not constant — **86/256**, an exact match with all 86 executed on the interpreter, and exactly the law's 88 minus the two constants that earlier paths serve.  An earlier note here said the law and the path *cross*, the search reaching 32 tables the law forbids; that came from testing the law on the wrong input.  Applied to the last input, where the law is actually stated, the containment is clean — **0 tables reached outside it** — and only the two constants separate the law's 88 from the path's 86, and they are served earlier by the cascade.  The `x0 ^ x2` pair was excluded too for a while, and that turned out to be a **witness selection artefact rather than a property of the model**.  The frontier keeps six value vectors per induced partition, and it chose them by arrival — but vectors sharing a partition are not interchangeable, because a later setter translates by `|b| <= 12` and cannot move a distant vector onto the values a tail needs.  For the partition `x0 ^ x2` needs, the six banked witnesses ran `(-24,-24,-23,-23)` through `(-19,-19,-18,-18)` while the usable one was `(-12,-12,-11,-11)`.  Ranking witnesses by magnitude recovers both tables at the same witness count (raising the count does nothing, which is why 84 held at every count up to sixteen), takes the path to 86, and shortens 40 further tables without lengthening any — the two recovered ones go from a 3054-character deep-band program to a 43-character one.  The reachable set is closed under complement and under input negation but **not** under input permutation, which is the setters composing in slot order rather than acting independently.  Permuting would take 84 to 150 of 256, but only by emitting the `{Xi}` out of ascending order, which the name-order invariant forbids; relabelling the setters while keeping emission order does *not* substitute, because slot position is semantic under composition (0 of 66 candidates computed their table).  The necessity half generalises: at four inputs the path reaches 486 tables and **every one** satisfies the law, though sufficiency does not (1042 of the 1528 admissible tables are unreached there).  An OR of several disjoint subcubes, majority-3 the smallest, was recorded here as unreached because chaining indicator gadgets needs a running total to survive a gadget that erases and there is one register — and that note added, correctly, that this was **an argument about one gadget shape, not a proof about the model**.  It does not bind: a fourth construction, the **threshold ladder**, keeps the running total in the accumulator itself and lets the over-3003 reset read it.  Every other path is affine in the accumulator — each command acts uniformly on it, so the rows keep their order and no two can merge unless they already agree — whereas the reset maps everything above 3003 onto 0 and leaves everything below alone, which is a *threshold*, and a threshold on a weighted sum is a majority.  Each input subtracts its weight into a **negative** accumulator, which is what keeps stage one exactly affine (the reset never fires on a negative value), and the stage-one vector is obtained by running the emitted characters rather than by solving the arithmetic separately — modelling them apart is what let an early version claim a program the interpreter then contradicted, since a `pp` hold negates and a magnitude past the limit clamps to 0 on the next command.  That adds **20 tables, including majority-3** (598 characters), each executed on all eight rows with every fill the same length.  The eight ladders that ship are a greedy **set cover**: 256 distinct ladders, 150 productive, and these eight reach all twenty between them — searching the other 248 costs ~50s of build time and finds nothing further (61.5s → 6.6s).  A bound *is* known on this shape: one reset is one threshold, and only **104 of the 256** three-input tables are linearly separable, so widening the ladder grid cannot make it total; deepening the suffix to 14 characters on the shipped ladders reached no further table either, though 24 witnesses do use two or more reset events, so multi-threshold behaviour does occur and is simply not harnessed.  Going past *that* shape needed a different lever, and it turned out to be the **printing command**.  Every construction above prints with `l`, which spells the accumulator in decimal and so needs it to *be* 0 or 1; that is what forces the two answer classes onto two exact values and what the tail bound below is about.  `e` prints `chr(acc & 0xFF)`, so a row only has to be **congruent** to 48 or 49 mod 256.  With residues as the target the reset becomes usable repeatedly rather than once, and the **band construction** makes three inputs total: weights are multiples of 256 so every row starts congruent, sorting the rows by the weighted sum turns the table into runs, and one stage clears each run from the top (the reset can only wipe the largest values).  A stage translates the top band past 3003, lets the reset wipe it, and parks the survivors back **under** the limit — parking them negative stops drift but also stops the next clamp, which is the bug that cost a rewrite.  Nothing is searched: a wiped band thereafter takes the same translations as the survivors, so the parking amount cancels out of their residue gap and the stage's translation is fixed by one congruence, `U ≡ (live − band) − v (mod 256)`; each cut's window is one full residue system wide, so exactly one translation in it qualifies — which is why a sweep of a window had found precisely one working candidate in about two thousand.  Stage counts follow the run structure exactly (2/14/42/70/70/42/14/2 tables at 0–7 stages), and the programs are much the longest here, 8257–14959 characters against the ladder's hundreds, so the path is tried last.  All 256 are interpreter-verified on all eight rows with every fill the same length.  **Three inputs is where this stops, and the reason is a count.**  Distinct row sums need weights that behave like a binary code, so at least `2^n - 1` units, while the accumulator limit allows only `3003 // 256 == 11` — and `n == 4` needs 15.  At unit 256 there are 72 usable weightings at three inputs and **zero** at four.  Dropping to unit 128 or 64 brings weightings back (1464 and 41592 at `n == 4`) but breaks the property the derivation rests on: each cut's window is then only 128 or 64 wide where the congruence needs a full 256, so the required translation falls outside the window.  Measured on random samples: 1 of 400 four-input tables derives at unit 128 and the same at unit 64 (the one that does needs no stages at all), and 0 of 120 at five inputs.  So this is a **counted wall for this construction**, not an untested guess — and not a statement about the language, which is what the **deep band** then demonstrated by lifting it. Both halves of the count are assumptions of the band shape. The unit budget exists only because the band builds its ladder *positive*, so every row sum must sit under the limit at once; subtracting instead puts the whole order below zero, where nothing resets. And distinct sums are more than a table needs, because a cut erases: rows it wipes land on zero together whatever their gaps, so only run *boundaries* need a residue system and rows sharing a class may collide. That takes four inputs from 496 to **all 65536**. The deep band has a budget of its own, and it is **distinctness**, not run count — a first guess that the run boundaries bind was measured and is wrong, since random five-input tables refuse at 5-8 runs where about 11 would fit. Two rows that share a value are merged by the first cut reaching them and can never be separated, so a weighting serves a table only if every collision it forces joins rows of one class. Keeping all rows distinct needs weights growing like a binary code, a span of `(2**n - 1) * 256`: 1792 at three inputs, which fits under 3003, but 3840 at four and 7936 at five, which do not. So from four inputs on, **every** weighting inside the limit collides some rows, and a table builds only if its structure tolerates the collisions forced on it. Four inputs are total because 3840 overshoots 3003 only slightly and enough weightings remain. At five the searched family collides two rows of opposite classes in all 537792 of its weightings for a random table, which is why generic five-input tables refuse — while **symmetric** ones build at any arity, since the popcount ladder spans only `n * 256` and its collisions are exactly the rows a symmetric table already agrees on: parity-5, majority-5 and threshold-5 all build, and parity is interpreter-verified through six inputs. Above four inputs that refusal is now **screened rather than searched**: it cost about eighteen seconds per table (0 of 8 random five-input tables build, 147s to prove it) and a table survives the forced collisions only if it agrees on every popcount class, which is an O(2^n) check. Screening moved a generic five-input build from ~18.3s to ~0.13s; the cost is the shorter program the deep band would sometimes have found for an asymmetric table, which now goes to the fold — near-parity-5 was 5220 characters there and is ~23000 here. Those refusals belong to the deep band, and the **fold** is what then lifted them, by dropping the weighting that costs the distinctness span. It treats the program as a sequence of *relocations*: rows start on a rigid ladder (`acc = -4r`), and every use of the reset moves a group of rows by exactly `3004 + slack` — a landing is at 0 and the line is at 3003, so the jump is structural, and the slack is bounded by the gap to the victim's nearest survivor. Wipes alone provably cannot reorder: each one caps the live spread at 3003, one short of the jump, so a landing never splits two survivors and the groups' cyclic order is invariant — an exhaustive search over wipe-only plans confirms alternating words of four or more runs never contract, which is why every earlier construction had to read the order off a weighting. The doubling `m` is the escape: it regrows a gap past 3004 (residues do not matter until the end, so it is free during the reduction), a landing then splits the doubled gap, and the cyclic order changes. Rows of one class merge by landing on a shared value, which erases their history; once each class is a single point only their mutual gap carries a residue requirement, and the last relocation's window spans a full residue system, so the residue work needs no weighting at all. Plans are found by search (exhaustive under ~20 groups, beam-first above) and the emitted program is mirrored on all `2**n` rows and asserted, then executed on the interpreter. Verified: all 256 at `n == 3` through the fold directly, 150 random four-input and 219 five-input tables (200 random, parity and its complement, majority, every threshold, ten near-parity), each on all its rows at equal fill length. The fold is **not proved total** — the search could in principle give up, though no tried table makes it — and its own bound is the workspace: the row ladder must fit the 6006 values a `p` can traverse, which holds through `n == 10`. Whatever it misses is **unreached, not walled** — the Lean theorem covers the reading model only, and nothing here bounds embedded-input programs in general.  An earlier note here recorded bounded searches "reaching about 100/256 and still climbing"; that figure was never reproduced and no construction behind it survives, so the verified 86 supersedes it.  The printing tail **via `l`** is separately bounded, and for a stated reason: every command acts uniformly on the accumulator, so `s`/`i` translate all rows alike and `m`/`p` scale them alike, and the over-3003 reset merges a class onto 0 but cannot *separate* rows that agree.  A BFS over value-vectors (not program strings) found no tail separating three or more values, with the reset instrumented as firing 1148–7020 times across ~43–55k states — so that zero is a real negative rather than dead code.  That bound still holds and the band construction does not contradict it: it does not separate more values under `l`, it changes the printing command to `e` so that congruence mod 256, not equality, is what has to be arranged. |
| 6-5 | `n <= 5` exact; past that, tables whose folded tree needs more than 35 branch labels are rejected (AND-6 and other well-folding tables *do* render) | Genuine wall, and the 35 is the **language's** number: the [wiki spec](https://esolangs.org/wiki/6-5) defines operands as "Numbers beyond 9 denoted using letters. (A=10, B=11 etc.)", and letters are `A..Z` — so `0..9A..Z` names 1..35 and an `8n` jump cannot address a marker past the 35th. Labels also cannot be reused: `8n` resolves its target by scanning the token list from the start for the n-th `4`, so a label is a global ordinal fixed by position, which makes the budget a total-standing-nodes count rather than a tree-depth one. The decision tree spends one label per internal node its constant-subtree fold leaves standing; the worst case is an alternating table, which folds nothing and spends `2**n - 1` — 31 at `n == 5`, so every table renders there; 63 at `n == 6`, so refusals begin. What survives past `n == 5` is tables that fold hard: ~1% of random `n == 6` tables, but structured ones like AND-`n` at any width. A lift built on operands past `Z` (`[` = 36, `{` = 68) was tried and **reverted**: those decode only through an unguarded fallthrough in this repo's interpreter, which is undefined behaviour rather than a language property — see the conformance gap below. |
| ZTOALC L | every table, bounded only by size: the anchor table reaches 1132 commands and the emitted program must stay under the `2**22` line gate | Not a capability wall. The generator constructs a branch-free array lookup — the row index is built by double-and-add (`s += s`; `s += x{i}`, no multiply needed), the table is one-hot encoded into a `2**n` array, and `t[s]` selects the answer — placed on a Collatz trajectory, which is collision-free because a trajectory visits distinct values until it reaches 1. Sparse tables reach further than dense ones, since the array init is one command per selected row. |
| Minifuck | every table at `n <= 3` (4/4, 16/16 and 256/256, interpreter-verified); wider tables fall through to the searches and may raise | Not a wall at `n <= 3`. The staged route *derives* the `(separator, settle count, suffix, accumulator)` choice rather than searching for it, and derives a whole arity in one pass — measured 0.7s for two inputs and 12s for three, so the first three-input table costs the arity and the other 255 are free. Selection reads the accumulator column **at the read**, not the cell holding the answer beforehand; the two differ because the walk out applies the running prefix-XOR. A table and its complement share a staging, the endgame trying both read polarities. The four tables no bracket run spells are derived by `_rescue`, a family with two `<` inside the run, rather than stored. Past three inputs a missing staging degrades to the searches rather than raising outright, and the four-input ceiling belongs to the staging family rather than to the language — an unshipped two-read chain prototype prints 19.5% of a sample of the tables that family misses, 78 of 78 interpreter-verified; see [`docs/walls.md`](walls.md). |
| WII2D | `n <= 4` exact (exhaustive through four); symmetric tables of any arity via closed forms; dense non-symmetric sampled built at `n == 5` and `n == 6`, rejected from `n == 7` | **Cost guard, not a wall — liftable by paying build time and width.** The `n == 7` refusal is `_WII2D_MAX_INDEX_DOMAIN = 32`, checked against `2 ** (n - 1)` before the chain is walked, so it never established that anything fails. Since 2026-08-31 the construction has **no search left**: the chain takes the first legal junction pair from a fixed catalogue whose last entry (Horner) is legal unconditionally, so the walk is provably total; and the decode takes the single best fold at each step under a fixed ranking, with no beam, no width ladder and no retry. **The doubling trap that motivated the old retry is gone by construction**: it was a consequence of ranking by live count — merging as hard as possible through ever-larger numbers — and the ranking is now magnitude-first, which removes the cause rather than detecting it. `_WII2D_MAX_STATE_BITS` and the second ranked pass no longer exist. The single-candidate rule is **exhaustively verified over all 65536 patterns at `D == 16`**, the widest domain the general path asks for, and all four rankings swept are total there, so the result is a property of the fold algebra rather than a lucky tie-break. What the guard still buys is width: 25 random `D == 64` patterns give a median 1187 cells and worst 2078 (against 4762/19448 under the old search), all under 0.06s; a shortlist screen (`_WII2D_SHORTLIST`) then removed the speculative compression that made per-call cost climb with the domain, flattening it at four compressions per fold. A second knob is that the fold squares, so peak `|acc|` grows with decode length; the wiki states no accumulator bound and this interpreter uses arbitrary-precision integers, so wide builds rest on spec silence. Symmetric tables never reach the check (majority-of-12 is 397 characters, instant). Completeness past `D == 16` is open, not refuted. Measurements in [`docs/walls.md`](walls.md). |
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

CV(N)(C) carries a **third** narrowing, and it is not about width at all:
its `s` parses a line with Python's `int()` after `str.strip()`, both
Unicode-aware, where the assembly is ASCII. `int("4_2")` is 42 because
underscores are legal between digits, and `strip` removes any
`str.isspace()` character including NBSP — so `4_2` and `\xa042` read as 0
compiled and 42 interpreted. Measured, not assumed, and stated rather than
chased: `int()`'s full grammar in assembly buys nothing any program here
reaches. Every ASCII form agrees, signs and leading zeros included. The
general point is that a compiler's agreement domain can be narrowed by a
*library function's* generality and not only by a machine word's width,
which is a place to look that the width rule above does not cover.

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

**Nothing shipped approaches this.**  Measured over the text generators'
programs, the largest integer any compiler emits is **65536** — a tape or
buffer constant in the OISC compilers (addsubjump, S*bleq, decleq); the
byte-oriented ones peak around 93–114, and Container's own containers peak
at 127 at run time.  That leaves fourteen orders of magnitude of headroom,
so this bounds hand-written programs only.  CV(N)(C)'s boolean generator is
the largest runtime value measured anywhere — **6,765,201**, the halt
gadget that squares twice to jump past the end of the program — and even
that is twelve orders of magnitude inside the bound, with a deque holding
one entry per input read (depth 4 at `n == 4`, against 4096) and a function
it never builds.

### Why it is recorded rather than checked or widened

Both fixes were costed and declined.

**A per-site overflow check is unsound at the cheap granularity**, which is
the argument that decides it — not the price.  Two's-complement addition is
exact mod `2**64`, and Container's clamp reads only the *committed* value's
sign, so a rule sum may cross `2**63` mid-tick and come back down with the
right answer.  A container starting at `2**63 - 1` with rules `+1` and `-2`
does exactly that: the transient sum is `2**63`, the committed value is in
range, and interpreter and compiled program agree today.  A check firing at
each `add` would abort that program — narrowing the accepted class to buy
insurance.  A *sound* check needs to track carries across the whole rule
sum, which costs more than the ~2x measured for the naive form (Container's
n=5 boolean program goes 1472 → 2816 instructions).  Forbin's arena abort is
not a precedent: it is one site, guarding a resource programs actually
exhaust.

**Arbitrary precision would not buy totality either.**  No compiler here has
a heap — every one uses static `.data`/`.bss` at compile-time-known sizes —
so bignums mean inventing an allocator, ten times over, on an `rv64i` target
with no hardware multiply (Forth already needs ~50 lines of assembly for
*fixed-width* `mul32`/`divmod32`).  And values are not the only unbounded
axis: RAM0 and Collatz Multiverse already ship a fixed window for unbounded
*index* space, so closing the value axis would leave that one open.  The
inversion is the real objection: these compilers exist for verification
value, and a large untested bignum runtime would make the checker the
buggiest component in the differential.

The one live alternative, if loud failure is ever wanted, is compile-time
rejection of an out-of-range **literal** in the program-text compilers —
Decleq's shape, the only entry reachable with no arithmetic at all
(precedent: S*bleq's unknown-`store` rejection).  It is unshipped because it
trades away acceptance parity: the interpreter runs `2**63 0 0`, and a
compiler that refuses it no longer accepts what the interpreter accepts.

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

## Transpilers: the admission bar, and what it removed

Transpilers here are **total** over their source language: each accepts
every program that language's own interpreter accepts, and agrees with it
on every run the interpreter completes.  The five admission criteria live
in the module docstring of `esolangs/tools/transpilers.py`, which is what
an author of a new one reads.

That bar is the outcome of a survey of the ten transpilers this repo used
to carry.  Six were partial, and the survey found that "partial" covered
two very different defects.  Some rejected out-of-class programs loudly,
which is honest but leaves the caller holding a subset they cannot check.
One did not: `bio_to_bf` named its class only in prose, and a program
outside it was mistranslated in silence.  Since a documented subset gives
a caller no way to test whether their program is inside it, all six were
removed rather than annotated.

**The four that remain, and why each clears the bar.**

- **`Decleq → S*bleq`** is the interesting one, because its wall was
  documented as structural and was not.  The old entry said neither OISC
  had dynamic instruction dispatch; that was wrong about S*bleq, whose `c`
  operand is *indirect* (`ip = mem[c]`) and whose `-1` special is a
  writable instruction pointer.  Its code cells are ordinary memory, so a
  generated program patches its own operand fields to reach a
  runtime-computed address -- indirect load and store.  Those are the
  pieces a runtime-in-a-language needs, so the transpiler emits one: a
  fixed emulator loop over the Decleq image, which rides along as data in
  `[loop | scratch | image]` order, the image last so that Decleq's
  grow-on-write and read-past-the-end-as-zero coincide with S*bleq's.

  A static per-instruction rewrite could never be total here, for a reason
  worth naming: Decleq can compute a jump into the middle of what it just
  wrote, so a target may land in the *interior* of a translated block, and
  only an emulator has no interiors.  The cost is size and speed -- a fixed
  ~1250-cell loop, a few hundred S*bleq steps per Decleq step -- not
  coverage.

  Its residue is the worked example for criterion 3.  Address `-2` is the
  only way an S*bleq program reads input, and it yields `0` both at
  end-of-input (where Decleq raises `EOFError`) and for an *empty* input
  line (where Decleq's reader yields `10`).  A `"\x00"` line yields `0`
  too, so two distinct inputs reach one value; every S*bleq computation is
  a function of the values it reads, so no S*bleq program separates them.
  That is a collision in the target language, not a gap in the rewrite, and
  `test_decleq_empty_input_line_is_a_target_language_collision` asserts it
  rather than avoiding it.

- **`brainfuck → 3D Brainfuck`** was made total by a runtime guard.
  Brainfuck *clamps* `<` at cell 0 while 3D Brainfuck's `s` walks negative,
  and the clamping is load-bearing: `+.<.` prints the same byte twice in
  brainfuck precisely because `<` was a no-op.  No static shift of the
  origin repairs that -- a shift cannot turn a move into a non-move -- but
  3D Brainfuck's array is *three-dimensional*, so a sentinel goes on an
  axis brainfuck's tape never uses.  A prefix `su+dn` writes `1` at
  `(-1, 1, 0)`, and `<` compiles to `su[dnu]d`.  Every observable channel
  already agreed -- cells wrap 0-255 in both, both grow on demand, both
  print `chr(cell)` and raise `EOFError` on exhausted input -- so this one
  is total with *no* residue at all.

  Two silent mistranslations died with it, both witnessed.  The old class
  check was a linear scan of the program text, so it missed dips that only
  happen on a loop's later laps: `++>+[<-].` passed the check and compiled
  to a program that never halts, where brainfuck prints `\x00`.  And
  comments were passed through, though brainfuck's comment characters
  include `n`, `s`, `e`, `w`, `u` and `d`, every one an array move in the
  target -- `+.hello.` printed `\x01\x00` against brainfuck's
  `\x01\x01`.

- **`brainfuck → Painfuck`** and **`BFStack → brainfuck`** are total by
  construction: both are per-command rewrites over a target that is a
  superset of the source's semantics, and neither has a rejection path.

**The six removed.**

- **`BIO → brainfuck`** -- the disqualifying case, and the reason criterion
  4 exists.  Its docstring restricted the transpiler to "programs whose
  registers never reach a nonzero multiple of 256", but nothing enforced
  it.  A BIO program whose register hits 256 and then loops on it
  transpiles without complaint; BIO enters the loop (256 is nonzero) and
  runs forever, while the translation's cell has wrapped to 0, so
  brainfuck skips the loop and prints `\x00`.  Silent mistranslation, in
  the same class as the long-dropped `nocomment_to_bf`.
- **`Basicfuck → brainfuck`** -- gated on cell range, refusing
  `r=0~127` and `r=0~65535`, which are legal Basicfuck.  Enforced, so not
  the BIO defect, but still a subset the caller cannot check.
- **`brainfuck → Circlefuck`** -- the one whose limit is *structural*, and
  so the clearest case for removal rather than repair.  A Circlefuck tape
  **is the program**, fixed at transpile time, while brainfuck's grows
  unboundedly rightward.  The witness is `,[[->+<]>-]`, which carries its
  counter one cell right per decrement and touches `n + 1` cells for an
  input of `n` -- measured tape lengths 4, 9 and 21 for inputs 3, 8 and 20.
  By pigeonhole no fixed-length Circlefuck program holds every input's
  tape.  It rejected 42% of unconstrained brainfuck.
- **`brainfuck → 6-5`** -- capped at 17 loops, because 6-5's loop markers
  are single characters `0-9A-Z`, two per loop, and the region past `Z` is
  undefined behaviour rather than more labels (see the conformance note
  above; a lift into it was tried and reverted).  Acceptance is therefore a
  function of program size: 86.7% at 40 chunks, 19.0% at 60, 0% at 100.
  An interpreter-in-6-5 would sidestep the cap the way Decleq's emulator
  did, but the classic 423-byte `dbfi` self-interpreter needs 58 loops --
  evidence against, not proof.
- **`Dimensional → LaserFuck`** and **`Streetcode → LaserFuck`** -- partial
  on the target's output convention and, for Streetcode, on control flow.
  Both were widened substantially before removal: LaserFuck has no output
  command (it prints its tape once, when the last laser dies), so outputs
  were *staged* into a region the halt dump replays in order, first for
  top-level prints and then, via a runtime append with a `value + 1` bias,
  for prints inside loops.  That work is recoverable at commits `e02e7716`
  and `ccd9fa37`.  What remained out of class was the rest of Dimensional's
  surface -- the pointer hierarchy (`$`, `{`/`}`, `?`/`!`), the numeric
  readers (`d`/`x`), drift loops, below-cell-0 -- which held acceptance to
  27.5% over the full command set, plus Streetcode's drawn control flow.
  A negative cell also made the emitted program hang rather than answer,
  and rejecting those would need a proof that a cell stays non-negative
  through arbitrary loops: the unsound static value analysis this module
  removed twice.

  Worth recording for anyone reviving these: the control-flow wall for
  Streetcode is real and separate.  Streetcode has no loop command; the car
  branches by which exit of a junction it takes, and brainfuck's loop needs
  a state the program returns to once per lap to close its `[`.  A ring
  entered from a junction rejoins the road *past* that junction's square,
  returning under a different heading and different steering latches, so
  the state that decides the loop is never revisited.  A ring that does
  re-cross its test square crosses further gaps on the way, and every gap
  crossing reads the CPth cell -- those reads are junctions too, so showing
  they cannot steer means showing a cell stays nonzero across iterations:
  value analysis, not a rewrite.

- **Earlier drops.**  `nocomment_to_bf` silently dropped NoComment's
  stack/jump/pointer commands (a silent mistranslation); the `6-5 → bf` and
  `Circlefuck → bf` decoders only reversed the forward transpilers'
  canonical form (round-trip-only).

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
