# Limitations and ruled-out ideas

What the generators cannot do, and the assessments that concluded an
approach is not viable (or only partially viable).  Completed work lives in
the commit history; this file records the walls, the negative results, and
the reasoning behind them.  Genuine future work is in `docs/roadmap.md`, and
the criteria for assessing a candidate language are in `CONTRIBUTING.md`.

The glanceable tables below name every blocker; the appendix at the bottom
keeps the full per-language argument for each.

## Interpreter conventions

The interpreters share a few behavioral conventions, so `esolangs.run` is
predictable across languages:

- **Empty programs are a no-op by default.**  An empty (or blank-only)
  program produces no output, unless the language structurally requires
  content to start — an initial direction (2dFish), a Collatz seed line
  (ZTOALC L), or a program grid (Circlefuck, BF-PDA, Suffolk, Dig, Back,
  Clockwise) — in which case it is rejected with a clear `ValueError`
  (usually ``"... cannot be empty"``, or 2dFish's
  ``"program does not set an initial direction"``).
- **Exhausted input raises :class:`EOFError` by default.**  A program that
  reads past the end of `stdin` is almost always a bug, and the loud error
  surfaces it (and lets `,[.,]`-style cat loops terminate).  Languages whose
  spec defines EOF behavior follow the spec instead and document it: S*bleq
  and Movesum read `0` at EOF (both per the wiki), and every other
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

## Text generator blockers

| Language | Why it cannot emit arbitrary text |
| --- | --- |
| A Painter Ant | No I/O; prints the visited-grid bounding box (a `#`/`.` raster). |
| ArrowQueue | No output at all; the IP walks the grid and halts, printing nothing. |
| Back | Prints the tape as a number list. |
| Bitdeque | Prints the register/deque contents as numbers. |
| Grapheme | Strings cannot contain `E` (terminates stringmode) and there is no concatenation, so even "HELLO" is unspellable. |
| Kak | Prints the tape as a `0`/`1` bit-string; exact bytes are unspellable. |
| Lightlang | Prints only the single bit as a number. |
| Minsky Swap | Prints the registers as numbers. |
| Movesum | Prints `n ` (numbers with a trailing space). |
| Number Seventy-Four | Output is `0`/`1`/`H` from a pass-restart model. |
| RAM0 | Prints a state dump. |
| Stun Step | Prints the reached cells as space-separated decimal numbers. |
| Trash | Prints only a prime-advanced number. |

The straight-line generators are also at their length floor — no
per-character encoding can be meaningfully shortened:

- **Sqrt-factorized** (AlbaBet, BIO, huf) build each byte as ``a*b + r`` with
  ``a`` near ``sqrt(byte)``, so they are O(sqrt) not O(byte).
- **Delta- and cell-reuse** (brainfuck, Circlefuck) keep a running cell and
  emit only the difference, so consecutive close bytes cost a couple of
  tokens.
- **Literal-embed** (Taglate, Eval, Between, Dotlang, MyScript, Nevermind)
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
| 2 Bits 1 Byte | Program is a single byte; `JMP`/`ACT` target fixed fields, so there is no value-testable branch. |
| 123 | Single data byte, every read overwrites it; the `3`-jump is nearest-match, not a branch — only one-input functions. |
| %^2^-1 | Only control flow is `t` (rewind on a nonzero accumulator); a whole-program while loop that cannot count passes. |
| A Painter Ant | Prints a `#`/`.` grid, not a `0`/`1`. |
| ArrowQueue | No output and no value-testable branch. |
| Bitdeque | `GOTO N` is an absolute token index that shifts under parameterized substitution. |
| Brainpocalypse | `-`-on-zero rewinds to the program start; re-running the `+` bake increments cells unboundedly. |
| Dotlang | The `W~` warp re-enters the first-match markers, losing branch history. |
| Eval | Nested parameterized trees need backtick escaping the spec forbids. |
| EXCON / Huf | Straight-line, no input, no branch. |
| Grapheme | `V` jumps forward on falsy with no mid-tree halt, so the truthy branch falls through both leaves. |
| Kak | Prints the whole tape, not a single `0`/`1`. |
| Lightlang | `&` skips one character, so a decision-tree node cannot route to a multi-character subtree. |
| Minsky Swap | `~` targets are absolute indices that shift under substitution. |
| Movesum | No conditional; the loop repeats until the array stops changing. |
| Number Seventy-Four | Halt depends only on the front-most output character. |
| RAM0 | `goto` is an absolute token index that shifts under substitution. |
| Stun Step | The loop-back re-runs the code with a shifted pointer, corrupting the bit bakes. |
| The Temporary Stack | The auto-drain prints `front - 1`, which cannot be `'0'`/`'1'`; no input-dependent branch. |
| Trash | Prints only a prime-advanced number; can never print `'1'`. |
| WII2D | The accumulator never affects control flow. |

