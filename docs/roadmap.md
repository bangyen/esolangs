# Roadmap

Planned work, in priority order.  Language assessments, documented walls,
and ruled-out ideas live in `docs/limitations.md`; completed ideas live in
the commit history.  This file only tracks what is still on the table.

## New interpreters (in priority order)

Candidates from re-scanning the esolangs wiki's Category:Unimplemented and
from User:PythonshellDebugwindow's language list.  The original scan is
exhausted: every candidate with a usable file-based I/O protocol, a complete
specification, and a plausible generator or boolean story now has an
interpreter.  The candidates below are the genuine Category:Unimplemented
gaps still on the table.  The rest of each scan is either implemented, a
joke, non-deterministic, uncomputable, no-I/O, or file/OS-based, and is
recorded in `docs/limitations.md`: ruled out are Gravity, Earfuck, Conveyor,
Chainlang, Binary ///, Fourfuck, Aaargh++, and Bitwise Cyclic Teast; already
implemented elsewhere are Exp, Eso2D, Yaren, FROM HERE TO THERE, Jumplang,
UFSA, Stackint, Queuenanimous, and N Refine.

### Procedure (medium priority)
A Turing-complete pseudonatural English language with `Set the variable
'x' to ...`, `Connect to STDOUT`/`Write ... to the connection`, functions,
repeat-gotos, and if-then-otherwise conditionals.  Working Hello World, cat,
and truth-machine examples given.  The English-syntax parser is a heavier
lift.

### Lamfunc (medium priority)
A Turing-complete functional language of prefix calls and `F name - code`
definitions with lambdas (`` .f ``) and builtins for equality, branching,
bit ops, and variable storage.  `p` prints a value, so text output goes
bit-by-bit and a text generator is awkward.

### Point Break (low priority)
A Turing-complete language with four commands (`LET`, `POINT`, `BREAK`,
`END`) that simulates Minsky machines; `?` reads an integer in a `LET`.  It
has no output at all, so like Crement and A Painter Ant it can only be a
self-contained interpreter without a generator.

### State and Main (low priority)
A language of `main` and numbered `state N` definitions whose only
statements are `(state N!)` changes and `(return)` — the truth-machine
example explicitly has "No output".  Like Point Break it can only be a
self-contained interpreter.

### Your Time Is Up (low priority)
A Turing-complete string-rewriting language in binary (`(1+0)(1+0)` rule
groups followed by the initial datastring), where execution picks a matching
rule at random.  The output is therefore non-deterministic, and like DSDLAI
the interpreter would be faithful but its behavior only testable
mechanically; it also has no I/O, so it is a self-contained interpreter.

### COD (low priority)
A two-dimensional concurrency-heavy language of cods swimming in waves
enclosed ponds, where each cod carries an unbounded integer and `+`/`-`
duplicate or remove it.  Branches resolve to random directions, so like
LaserFuck/DSDLAI the output is non-deterministic but the interpreter can be
faithful to the spec.  It has I/O (`...` input, `---` output).

### Suptiftam (low priority)
Two-dimensional tape-tapes of bytes or integers, permissive function
definitions, includes, and I/O via the `read`/`term` tapes.  The spec is
complete but has undefined behaviors and its examples are untested, so it is
a heavier, riskier implementation.

### Crement (low priority)
A self-modifying language with ADDRESS/DATA/JUMP opcodes and a polarity
field, fully specified including a Minsky-machine reduction.  It has no
I/O, so like A Painter Ant it can only be a self-contained interpreter
without a generator.

### Completed from these scans
Languages from these scans that shipped (details in the commit history):

- **MyScript** — a JavaScript-like prefix language (`var ... is ...`,
  `check`/`if`/`else`, `while`, `say`/`ask`); interpreter, text generator,
  and boolean generator built.
- **A Painter Ant** — a no-I/O grid interpreter (self-contained, no
  generator).
