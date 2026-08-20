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
| A Painter Ant | No I/O; prints the visited-grid bounding box (a `#`/`.` raster). Has a general (any-arity) boolean generator; no text generator. |
| ArrowQueue | No output at all; the IP walks the grid and halts, printing nothing. |
| Back | Prints the tape as a number list. |
| BF-PDA | `.` prints the top bit as the `'0'`/`'1'` character, so the output alphabet is just the two digits. |
| Bitdeque | Prints the register/deque contents as numbers. |
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
| 123 | Single data byte, every read overwrites it; the `3`-jump is nearest-match, not a branch — only one-input functions via runtime `,` reads. A parameterized generator (embedding each input in the program at compile time, as WII2D's does) has not been assessed. |
| %^2^-1 | Only control flow is `t` (rewind on a nonzero accumulator); a whole-program while loop that cannot count passes. |
| SLOW ACV MAMMALIAN | `ACCEPT` forces `ptr == 0` to consume a bit, but routing needs `SPRINT` to move the pointer away — reading and routing can't coexist; the constant source (`SEED` from an emptied array) accumulates rather than resets; `DIGEST` only recovers a bit as part of a sum. An exhaustive search over the branch-free tails reaches only 0-preserving two-input tables — the same class already removed for Minifuck as too weak to keep. Full argument in `docs/walls.md`. |

## Generator caps (shipped)

| Generator | Cap | Wall or liftable? |
| --- | --- | --- |
| NoComment | `n <= 8` | Genuine wall: the `s` skip is byte-indexed, capping every jump at 255. |
| Polynomial | `n <= 4` | Performance cap: exact factorization of huge coefficients is impractical past `n == 4`. |
| 6-5 | `n <= 5` exact; dense large-`T` tables (e.g. AND-6) rejected past that | Genuine wall: the decision tree is total through `n == 5` (35 branch labels); the arithmetic fallback needs the table (or its complement) as a single integer, so a dense table with no cheap complement needs an unbuildable ~O(2**(2**n))-character setup. |
| ZTOALC L | `n <= 3` exact; popcount-symmetric tables lifted further (e.g. XOR4 at `n == 4`); dense non-symmetric `n == 4` rejected | Genuine wall: every Collatz trajectory converges to the `16, 8, 4, 2, 1` tail, so a dense non-symmetric tree has leaf collisions past `n == 3`; symmetric tables fall back to a branch-free linear program instead. |
| WII2D | `n <= 4` exact (exhaustive through three, sampled dense at four); symmetric tables of any arity via closed forms; dense non-symmetric past `n == 5` rejected | Genuine wall: the single-embedding chain's branch op strings are bounded, so the counting bound rules out representing every table once `n` is large; the search raises for dense non-symmetric tables past `n == 5`. |
| 123 | one input only | Structural wall: single data byte, every read overwrites it. |
| Factor | program-size cap, not `n`-driven: sparse tables (e.g. constant-0/1) stay under the cap at any tested `n`, dense tables (e.g. XOR4, AND4 at `n == 4`) don't | Liftable by host config: the encoded integer's decimal length is checked against `sys.get_int_max_str_digits()` (CPython's int-to-string DoS guard, default 4300 digits) before rendering — the Factor *interpreter* parses its program the same way, so a caller who raises the process-wide limit gets both the generator and the interpreter working past it. |

Removed for being trivial: the boolean generators for Home Row (`n <= 2`) and
Minifuck (`n <= 3`, 0-preserving two-input only) were dropped — their caps
left them able to express only a small fraction of the two-input boolean
functions.  Their languages and text generators remain; see `docs/roadmap.md`.

The parameterized no-input generators embed every input exactly once rather
than re-embedding a bit at multiple decision nodes, mirroring how an
input-capable language reads each input once per run.  `nocomment` and
`bfpda` were previously counted as exceptions (embedding each input's
complement too), but neither actually needed it — `nocomment` computes the
complement from the bit at runtime, and `bfpda`'s second push turned out to
be a bit-independent constant, not a complement.  The per-language reasoning
is in [`docs/walls.md`](walls.md).

## Assessed and rejected

Languages from the wiki that were assessed against the admission criteria
and did not make the repo — whether they were never implemented (the
roadmap's fell-through) or were removed after being implemented.  The
viable candidates are in `docs/roadmap.md`; the full rationale for each
verdict is in the commit history.  ``(removed)`` marks languages whose
interpreter, generator, and tests were deleted from the repo.

- **2 Bits 1 Byte** (removed): joke; single-byte program, no text or boolean generator, externally implemented.
- **Aaargh++**: 4D work-in-progress with a partial spec.
- **Albabet** (removed): straight-line two-register accumulator; no conditional at all (only reset/increment/copy/multiply/print), so no boolean generator.
- **ASCII art** (removed): brainfuck with an art alphabet; a trivial reskin.
- **Binary ///**: stub with no usable specification.
- **Bitwise Cyclic Teast**: work-in-progress, interpreter still in development.
- **Brainpocalypse** (removed): no input; invented dump and a one-bit halt-vs-loop wall; externally implemented.
- **Chainlang**: AI-generated spec its own author calls unfinished.
- **Conveyor**: no input command, stderr-only output.
- **Crement**: self-modifying, no I/O; no input to branch on.
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
- **EXCON** (removed): straight-line 8-cell bit pool; no conditional at all (only reset/flip/pointer/print), so no boolean generator.
- **Fourfuck**: incomplete, a stub with a couple of commands.
- **Gravity**: non-computable evolution; nothing verifiable.
- **Huf** (removed): straight-line two-register accumulator; no conditional at all (only reset/increment/multiply/print), so no boolean generator.
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
- **The Temporary Stack** (removed): its text generator is a literal-embed (the text is pushed as a `*` string literal), and its boolean generator was walled — the auto-drain's `front - 1` output can't be `'0'`/`'1'` and there is no input-dependent branch. Under the tightened generator-story criterion (a literal-embed text generator needs a boolean generator), that made it inadmissible; the full wall argument is in `docs/walls.md`.
- **Trash** (removed): advance-to-next-prime gadget; can never print `1`.
- **Vandevelo**: input-only, no output at all.
- **Varigen**: explicitly "uncomputable" joke language.
- **Welcome To...**: work-in-progress.
- **Your Time Is Up**: random rule choice, no I/O; nondeterministic.

## Cross-check removals

Seven `extra/` cross-checks (Rust and RISC-V ports) were removed for not
meeting the independent-and-broad bar — no generator, or a corpus-only
cross-check that added nothing over the round-trip tests.  The languages
themselves mostly stayed; the full reasoning and the per-cross-check list
is in [`docs/walls.md`](walls.md#cross-check-removals-why-seven-were-dropped).

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
- **2D-to-2D.**  No two 2D languages share a model: 2dFish is a deadfish
  accumulator, Dimensional a pointer-hierarchy tape, LaserFuck mirror-driven
  control, ABCDrection a Boolfuck bit tape with a queue.  Even the two
  bf-tape ones (Dimensional, LaserFuck) differ in control flow.
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