## Generator caps (shipped)

| Generator | Cap | Wall or liftable? |
| --- | --- | --- |
| NoComment | `n <= 8` | Genuine wall: the `s` skip is byte-indexed, capping every jump at 255. |
| Polynomial | `n <= 4` | Performance cap: exact factorization of huge coefficients is impractical past `n == 4`. |
| Home Row | `n <= 2` | Language cap: the fixed 5x5 torus cannot route `2**n` combinations past `n == 2`. |
| Minifuck | `n <= 3`, 0-preserving two-input only | Structural wall: the decode suffix fixes the pointer orientation. |
| 123 | one input only | Structural wall: single data byte, every read overwrites it. |
| Circlefuck, ROTfuck, ABCDirection, BF-PDA | total (no cap) | Verified exhaustively to `n <= 3`-`4`, sampled beyond. |

## Fell-through candidates

Assessments of unimplemented languages from the wiki that did not make the
roadmap.  The viable candidates are in `docs/roadmap.md`.

- **Gravity**: particle-collision simulation whose evolution is in general
  non-computable, so no interpreter can be verified against expected output.
- **Earfuck**: a trivial brainfuck reskin that renames each instruction to a
  pentatonic-scale note; too easy to be worth a dedicated interpreter.
- **Conveyor**: multi-worker language with belts, stacks, and a hand, but no
  input command and only stderr output, so it cannot support the repo's
  file-based I/O protocol.
- **Chainlang**: an AI-generated graph-based spec whose own author warns it is
  unfinished ("don't expect it to be perfect").
- **Binary ///**: a stub with no usable specification beyond "only uses `1`
  and `0`".
- **Fourfuck**: an incomplete language whose spec is a stub with only a couple
  of core commands documented.
- **Aaargh++**: a 4D work-in-progress with a partial spec.
- **Bitwise Cyclic Teast**: a work-in-progress with a still-in-development
  interpreter definition.
- **N Refine**: probabilistic self-rewriting OISC with no I/O; also already
  implemented per its wiki page, so it is not a gap either way.
- **something positive**: explicitly uncomputable (its halting depends on
  program equivalence), so no interpreter can be verified.
- **LogicF---**: a joke language whose commands are non-deterministic and
  non-functional (a 2% chance to increment, a 67% chance to throw a
  KeyError, and so on), with no usable protocol.
- **Vandevelo**: input-only, with no output at all.
- **Varigen**: an explicitly "uncomputable" joke language.
- **Not Python**, **2001: An Esolang Odyssey**, **Stu**, **Bias**,
  **Writeover**: joke or vaguely specified languages with no usable
  specification or I/O protocol.
- **Objects In Mirror Are Heavier Than They Appear**, **OpenStreetCode**,
  **Streetcode**, **Unary Filesystem**, **Phile**: particle/map/file- or
  OS-based languages with no portable file-based I/O protocol.
- **Welcome To...**: a work-in-progress.

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
- **2D-to-2D.**  No two 2D languages share a model: 2dFish is a deadfish
  accumulator, Dimensional a pointer-hierarchy tape, LaserFuck mirror-driven
  control, ABCDrection a Boolfuck bit tape with a queue, EXCON a straight-line
  bit pool.  Even the two bf-tape ones (Dimensional, LaserFuck) differ in
  control flow.
- **Dropped transpilers.**  `nocomment_to_bf` silently dropped NoComment's
  stack/jump/pointer commands (a silent mistranslation); the `6-5 → bf` and
  `Circlefuck → bf` decoders only reversed the forward transpilers' canonical
  form (round-trip-only).

## Lean proofs (kept set)