- **AddSubJump** — a self-modifying OISC with a text generator.
- **Grapheme** — the interpreter covers the four modes, the
  arithmetic/stack commands, the untyped variable system, and function
  execution (`G`/`I`/`Q`/`Z`), and its only wiki example that can run
  (Hello World) verifies.  It has no text generator — strings cannot contain
  `E`, so even "HELLO" is unspellable — nor a boolean generator (the wiki's
  truth-machine cannot even read its `"0"`/`"1"` input as a clean bit); both
  walls are recorded in `docs/limitations.md`.
- **Forbin** — the interpreter covers function definitions (including
  nested and higher-order), iteration and range loops (``0..1`` iterates
  twice, so ranges double as if-statements), NOT, and the bit ``in``/``out``
  builtins; the text generator emits one ``out`` line per byte.  Two of the
  wiki's examples are not reproduced — the cat is buggy (its
  ``for _:0..1`` "while" doubles every byte; the language was unimplemented,
  so it was never run) — and the entry point is ``main`` with a dummy
  argument, per the examples.
- **ROTfuck** — the interpreter treats each executed command as advancing
  every source character one step along `+-><,.[]` and matches brackets
  dynamically — a bracket that fires rotates the program first, then seeks
  its partner in the rotated program (a partnerless fired bracket halts), so
  loops that revisit a bracket are expressible.  The text generator emits
  straight-line programs by placing the ``i``-fold inverse rotation of each
  desired command at position ``i``.
- **Decleq** — the memory-mapped I/O falls through (the `-2` output and
  `-1` input do not jump), `a b c` stores `memory[a]-1` into `memory[b]` and
  jumps when it is `<= 0`, and the generator simply places each byte in a
  data cell and prints it with a `-2` instruction, so the program is linear
  and compact.

## Lean proofs (in priority order)

Kept proofs: SLOW ACV MAMMALIAN generator totality (`extra/lean/esolangs/Esolangs.lean`)
and Factor's Dirichlet totality / encode-decode round-trip
(`FactorCorrect.lean`).  Everything else in the Lean project was dropped:
the four ported interpreters, their equivalence proofs, and all the
generator and boolean correctness proofs were redundant with the round-trip
test suite, so the Lean project now contains only the proofs of facts the
tests cannot establish (SLOW ACV MAMMALIAN's search totality, Factor's prime-search
totality).  The one exception kept self-contained rather than dropped is the
brainfuck-minterm boolean proof (`BfMintermCorrect.lean`), the completed
proof of the ``_bf_minterm`` generator's copy/AND scratch machinery and
minterm sum, which is not part of the main Lean build.  The candidates below
go beyond totality, in increasing payoff order.

### Factor: Dirichlet totality and encode/decode round-trip (medium priority)
Done.  `FactorCorrect.lean` models the commands/residues, the run-length
machinery, and the prime search `nextPrimeWithRes`, whose totality is exactly
mathlib's Dirichlet theorem (`Nat.forall_exists_prime_gt_and_modEq`).  The
round-trip `decodeRuns_encodeRuns` / `decode_encode` proves the sorted distinct
prime factors of the encoded integer are precisely the chosen primes, in
order, with the right exponents (`encodeRuns_factorization_at`,
`chosenExp_pos_iff`, `primeFactors_encodeRuns`).

