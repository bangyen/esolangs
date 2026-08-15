# Roadmap

Planned work, in priority order.  Language assessments, documented walls,
and ruled-out ideas live in `docs/limitations.md`; completed ideas live in
the commit history.  This file only tracks what is still on the table.

## New interpreters (in priority order)

Candidates from re-scanning the esolangs wiki's Category:Unimplemented and
from User:PythonshellDebugwindow's language list.  The original scan is
exhausted: every candidate with a usable file-based I/O protocol, a complete
specification, and a plausible generator or boolean story now has an
interpreter.  Ruled-out candidates (Gravity, Earfuck, Conveyor, Chainlang,
Binary ///, Fourfuck, Aaargh++, Bitwise Cyclic Teast) are recorded in
`docs/limitations.md`, and A Painter Ant (a no-I/O grid interpreter) and
AddSubJump (a self-modifying OISC with a text generator) shipped from that
scan.  A second look over the PythonshellDebugwindow languages found Forbin
(a genuine Category:Unimplemented gap, now built); the other reassessed
pages (Exp, Eso2D, Yaren, FROM HERE TO THERE) already have implementations,
so like the earlier Jumplang/UFSA/Stackint/Queuenanimous they are not on
this roadmap.  A third pass over the remaining unchecked pages found
Grapheme (built) and Point Break, and a fourth found MyScript, Procedure,
Lamfunc, and State and Main — all Category:Unimplemented.  The rest of that
list is either implemented, a joke, non-deterministic, uncomputable,
no-I/O, or file/OS-based, and is recorded in `docs/limitations.md`.

### MyScript (high priority)
A Turing-complete JavaScript-based language with prefix functions, `var
... is ...` variables, `check`/`if`/`else` switches, `while` loops, and
`say`/`ask` I/O.  Fully specified with working Hello World, cat, and
truth-machine examples, and it is a genuine Category:Unimplemented gap.

### Procedure (medium priority)
A Turing-complete pseudonatural English language with `Set the variable
'x' to ...`, `Connect to STDOUT`/`Write ... to the connection`, functions,
repeat-gotos, and if-then-otherwise conditionals.  Working Hello World, cat,
and truth-machine examples given.  A genuine Category:Unimplemented gap,
though the English-syntax parser is a heavier lift.

### Lamfunc (medium priority)
A Turing-complete functional language of prefix calls and `F name - code`
definitions with lambdas (`` .f ``) and builtins for equality, branching,
bit ops, and variable storage.  `p` prints a value, so text output goes
bit-by-bit and a text generator is awkward.  A genuine
Category:Unimplemented gap.

### Point Break (low priority)
A Turing-complete language with four commands (`LET`, `POINT`, `BREAK`,
`END`) that simulates Minsky machines; `?` reads an integer in a `LET`.  It
has no output at all, so like Crement and A Painter Ant it can only be a
self-contained interpreter without a generator.  A genuine
Category:Unimplemented gap.

### State and Main (low priority)
A language of `main` and numbered `state N` definitions whose only
statements are `(state N!)` changes and `(return)` — the truth-machine
example explicitly has "No output".  Like Point Break it can only be a
self-contained interpreter.  A genuine Category:Unimplemented gap.

### Your Time Is Up (low priority)
A Turing-complete string-rewriting language in binary (`(1+0)(1+0)` rule
groups followed by the initial datastring), where execution picks a matching
rule at random.  The output is therefore non-deterministic, and like DSDLAI
the interpreter would be faithful but its behavior only testable
mechanically; it also has no I/O, so it is a self-contained interpreter.  A
genuine Category:Unimplemented gap.

### COD (low priority)
A two-dimensional concurrency-heavy language of cods swimming in waves
enclosed ponds, where each cod carries an unbounded integer and `+`/`-`
duplicate or remove it.  Branches resolve to random directions, so like
LaserFuck/DSDLAI the output is non-deterministic but the interpreter can be
faithful to the spec.  It has I/O (`...` input, `---` output).  A genuine
Category:Unimplemented gap.

N Refine was considered here but dropped: it is Category:Implemented (an
interpreter exists on GitHub), so by this roadmap's rule it is not a gap.

Grapheme previously listed here is done: the interpreter covers the four
modes, the arithmetic/stack commands, the untyped variable system, and
function execution (`G`/`I`/`Q`/`Z`), and its only wiki example that can
run (Hello World) verifies.  It has no text generator — strings cannot
contain `E`, so even "HELLO" is unspellable — nor a boolean generator (the
wiki's truth-machine cannot even read its `"0"`/`"1"` input as a clean bit);
both walls are recorded in `docs/limitations.md`.

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

Forbin previously listed here is done: the interpreter covers function
definitions (including nested and higher-order), iteration and range loops
(``0..1`` iterates twice, so ranges double as if-statements), NOT, and the
bit ``in``/``out`` builtins; the text generator emits one ``out`` line per
byte.  Two of the wiki's examples are not reproduced — the cat is buggy
(its ``for _:0..1`` "while" doubles every byte; the language was
unimplemented, so it was never run) — and the entry point is ``main`` with a
dummy argument, per the examples.

ROTfuck previously listed here is done: the interpreter treats each
executed command as advancing every source character one step along
`+-><,.[]`, brackets are matched on the source (partners stay fixed as
positions do; a partnerless executed bracket halts), and the text generator
emits straight-line programs by placing the ``i``-fold inverse rotation of
each desired command at position ``i``.  The loop wall is recorded in
`docs/limitations.md`: a rotating program cannot keep its bracket pair in
place, so no iterative loop is expressible and the generator is
straight-line.

Decleq previously listed here is done: the memory-mapped I/O falls through
(the `-2` output and `-1` input do not jump), `a b c` stores `memory[a]-1`
into `memory[b]` and jumps when it is `<= 0`, and the generator simply
places each byte in a data cell and prints it with a `-2` instruction, so
the program is linear and compact.

## Lean proofs (in priority order)

Kept proofs: MAMMALIAN generator totality (`extra/lean/esolangs/Esolangs.lean`)
and Factor's Dirichlet totality / encode-decode round-trip
(`FactorCorrect.lean`).  Everything else in the Lean project was dropped:
the four ported interpreters, their equivalence proofs, and all the
generator and boolean correctness proofs were redundant with the round-trip
test suite, so the Lean project now contains only the proofs of facts the
tests cannot establish (MAMMALIAN's search totality, Factor's prime-search
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
differential/round-trip tests already establish): EXCON, AlbaBet, CircleFuck,
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
(ArrowQueue, Back, BitDeque, DSDLAI, Keys, Lightlang, Minsky Swap, Movesum,
RAM0, A Painter Ant) either have no output, print numeric state, print a
fixed string, or print their final grid, so none can emit arbitrary text.
ABCDirection is the one exception: its Boolfuck output can emit arbitrary
bits, but moving the tape pointer between outputs needs the full 2D routing
that makes a text generator a routing problem rather than an arithmetic one.
The newly assessed boolean candidates that fell through (Temporary, Movesum,
WII2D, EXCON, Huf, Lightlang, DSDLAI) are recorded in `docs/limitations.md`.

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