The Lean project keeps only the proofs of facts the tests cannot establish:
SLOW ACV MAMMALIAN's generator search totality and Factor's Dirichlet-based
prime-search totality plus the encode/decode round-trip
(`extra/lean/esolangs/Esolangs.lean`, `FactorCorrect.lean`), and the
self-contained brainfuck-minterm boolean proof (`BfMintermCorrect.lean`).
Every other proof (the ported interpreters, their equivalence proofs, and
the generator/boolean correctness proofs) was dropped as redundant with the
round-trip test suite.  The one open theorem, if more Lean work is ever
wanted, is the Minifuck boolean reachability characterization: a
language-power statement (exactly the four one-input functions plus the
eight 0-preserving two-input tables), not a generator-correctness proof.

## Removed languages

Languages removed from the repo, and why.  The interpreter, generator, and
tests were deleted; the negative result is recorded so the assessment is not
repeated.

- **DSDLAI: removed.**  A Dig variant whose dig commands carry a random
  20-90% death chance (printing "You died." and halting).  It was a trivial
  reskin of Dig (its interpreter delegated to ``dig.run``) with irreducibly
  random behavior, so a program's output was non-deterministic and could not
  be verified against expected output — it failed the admission criteria in
  `CONTRIBUTING.md` (deterministic computable behavior, not a trivial
  reskin).
- **ASCII art: removed.**  Brainfuck with an art alphabet — each of the eight
  commands replaced by a block of repeated characters, and the interpreter
  decoded the blocks then delegated to ``brainfuck.run``.  The transpiler
  pair was a character-to-block string substitution, and the text/boolean
  generators simply ran the brainfuck generators through that substitution.
  It added no capability beyond a visual encoding, so it failed the "not a
  trivial reskin" admission criterion and was removed along with its
  transpiler pair and generators.
- **Keys: removed.**  The program was two lines compared for equality (and
  the absence of ``- _ / \\``), printing "Accept." or "Reject." — no loops,
  no memory, no computation beyond one comparison.  It was a trivial
  comparison gadget rather than a language model, so like Earfuck (a
  brainfuck reskin "too easy to be worth a dedicated interpreter") it failed
  the non-triviality admission criterion.

---

# Appendix: full wall arguments

The detailed reasoning behind the blockers in the tables above — the
negative result and the structural reason it cannot be lifted.  Completed
constructions (the working generators, and how they work) live in the
commit history, not here.

## 6-5 (constant program size is impossible)

A generator that must work for any table has to embed the table, and the
single-integer representation 6-5 requires (the pointer cannot net-advance,
so there is no computed array indexing) costs O(`2**(2**n)`) characters for
dense tables.  A ~2 MB setup guard rejects the `n > 5` and large-`T` region
(AND-n is the pathological case), and runtime is O(x*T) — minutes at the
size guard.  The shipped decision tree stays primary (total through
`n <= 5`); the arithmetic kernel is the fallback for small-`T` tables past
that.

## ZTOALC L (dense non-symmetric n > 3 wall)

All Collatz trajectories converge to the `16, 8, 4, 2, 1` tail, so a dense
full tree like XOR4 has every leaf's tail sweep through another leaf.  For
**popcount-symmetric** tables the generator falls back to a branch-free
*linear* program, which is `2**L` lines (XOR4 is 524,288; gated at `2**22`).
Only dense, non-symmetric tables past `n == 3` still raise `ValueError`;
those need a full `2**n` result table, which would be `2**(2**n)` lines.

## 3x (constant-bit guard skip is unsafe)

A guard that separates differing rows from default rows sharing the same bit
prefix cannot have a "redundant" bit test dropped, because the default rows
share the prefix too — dropping the test would misclassify them.  The sibling
idea (pre-negating stored input bits to halve `not_bit`) remains open but is
marginal.

## Minifuck (0-preserving functions, n <= 3)

The two-input limitation is structural: the decode suffix flips the pool LSB
only when the pointer sits at cell 7, and `[`'s skip always maps bit 0 to
the higher pointer position, fixing the pointer orientation.  XNOR, NAND,
NOR, NOT-b0, NOT-b1, and const-1 were not reachable in the original analysis
(no complemented read-prefix exists to length 11, full-program search to
length 14 finds none, and a re-verification search to length 34 still finds
none).  The n == 4 walker stage additionally cannot reach the 8 distinct
pointer positions a third bit needs.  The single-input case is *not*
0-preserving-bound (a re-verification found NOT and const-1 at lengths
17-18), so the generator covers the four one-input functions plus the
0-preserving two-input tables, and nothing past `n == 3`.

## 123 (four one-input functions)