### Retired Lean proof items
All other Lean proofs were dropped as redundant with the round-trip test
suite (the generator and boolean correctness proofs re-prove what the
differential/round-trip tests already establish): EXCON, AlbaBet, Circlefuck,
Sophie, BIO, 6-5, Qoibl, huf, brainfuck, eval, Collatz Multiverse, the
``_bf_set`` multiply loop, and the Sophie/6-5 boolean proofs, and the four
ported Lean interpreters with their equivalence proofs.  The one
non-redundant candidate remaining, if more Lean work is ever wanted, is the
Minifuck boolean reachability characterization (a language-power theorem, not
a generator-correctness proof): Minifuck computes exactly the four one-input
functions plus the eight 0-preserving two-input tables, via the ``[<``
conditional pointer move and the decode-suffix wall (`docs/limitations.md`).

## Text generators: exhausted

Every language whose interpreter can emit arbitrary bytes already has a text
generator, now including Collatz Multiverse (a constant table of byte values
bootstrapped from ``negativeOne`` with the copy trick and parity-aware
``one x + one``/``one x + two`` increments, then one copy-and-print line per
character) and AlbaBet (its `c`+`a`-run+`i` generator and correctness proof
landed with the other Lean proofs).  The remaining interpreter-only languages
(ArrowQueue, Back, Bitdeque, DSDLAI, Keys, Lightlang, Minsky Swap, Movesum,
RAM0, A Painter Ant) either have no output, print numeric state, print a
fixed string, or print their final grid, so none can emit arbitrary text.
ABCDirection is the one exception: its Boolfuck output can emit arbitrary
bits, but moving the tape pointer between outputs needs the full 2D routing
that makes a text generator a routing problem rather than an arithmetic one.
The newly assessed boolean candidates that fell through (The Temporary Stack, Movesum,
WII2D, EXCON, Huf, Lightlang, DSDLAI) are recorded in `docs/limitations.md`.

## Boolean generators: assessed

Text generators are exhausted.  The last two candidates to assess were
AddSubJump and ROTfuck (both read input, branch on a value, and output a
bit):

- **AddSubJump.**  A self-modifying OISC whose conditional is the zero /
  negative flag under flag mode, with input and output specials.  It already
  has a text generator; a boolean generator would compile the truth table
  the same way the Decleq and S*bleq boolean generators do, and the
  input/conditional/output primitives are verified to work (a byte reads in
  and echoes out).  The strongest remaining opportunity.  **Done: the
  generator shipped (decision tree through the negative flag).**
- **ROTfuck (research-level, not a carry-over).**  ROTfuck is brainfuck
  whose program text rotates after every command and whose brackets match
  *dynamically* (a firing bracket rotates, then seeks its partner in the
  rotated program).  The text generator's straight-line inverse-rotation
  encoding does not survive loops — a rotation-encoded brainfuck loop fails
  (the ``]`` cannot find its ``[`` at the right rotation state) — so a
  boolean generator cannot reuse the brainfuck minterm strategy.  A decision
  tree would have to be designed around the rotation-state-dependent bracket
  matching, which is fragile and hard to verify.  The rotation is a real
  wall, not a pre-encoding detail.  **Done: the generator shipped.**  The
  escape from the wall is to avoid loops entirely: each ``[ body ]`` block
  has a straight-line ``+-><``-only body (no nested brackets), and the
  closing ``]`` is a *phantom* whose source character is encoded so the
  ``[``-fire seek finds it at the right rotation state.  Both the skip path
  (tested cell 0) and the body path re-converge after the block in the same
  rotation state because every body length is 7 (mod 8), so the program
  after a block can be encoded position-wise.  The truth table is evaluated
  as a minterm sum with an idempotent-zeroing indirection (each input bit
  and its complement guard mismatch counters; one block per minterm zeroes
  the minterm iff its counter is nonzero; ``1``-rows accumulate).  Verified
  exhaustively for every table at ``n <= 2`` and sampled through ``n = 4``.

### No-input languages: parameterized (assessed)

The parameterized generators (back, bio, nocomment, bfpda) prove a no-input
language can compute a truth table if it has output plus a value-testable
branch (the bits are embedded as constants).  The no-input candidates that
were assessed:

- **Trash: ruled out.**  Its output is a prime-advanced number: a
  non-prime start prints ``0``, a prime start prints the next prime (3, 5,
  7, ...), and no ``t`` prints nothing.  It can never print a boolean
  ``"1"``, so it cannot return a truth-table result.
- **BF-PDA: the earlier wall was wrong; the generator shipped.**  ``.``
  prints the top bit as a literal ``'0'``/``'1'`` and ``[``/``]`` loop on the
  top bit, which looks ideal — the assessment claimed a decision tree needs
  two independent guard cells per bit and that BF-PDA's guards are all the
  same stack top, but the bit stack *provides* the independent guards: a
  node pushes the complement then the bit, runs the one-side loop when the
  bit is one, pops it, and runs the zero-side loop when the complement is
  one.  Each subtree is stack-balanced (leaves push the answer bit, print it
  with ``.``, and pop it), so every ``]`` re-tests its own guard.  A
  parameterized ``bfpda`` generator ships and is verified for every table at
  ``n <= 4``.
