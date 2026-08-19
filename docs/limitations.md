# Limitations and ruled-out ideas

What the generators cannot do, and the assessments that concluded an
approach is not viable (or only partially viable).  Completed work lives in
the commit history; this file records the walls, the negative results, and
the reasoning behind them.  Genuine future work is in `docs/roadmap.md`, and
the criteria for assessing a candidate language are in `CONTRIBUTING.md`.

The tables below name every blocker at a glance; the full structural
argument for each is in [`docs/walls.md`](walls.md).

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

## Text generator blockers

| Language | Why it cannot emit arbitrary text |
| --- | --- |
| A Painter Ant | No I/O; prints the visited-grid bounding box (a `#`/`.` raster). Has a general (any-arity) boolean generator; no text generator. |
| ArrowQueue | No output at all; the IP walks the grid and halts, printing nothing. |
| Back | Prints the tape as a number list. |
| Bitdeque | Prints the register/deque contents as numbers. |
| Grapheme | Strings cannot contain `E` (terminates stringmode) and there is no concatenation, so even "HELLO" is unspellable. |
| Minsky Swap | Prints the registers as numbers. |
| Point Break | No output at all; a program only halts or loops. Has a termination-convention boolean generator (halt for 0, loop for 1); no text generator. |
| RAM0 | Prints a state dump. |

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
| 123 | Single data byte, every read overwrites it; the `3`-jump is nearest-match, not a branch — only one-input functions. |
| %^2^-1 | Only control flow is `t` (rewind on a nonzero accumulator); a whole-program while loop that cannot count passes. |
| ArrowQueue | No output; only the halt-vs-hang outcome is observable, which capped the ring template at AND/OR/threshold functions.  **Lifted:** the shipped decision-tree generator reads the bits from the queue (see `docs/walls.md`). |
| Dotlang | The `W~` warp re-enters the first-match markers, losing branch history.  **Lifted:** the parameterized fork-and-kill generator embeds the bits and kills one of two forked dots per junction, reading the answer from termination (see `docs/walls.md`). |
| Eval | Nested parameterized trees need backtick escaping the spec forbids. |
| EXCON / Huf | Straight-line, no input, no branch. |
| The Temporary Stack | The auto-drain prints `front - 1`, which cannot be `'0'`/`'1'`; no input-dependent branch. |
| WII2D | The accumulator never affects control flow.  **Lifted:** the n-embedding chain decodes the input with accumulator arithmetic (see `docs/walls.md` and `docs/roadmap.md`). |

## Generator caps (shipped)

| Generator | Cap | Wall or liftable? |
| --- | --- | --- |
| NoComment | `n <= 8` | Genuine wall: the `s` skip is byte-indexed, capping every jump at 255. |
| Polynomial | `n <= 4` | Performance cap: exact factorization of huge coefficients is impractical past `n == 4`. |
| 123 | one input only | Structural wall: single data byte, every read overwrites it. |
| A Painter Ant | total (no cap) | Lifted: the piecewise leaf-paint head with WS/NE anchors is exact and cycle-stable for every arity (see `docs/roadmap.md` and `docs/a_painter_ant_generator.md`). |
| Circlefuck, ROTfuck, ABCDirection, BF-PDA, Bitdeque, Minsky Swap, RAM0, Grapheme, A Painter Ant, ArrowQueue, Dotlang | total (no cap) | Verified exhaustively to `n <= 3`-`4`, sampled beyond. |

Removed for being trivial: the boolean generators for Home Row (`n <= 2`) and
Minifuck (`n <= 3`, 0-preserving two-input only) were dropped — their caps
left them able to express only a small fraction of the two-input boolean
functions.  Their
languages and text generators remain; see `docs/roadmap.md`.

The parameterized no-input generators (bio, back, nocomment, bfpda, lamfunc,
bitdeque, ram0, minsky_swap) each embed every input **exactly once**, never
re-embedding a bit at multiple decision nodes — an input-capable language
reads each of its `n` inputs once per run, and the no-input generators
mirror that (see `esolangs.tools.boolean.parameterized` and its regression
test).  Two of them, `nocomment` and `bfpda`, also embed each input's
complement (`{Ci}`) once, because their if/else branch needs a gate that is
nonzero exactly when the bit is zero and neither language can compute that
complement at runtime (`nocomment` has no flip; `bfpda`'s `@` destroys the
bit) — a documented wall, not a superfluous read.

## Assessed and rejected

Languages from the wiki that were assessed against the admission criteria
and did not make the repo — whether they were never implemented (the
roadmap's fell-through) or were removed after being implemented.  The
viable candidates are in `docs/roadmap.md`; the full rationale for each
verdict is in the commit history.  ``(removed)`` marks languages whose
interpreter, generator, and tests were deleted from the repo.

- **2 Bits 1 Byte** (removed): joke; single-byte program, no text or boolean generator, externally implemented.
- **Aaargh++**: 4D work-in-progress with a partial spec.
- **ASCII art** (removed): brainfuck with an art alphabet; a trivial reskin.
- **Binary ///**: stub with no usable specification.
- **Bitwise Cyclic Teast**: work-in-progress, interpreter still in development.
- **Brainpocalypse** (removed): no input; invented dump and a one-bit halt-vs-loop wall; externally implemented.
- **Chainlang**: AI-generated spec its own author calls unfinished.
- **Conveyor**: no input command, stderr-only output.
- **Crement**: self-modifying, no I/O; no input to branch on.
- **DSDLAI** (removed): trivial Dig reskin with a random death chance; non-deterministic.
- **Earfuck**: trivial brainfuck reskin (notes for instructions).
- **Fourfuck**: incomplete, a stub with a couple of commands.
- **Gravity**: non-computable evolution; nothing verifiable.
- **Kak** (removed): no input; only the tape bit-string (an invented dump); externally implemented.
- **Keys** (removed): a two-line equality comparison; a gadget, not a language model.
- **Lightlang** (removed): boolean capability caps at the AND/OR class; only a single bit is ever printed.
- **LogicF---**: joke, non-deterministic and non-functional commands.
- **Movesum** (removed): no conditional at all, so no boolean generator; numbers-only output.
- **N Refine**: probabilistic self-rewriting OISC with no I/O; already implemented elsewhere.
- **Not Python**, **2001: An Esolang Odyssey**, **Stu**, **Bias**, **Writeover**: joke or vaguely specified, no usable spec or I/O.
- **Number Seventy-Four** (removed): string-rewriting with no input; output alphabet `0`/`1`/`H`.
- **Objects In Mirror Are Heavier Than They Appear**, **OpenStreetCode**, **Streetcode**, **Unary Filesystem**, **Phile**: file/OS-based, no portable file I/O.
- **Procedure**: only `the sum of ...` arithmetic is defined, so a faithful interpreter would have to invent the rest. Revisit if the wiki or Pure defines the operators.
- **something positive**: explicitly uncomputable.
- **State and Main**: one `main` argument, no output, no conditional; a boolean generator could reach at most one input.
- **Stun Step** (removed): no input; invented dump and a one-bit halt-vs-loop wall; sole implementation removed anyway.
- **Trash** (removed): advance-to-next-prime gadget; can never print `1`.
- **Vandevelo**: input-only, no output at all.
- **Varigen**: explicitly "uncomputable" joke language.
- **Welcome To...**: work-in-progress.
- **Your Time Is Up**: random rule choice, no I/O; nondeterministic.

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