A decision tree needs the `3` jump, which on a TRUE/FALSE bit jumps to the
*nearest* preceding/following `3` (not bracket-matched), so the only
constructible pattern is "repeat the region before the `3` while TRUE" — no
`3`-based branch exists (a random search finds no NOT even at n == 1), and
the single data byte makes multi-bit state impossible (every read overwrites
it).  The four one-input programs were too trivial to keep, so the boolean
generator was removed.

## RAM0, Bitdeque, Minsky Swap (parameterized template blocked)

These three have value-testable branches and clean setters, but their jumps
are *absolute token indices*: RAM0's digit-`GOTO`, Bitdeque's `GOTO N`, and
Minsky Swap's `~` targets are all fixed positions in the token/command
stream.  The parameterized template's bit setter has variable length (e.g.
RAM0's `Z` for a zero bit vs `Z A` for a one bit; Bitdeque's `INVERT` vs
nothing), so substitution changes the token count and every jump target
shifts — a fixed template cannot be correct for all instantiations.  Only
Back avoids token-index jumps (its `+`-advance condition is positional).

## Eval (nested parameterized trees)

Building a decision tree requires nesting: each subtree must be a string
evaluated with `!`.  This is a **spec** limitation (the interpreter matches
the wiki exactly): the wiki defines stringmode with no way to escape a
backtick or include a literal one, so a pushed string can never contain a
backtick and a nested `!`-evaluated subtree cannot survive more than one
wrap.  The wiki's examples only ever use single-level `!`.

## SLOW ACV MAMMALIAN (general n-bit open)

The n-bit case is blocked by three mutually conflicting constraints:

- `ACCEPT` unconditionally appends the normalized bit to `lst[0]`, and
  consuming that bit needs `ptr == 0`, but routing `SPRINT`s move the
  pointer to a node — so the bit cannot be both read and routed without a
  way to return the pointer to 0.
- The read's clean normalization needs `lst[0][0] == 48` (the `^ 48` base),
  and `SEED` skips empty arrays, so the only constant source is `K SEEDs
  CONSUME` starting from `lst[0] = [0]` — which empties the array, so every
  later constant **accumulates** on the previous one (`42 + 5 = 47`, never a
  clean `5`).  The `[48, C, m]` triple a branch needs therefore cannot be
  assembled in one array.
- `DIGEST` normalizes by XORing the *sum* of `lst[ptr]`, so a bit buried
  among previous bits is only recoverable as part of a sum, and `48 ^ (48 +
  m1 + m2)` is not `m1 ^ m2` when both bits are set.

Re-verified against the interpreter: a search over the branch-free tails
after the `b1`-normalize prefix reaches only the 0-preserving two-input
tables, matching the structural argument.  (Unlike Minifuck, this wall
holds.)

## Dotlang (not viable)