- **Home Row: done.**  Its random-access cells give bf-style separate
  guards, and the ``l`` loops pair strictly *by order* (the first and second
  ``l`` form a loop, the third and fourth another; the RISC-V compiler's
  ``loop // 2`` numbering), so loops cannot nest — a bf-style decision tree
  is inexpressible.  But ``j`` skips the next instruction when the current
  cell is zero, so ``jf``/``jd`` are *guarded moves*: a beam at a nonzero
  cell moves right/down, at a zero cell stays put.  The generator routes a
  tree with these instead of loops: a baked bit cell at position ``i`` is
  tested by a ``j``-guarded move, and the two outcomes (beam at the bit cell
  or one cell right) are diverged with a plain move.  The ``jfjffjdd``
  routing with bits at cells 0 and 1 separates all four two-input
  combinations onto distinct cells with every ``j`` testing only a baked bit
  cell, so the answer bytes can be baked first without corrupting the
  branches; ``jfd`` does the same for one input.  Verified exhaustively for
  every one- and two-input table.  ``n >= 3`` raises: no ``j``-guarded
  routing separates ``2**n`` combinations onto distinct cells of the 5x5
  grid (an exhaustive search caps at 6 of 8 combinations).
- **No-input and no-output** (A Painter Ant, ArrowQueue, Bitdeque, Eval,
  Factor, Kak, Keys, Minsky Swap, RAM0): impossible — nothing to return.

A note on embedding: the shipped parameterized generators fall into two
classes.  **Single-embed** generators bake each input bit exactly once —
nocomment computes the input's numeric index arithmetically with one
``{Xi}`` setter per bit and does a single computed skip, and home_row's beam
passes through each baked bit cell exactly once per combination.  (The
nocomment skip is byte-sized, so its index caps at eight inputs — a genuine
language wall, since a conditional ``s`` jump over a region larger than 255
commands is inexpressible; see `docs/limitations.md`.)  **Per-node
embed** generators place the bit at every tree node of its depth — back's
``{Xi}`` mirror appears at each of the ``2**i`` nodes at depth ``i``, and
bio's ``{Xi}``/``{Ci}`` twice per node.  The per-node embedding is not an
optimization opportunity: a node's two branches diverge to different
locations, so sharing one test cell would require them to *reconverge*
before the next bit — which loses the branch history (the beam's position /
registers are the only record of the path).  Reconvergence is precisely the
construct those languages lack, so single-embedding back/bio is a structural
wall, not a cheap win; the single-embed designs already shipped where the
language permits it.

So AddSubJump (the one target with a usable conditional) shipped, and the
assessed no-input interpreters mostly hit structural walls — BF-PDA turned
out to be a false wall and shipped too.  **Assessed since:
123 and the last seven candidates.**  123's single 8-bit data byte and
pointer that flips the bit as it moves (``1`` XORs the mask *and* advances,
wrapping -3..0) corrupt the value being built as the pointer navigates to the
write position.  **Assessed: ruled out.**  An exhaustive search over every
program up to length 13 (1.6M programs) finds that input ``'0'`` (48) can
only ever print the even bytes ``{0, 4, 6, 8, ..., 248}`` — the odd byte 49
(``'1'``) is unreachable, so NOT and const-1 are inexpressible.  Only two of
the four one-input functions work: identity (``1112121121``) and const-0
(``1111132231``), both verified against the interpreter.  The ``3``-jump
(nearest preceding/following ``3``) and the loop-from-start behavior (reaching
the end with the pointer at a data position restarts without resetting data)
do provide real control flow, but the write's fixed flip structure (writing
needs mask 512, whose ``1``-path toggles masks 2..256) binds the reachable
output bytes per input.  A boolean generator is not feasible.  The last
seven:

- **Stun Step: ruled out.**  On halt it prints the reached cells
  space-joined, and the leftmost cell (position 0, where the pointer starts)
  must be 0 to halt, so a bare single-cell output is always ``"0"`` and
  reaching any other cell appends more numbers — it can never print a bare
  boolean ``"1"``.
