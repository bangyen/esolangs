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
  wall, not a pre-encoding detail.

### No-input languages: parameterized (assessed)

The parameterized generators (back, bio, nocomment) prove a no-input
language can compute a truth table if it has output plus a value-testable
branch (the bits are embedded as constants).  The no-input candidates that
were assessed:

- **Trash: ruled out.**  Its output is a prime-advanced number: a
  non-prime start prints ``0``, a prime start prints the next prime (3, 5,
  7, ...), and no ``t`` prints nothing.  It can never print a boolean
  ``"1"``, so it cannot return a truth-table result.
- **BF-PDA: research-level.**  ``.`` prints the top bit as a literal
  ``'0'``/``'1'`` and ``[``/``]`` loop on the top bit, which looks ideal —
  but a decision tree needs *two independent guard cells per bit* (the bit
  and its complement, cleared separately so each ``]`` exits), and BF-PDA's
  guards are all the same stack top.  The one-side loop cannot exclude the
  zero-side after it (no forward jump), so a bit-consuming tree over the
  stack is genuinely awkward.
- **Home Row: research-level.**  Its random-access cells give bf-style
  separate guards, but the ``l`` loops pair strictly *by order* (the first
  and second ``l`` form a loop, the third and fourth another; the RISC-V
  compiler's ``loop // 2`` numbering), so loops cannot nest.  A decision
  tree's AND-gating needs nested guards (the bf_tree structure), which Home
  Row cannot express; the pointer also only moves forward (``d``/``f``, no
  left/up).
- **No-input and no-output** (A Painter Ant, ArrowQueue, Bitdeque, Eval,
  Factor, Kak, Keys, Minsky Swap, RAM0): impossible — nothing to return.

So AddSubJump (the one target with a usable conditional) shipped, and the
assessed no-input interpreters all hit structural walls.  **Assessed since:
123 and the last seven candidates.**  123's single 8-bit data byte and
pointer that flips the bit as it moves (``1`` XORs the mask *and* advances,
wrapping -3..0) mean even reading a byte and navigating to the write
position corrupts the value being built — an n=1 identity loops.  123 is
research-level too.  The last seven:

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
- **%^2^-1: research-level.**  Its only control flow is ``t`` (rewind to
  the program start when the accumulator is nonzero) — no local jump
  targets and no skip — so a decision tree must be threaded through
  restart-to-start loops, and the arithmetic (``-2``/``-3``/``*2``/negate/
  zero) is too weak to fold the bits arithmetically.
- **Brainpocalypse: research-level.**  Its only control flow is ``-`` on a
  zero cell rewinding the instruction pointer to the program start, and
  every other character is a comment; it can print ``"0"``/``"1"`` (the
  tape prints on end) but any ``-`` that sees zero restarts the whole
  prefix, so loops and decisions need the pointer routed so the ``-`` never
  lands on a zero — a general n-bit tree is a genuine construction problem.
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
  **Built since: an ``abcdirection`` generator now ships (``n == 1``).**  A
  read staircase fills the queue, a corridor routes the pointer around the
  tree, each node tests its bit with ``C`` up, and the fired leaf prints
  ``48 + f`` before running off the terminator row (``EOFError``, which the
  harness treats as termination).  The tree's ``D``-left cells are spaced so
  no six-``D`` run fools the grid reader.  ``n == 1`` is verified; ``n > 1``
  raises, because deeper trees route the leaves through the tree's own cells
  and are not yet correct.

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
``bf → 6-5``, ``Decleq → S*bleq`` (the one non-brainfuck pair), and ``X → bf``
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
- **2D bf-tape (Dimensional ↔ LaserFuck; research-level).**  Both operate a
  brainfuck-style byte tape, but Dimensional's ``[``/``]`` loops have no
  counterpart in LaserFuck's mirror-driven control — a direct transpile
  would again be a full simulation.

## VM / debugging interface

A common step-and-inspect interface would make the library a tool for
studying esolangs, not just running them: `vm.step()`, `vm.halted`,
`vm.output`, `vm.ip`, `vm.memory`, and `vm.stack` on a wrapper around each
interpreter.  The goal is a `vm` module exposing one `VM` protocol, with a
per-language adapter behind it.

The state models are fundamentally different (tapes, stacks, registers, 2D
grids, self-modifying code), so `memory`/`stack`/`ip` are best-effort and
language-shaped rather than uniform: a tape language exposes its cells and
pointer, a stack language exposes its stack (and an empty ``stack`` for
languages without one), an OISC exposes its cells, and a 2D language exposes
its position and direction.  The interface contract is common; the fields
are what each language's state actually is.

This needs the interpreters to expose their state machine, which only seven
currently do (S*bleq, Dimensional, Grapheme, Qoibl, Eval, Modulous, The
Temporary Stack); the rest keep state in `run()` locals.  The incremental
path is to define the `VM` protocol, implement adapters for those seven plus
brainfuck (a trivial tape + pointer), and grow the set per state model over
time.  Medium priority: it is a distinct workstream rather than more
interpreters or transpilers, and it is the one feature that changes the
library's audience from "runner" to "study tool".

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
