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
| A Painter Ant | No I/O; prints the visited-grid bounding box (a `#`/`.` raster). Has a boolean generator (exact n <= 2), not a text one. |
| ArrowQueue | No output at all; the IP walks the grid and halts, printing nothing. |
| Back | Prints the tape as a number list. |
| Bitdeque | Prints the register/deque contents as numbers. |
| Grapheme | Strings cannot contain `E` (terminates stringmode) and there is no concatenation, so even "HELLO" is unspellable. |
| Kak | Prints the tape as a `0`/`1` bit-string; exact bytes are unspellable. |
| Lightlang | Prints only the single bit as a number. |
| Minsky Swap | Prints the registers as numbers. |
| Movesum | Prints `n ` (numbers with a trailing space). |
| RAM0 | Prints a state dump. |
| Stun Step | Prints the reached cells as space-separated decimal numbers. |

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
| ArrowQueue | No output; only the halt-vs-hang outcome is observable, which expresses AND/OR/threshold functions but no XOR (see `docs/walls.md`). |
| Brainpocalypse | `-`-on-zero rewinds to the program start; re-running the `+` bake increments cells unboundedly. |
| Dotlang | The `W~` warp re-enters the first-match markers, losing branch history. |
| Eval | Nested parameterized trees need backtick escaping the spec forbids. |
| EXCON / Huf | Straight-line, no input, no branch. |
| Grapheme | `V` jumps forward on falsy with no mid-tree halt, so the truthy branch falls through both leaves. |
| Kak | Prints the whole tape, not a single `0`/`1`. |
| Lightlang | `&` skips one character, so a decision-tree node cannot route to a multi-character subtree. |
| Movesum | No conditional; the loop repeats until the array stops changing. |
| Stun Step | The loop-back re-runs the code with a shifted pointer, corrupting the bit bakes. |
| The Temporary Stack | The auto-drain prints `front - 1`, which cannot be `'0'`/`'1'`; no input-dependent branch. |
| WII2D | The accumulator never affects control flow. |

## Generator caps (shipped)

| Generator | Cap | Wall or liftable? |
| --- | --- | --- |
| NoComment | `n <= 8` | Genuine wall: the `s` skip is byte-indexed, capping every jump at 255. |
| Polynomial | `n <= 4` | Performance cap: exact factorization of huge coefficients is impractical past `n == 4`. |
| Home Row | `n <= 2` | Language cap: the fixed 5x5 torus cannot route `2**n` combinations past `n == 2`. |
| Minifuck | `n <= 3`, 0-preserving two-input only | Structural wall: the decode suffix fixes the pointer orientation. |
| 123 | one input only | Structural wall: single data byte, every read overwrites it. |
| Circlefuck, ROTfuck, ABCDirection, BF-PDA, Bitdeque, Minsky Swap, RAM0 | total (no cap) | Verified exhaustively to `n <= 3`-`4`, sampled beyond. |

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
- **2 Bits 1 Byte: removed.**  A joke language (wiki categories: joke,
  unusable for programming) whose program is a single byte, so it can never
  have a text generator (the output is always one byte) or a boolean
  generator (``JMP``/``ACT`` target fixed fields, so there is no
  value-testable branch).  Its wiki page already documents six external
  implementations (JavaScript, C++, Haskell, Snap!, HTML, and Bangyen's
  Python), so removing this interpreter leaves no gap, and its RISC-V
  cross-check had already been dropped.  The counterweight — it was one of
  the few interpreters hand-verifiable against a complete spec enumeration
  (the wiki lists every one of the 256 possible programs' output) and it
  resolved the wiki's ACT ambiguity (the command table contradicts the
  disassembly example, and the interpreter followed the example to match
  Hakerh400's reference) — was weighed and did not outweigh the absence of
  any generator, gap, or unique verification value.
- **Number Seventy-Four: removed.**  A string-rewriting language whose three
  commands ``0``/``1``/``H`` only ever *prepend* to an output string, run in
  repeated passes until the output starts with ``H``; it has no input
  command.  It can never have a text generator (the output alphabet is
  ``0``/``1``/``H``) or a boolean generator (the halt depends only on the
  front-most output character).  Unlike 2 Bits 1 Byte it is a genuine gap to
  remove — the wiki categorizes it Unimplemented, so this interpreter was
  the only one — and its Rust cross-check had already been dropped.  The
  interpreter was hand-verifiable (it resolved the pass-boundary halting
  check and the restart-forever behavior), but the absence of any input,
  generator, or non-trivial output class was weighed against the gap and won.
- **Trash: removed.**  The wiki defines a single function — advance to the
  next prime, or print ``0`` for a non-prime start — applied to a number,
  so a program is just a value with leading ``t`` step counts: a gadget
  rather than a language model (it exists to satisfy CGCC's definition of a
  programming language).  It can never have a text generator (only
  prime-advanced output) or a boolean generator (it can never print ``1``).
  It is also a genuine gap to remove (the wiki categorizes it Unimplemented;
  this interpreter was the only implementation) and its Rust cross-check was
  already dropped.  The interpreter resolved real spec details (trial
  division, 2-is-prime, leading-digit and prefix parsing) but the language's
  triviality and missing generator story outweighed the gap.