- **Number Seventy-Four: ruled out.**  A program halts only once the output
  starts with ``H`` (and an ``H`` fires only on an output that starts with
  ``0``), so every halting program prints ``"H..."`` and never a bare
  ``"0"``/``"1"``.
- **2 Bits, 1 Byte: ruled out.**  Its only branches are the unconditional
  ``JMP`` and the self-modifying ``ACT``; the 2-bit opcode is fixed by the
  program byte, so there are no runtime values to test — a generator would
  degenerate to printing a baked constant.
- **AlbaBet: ruled out.**  Only straight-line arithmetic (+1, *y, square,
  move, print); there is no loop, jump, or skip, so no value-testable
  branch for the bits to route through.
- **%^2^-1: ruled out.**  Its only control flow is ``t`` (rewind to
  the program start when the accumulator is nonzero) — no local jump
  targets and no skip.  The rewind re-runs the whole body with the
  accumulator preserved, so a program is a whole-program ``while`` loop:
  ``run body; if acc != 0: rewind``.  Each ``n`` in the body consumes an
  input line, so the loop iterates over the input bits — but it cannot
  *count* them (there is no increment op, and rewinds re-run the body, so a
  ``m``/``s``-style counter grows without bound and crashes).  The loop
  stops only when a body pass ends with ``acc == 0``, a uniform predicate
  that cannot distinguish pass 1 from pass n, so the all-ones input of any
  truth table either stops early or rewinds past the input (EOF).  Exhaustive
  search confirms it: of the four one-input functions only identity and the
  two constants are expressible (``ne``/``n``+24×``s``+``l`` for identity,
  ``l`` for const-0, ``ipsl`` for const-1); NOT and every two-input table
  (AND, OR, XOR) fail even at length 8.  A boolean generator is not
  feasible.
- **Brainpocalypse: ruled out.**  Its only control flow is ``-`` on a
  zero cell rewinding the instruction pointer to the program start, and
  every other character is a comment; it can print ``"0"``/``"1"`` (the
  tape prints on end) but any ``-`` that sees zero restarts the whole
  prefix.  The output constraint closes the case: a bare boolean means only
  cell 0 may print (``right`` stays 0), leaving just cell 0 and the wrap
  scratch cell 255; the ``-``-on-zero branch is the *only* conditional, and
  rewinding re-runs the whole bit-baking prefix with the tape intact.  An
  exhaustive search of templates confirms it: of the four one-input
  functions, only identity is expressible (bake the bit into cell 0 and move
  away) — const-0, const-1, and NOT all need to branch on cell 0's value,
  which the ``-``-rewind destroys.  A boolean generator is not feasible.
- **ABCDirection: the one remaining genuine opportunity.**  It has real
  input (``D`` up reads a Boolfuck bit), output (``C`` down emits one), and
  value-tested routing (``C`` up turns on a one, ``D`` down dispatches on
  the cell and queue), so a decision tree is expressible — but it must be
  laid out on a wrapping 2D grid with no halt instruction (the interpreter
  stops on a command limit), the LaserFuck/Back class of hard 2D-layout
  work.  A quick probe confirms the concrete blockers: the ``D``/``C``
  actions depend on the current heading (up reads, right enqueues, left
  dequeues, down dispatches), the ``C left`` tape move flips the cell it
  leaves so the tape pointer cannot move right without corrupting, the
  ``DDDDDD`` terminator row sits on the donut's wrap edge so every upward
  wrap enters it and fires its ``D`` actions, and there is no halt.  A
  queue-based byte echo (read into cell 0, ``D`` right enqueue, then
  ``D`` left dequeue and ``C`` down output) is the promising construction,
  but it needs the heading state threaded correctly through the wraps.
   **Built since: an ``abcdirection`` generator now ships and scales to any
   ``n``.**  A read staircase fills the queue, a corridor routes the pointer
   around the tree, each node tests its bit with ``C`` up, and the fired leaf
   prints ``48 + f`` before running off the terminator row (``EOFError``,
   which the harness treats as termination).  The tree is laid out on absolute
   columns (each node sits at the midpoint of its leaf range, so the crossing
   subtrees can never meet), the ``D``-left cells are spaced so no six-``D``
   run fools the grid reader, each leaf routes DOWN at a clear column to its
   own escape row before the serpentine, and each leaf's EOF sink uses its own
   column so the turn cells never sit on another leaf's upward path.
   Verified for every table at ``n <= 3`` and sampled through ``n = 6``.