The `W~` warp reads a line and teleports the dot to the *first* `W<bit>`s`
marker in the grid.  A single-bit program works, but every deeper level of a
decision tree re-enters those same first-match markers, so the branch
history is lost: the second `W~` lands back on the first markers and loops.
The type conditionals (`!?:`) cannot help — input digits are converted to
`int` 0/1, so both bits share the same type — and there is no value
comparison or arithmetic.  Only a fragile direction-routing trick could
express more, and it caps at three inputs before the eight (marker, heading)
states run out.

## Polynomial (numeric root-finding ruled out; caps at n <= 4)

The generator emits exact integer polynomials whose coefficients far exceed
float64's exact-integer range (2**53) once a few instructions accumulate —
`'Hello, World!'` has coefficients up to 10**95 — so every floating-point
solver (high-precision `mp.polyroots`, companion-matrix QR, change-of-scale)
silently solves the wrong polynomial, and a residual-based gate cannot work
(the ill-conditioning ~1e16 makes wildly wrong roots look right).  The
interpreter factors the monic integer polynomial over Z with sympy instead.
That exact factorization defines the boolean generator's practical bound:
`n == 4` (degree 184) factors in ~10s, while `n == 5` (degree 376) does not.

## ROTfuck (rotation defeats a decision tree)

The rotation defeats a brainfuck decision tree outright: a `[ body ]` whose
body is a rotation-encoded loop cannot work, because when the `]` fires its
`[` has rotated away (the skip-path seek needs `q ≡ p+1` while
re-convergence needs `q ≡ p`).  The shipped boolean generator sidesteps the
wall by never looping (a phantom-`]` block whose straight-line body is
position-encoded), which keeps the generator total but makes the programs
long (O(`n·2**n`) blocks, ~1.4s/execution at `n == 4`).

## Home Row (j-guarded-move boolean generator, n <= 2)

`l` loops pair strictly by order, so loops cannot nest and a bf-style
decision tree is inexpressible.  The shipped generator routes with `j`
(guarded moves) instead of loops, which works through `n == 2`.  `n >= 3`
raises: an exhaustive search over `j`-guarded sequences shows no routing
separates `2**n` combinations onto distinct cells of the fixed 5x5 torus
past `n == 2` (the search caps at 6 of 8 combinations).

## Assessed boolean candidates that fell through

- **%^2^-1**: its only control flow is `t` — rewind to the program start
  when the accumulator is nonzero — with the accumulator preserved across
  the rewind.  A program is therefore a whole-program `while` loop, and each
  `n` in the body consumes one input line, so a `t` loop iterates over the
  input bits.  It cannot count them: there is no increment-by-1 for an
  arbitrary value, and a counter in the rewind path grows without bound (the
  `acc > 3003` reset only fires on huge magnitudes), so the loop stops only
  when a body pass ends with `acc == 0` — a uniform predicate that cannot
  tell pass 1 from pass n.  The all-ones row of any truth table therefore
  either stops the loop early or rewinds past the input.  Exhaustive search:
  of the four one-input functions only identity and the two constants are
  expressible; NOT and every two-input table fail even at length 8.
- **The Temporary Stack**: the auto-drain is the only output, and it prints
  `front - 1` for the *oldest* stack element when `sum(rest) / 2 > front`.
  An input-dependent `'0'`/`'1'` (48/49) output therefore needs the input to
  select a 49/50 constant, but the only value-to-length conversion — the
  front element popping — requires `front < input / 2 < 24`, so the front is
  at most 24 and prints garbage, while the raw input at the front prints
  `input - 1` (47/48).  Neither is a `'0'`/`'1'`.  Exhaustive search to
  length 5 finds no identity or NOT program, and `\` (while nonempty) never
  terminates except via the fixed 15-command stack reset, so there is no
  input-dependent branch either.
- **WII2D**: the accumulator never affects control flow (`^v<>` set the
  direction, `@` jumps unconditionally to the closest `@`), so there is no
  value-testable branch to route a decision tree on.
- **Movesum**: only `move` (copy) and `sum` (add), with no conditional — the
  loop repeats commands until the array stops changing.  The numeric output
  (always a trailing space) and the addition-only arithmetic cannot express a
  general boolean function.
- **Trash**: its only output is a prime-advanced number — a non-prime start
  prints ``0``, a prime start prints the next prime (3, 5, 7, ...), and no
  leading ``t`` prints nothing — so it can never print a boolean ``"1"`` and
  cannot return a truth-table result even parameterized.
- **Lightlang**: `?` reads a bit (an empty line gives 1, any non-empty line
  gives 0), so a bit is readable — but `&` (skip the next instruction when
  the bit is 1) skips exactly one character, so a decision-tree node cannot
  route to a multi-character subtree.  Only a one-sided AND-like cascade is
  expressible (each level's zero-branch is the fixed ``!&#`` "print 0,
  halt"), not a general truth table; XOR and OR were both searched and
  rejected.  Its ``@`` command is also non-deterministic (a random bit).

## Termination-based convention (partial, not a boolean generator)

A "halt vs. loop forever" convention — the program halts iff the embedded
input bits satisfy the function — was explored for the three languages with
a built-in infinite-loop branch.  It expresses the one-input functions but
no multi-input tree:

- **Brainpocalypse**: `-`-on-zero rewinds and loops, so `-` loops for bit 0
  and `+-` halts for bit 1; but the rewind restarts the prefix and re-running
  `+` increments already-set cells, so multi-input bakes corrupt.
- **Stun Step**: the machine halts iff the current cell is 0 at a pass
  boundary, so `>` (moves only when the cell is nonzero) gives
  halt-for-0/loop-for-1; but the loop-back re-runs the code with a shifted
  pointer, corrupting multi-bit bakes.
- **Number Seventy-Four**: the pass-restart checks the accumulated output
  string (not corrupted by restart), so `0H` halts and `1H` loops; but the
  halt depends only on the front-most output character, so multi-bit trees
  still fail.

No existing boolean generator uses this convention; it would require a new
harness contract (termination as the answer) and still does not unlock a
multi-input generator in any of the three.