**Never assessed** and still on the table: none — the no-input and
input-reading candidates are now individually assessed.

## Compiler consolidation

The repo previously had two compiler backends: Python compilers emitting
RISC-V assembly (`src/esolangs/compilers/assembly/`) and C programs emitting
C (`src/esolangs/compilers/c/`).  The consolidation is done: EXCON, BF-PDA,
and RAM0 each got a Python ``comp()`` in ``assembly/`` emitting RISC-V Linux
assembly, every compiler is now verified end to end in CI through
``scripts/verify_riscv_unicorn.py``, and the ``.c`` files plus their
gcc-based test suite were dropped.  The new BF-PDA and RAM0 backends follow
the interpreters (no-op brackets; the ``z:/n:/ram:`` state dump with
insertion-ordered RAM) rather than the C compilers' divergent semantics
(while-loops; a pre-seeded stack; a ``Z:/N:`` dump).

## Transpilers

The transpilers today: ``bf ⇄ ASCII art`` (a bijection), ``bf → Circlefuck``,
``bf → 6-5``, ``bf → 3D Brainfuck``, ``bf → Painfuck``, ``Decleq → S*bleq``
(the one non-brainfuck pair), and ``X → bf``
for X in {Basicfuck, BFStack, BIO, huf}.  This works because those languages
share a common core; the partial ones reject their out-of-class programs
rather than mistranslate, and the NoComment and reverse-decoder transpilers
were dropped (silent-dropper, round-trip-only).

A direct transpile between languages with no shared core is not a rewrite —
it needs a full runtime of one inside the other.  The candidates that do
share a core:

- **OISC-to-OISC (Decleq → S*bleq; done).**  Both are self-modifying-memory
  OISCs, and both branch on "≤ 0"; the transpiler materialises Decleq's
  ``mem[b] = mem[a] - 1`` with straight-line scratch blocks and S*bleq's
  indirect ``c`` (``ip = mem[c]``) expresses Decleq's direct jump.  Decleq
  code that re-reads a written cell as an operand (self-modifying code) is
  rejected, and a program that runs off into memory it extended past itself
  halts in the translation; both limits are documented in
  `transpilers.decleq_to_sbleq`.  The reverse S*bleq → Decleq and the
  AddSubJump pair remain research-level: neither has dynamic instruction
  dispatch, so the general total transpiler is not expressible.
- **Forth-family ↔ Forþ.**  Forþ is Forth-like (single-char stack,
  arithmetic, ``(``/``[`` loops, ``;`` calls); adding a second Forth dialect
  (e.g. plain Forth) would share the stack+arithmetic+loop core and
  transpile directly.
- **Boolfuck ↔ ABCDrection / Minifuck.**  A Boolfuck (bit tape, little-endian
  byte I/O) shares ABCDrection's bit-tape model; Minifuck's
  flip-and-conditional-skip is further away.
- **2D bf-tape (Dimensional → LaserFuck; done).**  Dimensional's ``[``/``]``
  loops have no counterpart in LaserFuck's mirror-driven control, so a
  transpile is a real construction, not a rewrite.  It works by giving the
  start marker a funnel that pins its random heading, emitting each ``[`` as
  a ``v`` that detours the beam into a loop ring below the strip (the test
  ``# v ) \\`` reflects a nonzero cell back into the body and lets a zero
  cell fall through to the exit, with a loop-back up a clear column), and
  negating every working cell at the end so LaserFuck's single final tape
  dump matches Dimensional's output.  The supported class is the linear-tape
  core (``>0``/``<0``, ``+``/``-``, ``.``/``,``, ``[``/``]``, the ``=HH``/
  ``:CH`` literals); the pointer hierarchy, non-zero-dimension moves, moving
  below cell 0, drifting loops, and any output beyond a final single ``.``
  are rejected rather than mistranslated, and cells do not wrap at 8 bits in
  the translation.
- **bf → 3D Brainfuck (done).**  3D Brainfuck is a brainfuck superset whose
  ``>``/``<`` set the code pointer's heading and whose array moves ``n``/``s``
  walk the tape along one axis, so the translation is a one-to-one command
  swap: ``>``→``n``, ``<``→``s``, everything else unchanged.  Verified for
  the transpiler battery through the target interpreter.
- **bf → Painfuck (done).**  Painfuck is brainfuck-compatible through a
  fixed two-cycle Caesar substitution (the interpreter rewrites each source
  character ``k`` steps along its cycle, where ``k`` counts the characters
  translated so far): brainfuck ``>``/``<``/``+``/``-``/``[``/``]``/``,``/``.``
  become ``rl``/``l``/``ps``/``s``/``a``/``b``/``j``/``u``, and each emitted
  command is pre-shifted ``k`` steps back along its cycle to undo the
  interpreter's forward shift.  Verified for the transpiler battery through
  the target interpreter.

## VM / debugging interface

A common step-and-inspect interface makes the library a tool for studying
esolangs, not just running them: `vm.step()`, `vm.halted`, `vm.output`,
`vm.ip`, `vm.memory`, and `vm.stack` on a wrapper around each interpreter.
The goal is a `vm` module exposing one `VM` protocol, with a per-language
adapter behind it.

The state models are fundamentally different (tapes, stacks, registers, 2D
grids, self-modifying code), so `memory`/`stack`/`ip` are best-effort and
language-shaped rather than uniform: a tape language exposes its cells and
pointer, a stack language exposes its stack (and an empty ``stack`` for
languages without one), an OISC exposes its cells, and a 2D language exposes
its position and direction.  The interface contract is common; the fields
are what each language's state actually is.

**Shipped:** `esolangs.make_vm` exposes the `VM` protocol with adapters for
nine interpreters whose state objects step: brainfuck (tape + pointer),
S*bleq (OISC cells), Dimensional (its addressed byte), Grapheme (stack +
call frames), Qoibl (expression cursor + variable list), Eval (active stack),
Modulous (stack + token cursor), The Temporary Stack (stack + word pointer),
and LaserFuck (a grid language whose ``ip`` is the active laser's
``(x, y, heading)``, with the heading fixed to 0 for reproducible stepping).
The interpreters expose their state machine as `step()`/`halted`; the rest
of the registry keeps state in `run()` locals.

The remaining work is to grow the set per state model over time: convert
more interpreters to a step-capable state object (the other grid languages,
whose position/direction is the natural ``ip``), and add the debugger
affordances on top of the VM (breakpoints, watch on a cell/stack slot, a
richer ``ip`` for the recursive languages).  Medium priority: it is a
distinct workstream rather than more interpreters or transpilers, and it is
the one feature that changes the library's audience from "runner" to
"study tool".

### Cheaper study-tool improvements (do first)

These serve the same "study tool" goal with no interpreter refactor, so they
are natural stepping stones while the VM grows:

- **Annotated program walkthroughs.**  For one representative language per
  state model (brainfuck / a stack language / a register or OISC language /
  a 2D language), a docs page walking a small program command by command:
  what each instruction does to the cells/stacks/registers and why the
  example terminates.  Pure content, immediately useful for teaching, and it
  doubles as a spec-check against the wiki pages the interpreters document.
- **`esolangs.describe(lang)`.**  A public function returning a structured
  description: state model (derived from the interpreter's module path),
  I/O style, whether it has a text/boolean generator, its transpilers, its
  example files, and its esolangs.org page.  Most of the data already lives
  in the registry and `docs/languages.md`; this just exposes it through the
  API.
- **A `run(..., timeout=...)` wall-clock guard.**  The public API currently
  cannot bound a program (see the unbounded-execution convention), so a
  runaway program hangs a caller.  A wall-clock `timeout` parameter on
  `esolangs.run` that raises `HaltError` on expiry is a thin wrapper around
  the existing interpreters and makes automation and study safe.
