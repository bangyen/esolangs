# Roadmap

Planned work, in priority order.  Language assessments, documented walls,
and ruled-out ideas live in `docs/limitations.md`; completed ideas live in
the commit history.  This file only tracks what is still on the table.

## New interpreters (in priority order)

Candidates from the esolangs wiki's Category:Unimplemented with a usable
file-based I/O protocol, a complete specification, and a plausible generator
or boolean story.  Ruled-out candidates (Gravity, Earfuck, Conveyor,
Chainlang, Binary ///, Fourfuck, Aaargh++, Bitwise Cyclic Teast) are recorded
in `docs/limitations.md`.

### 3D Brainfuck (high priority)
A brainfuck variant whose tape, block grid, and instruction pointer are all
three-dimensional (`esolangs.org/wiki/3D_Brainfuck`).  Full `,`/`.` I/O and
Turing complete, with a completely specified instruction set.  Fits
`tape_based`; a text generator can be derived from the existing brainfuck one
by encoding the 1D tape traversal onto the 3D grid.

### ABCDirection (medium priority)
A 2D `A`/`B`/`C`/`D` language with a bit tape and a queue
(`esolangs.org/wiki/ABCDirection`).  Boolfuck-style I/O and Turing complete.
The spec leaves a few edge cases open (donut wrapping, empty-queue start,
queue/tape initialization); those need to be pinned down as conventions before
an interpreter can be verified.

### Collatz Multiverse (medium priority)
An OISC where each line is `[var1] = [var2] x + [var3], [DO|NOT] PRINT`
(`esolangs.org/wiki/Collatz_Multiverse`).  Real input via the `input` special
variable, `DO`/`NOT` conditional printing, arrays, and `lineNumber` for jumps.
The spec is slightly loose but implementable.

### A Painter Ant (low priority)
A grid-based ant language with conditional movement and unconditional painting
(`esolangs.org/wiki/A_Painter_Ant`).  Well-specified and Turing complete, but
has no I/O, so it can only be a self-contained interpreter (like the existing
C++/Lean extras) without a generator.

## Boolean generators (in priority order)

### Minifuck partial boolean generator (low priority)
The documented wall caps Minifuck at 0-preserving tables with `n <= 3`.  A
generator for exactly that subset is possible but low value; the working
prefixes and the exact reachable table set are recorded in
`docs/limitations.md`.

## Lean proofs (in priority order)

Completed proofs live in the commit history: MAMMALIAN generator totality
(`extra/lean/esolangs/Esolangs.lean`), EXCON generator correctness
(`ExconCorrect.lean`), CircleFuck generator correctness
(`CircleFuckCorrect.lean`), and BF-PDA bracket matching
(`BfpdaCorrect.lean`).  The candidates below go beyond totality, in
increasing payoff order.

### Factor: Dirichlet totality and encode/decode round-trip (medium priority)
`_factor_encode` (`tools/generators/tape.py`) searches for a prime with a given
residue mod 11; totality needs mathlib's Dirichlet theorem
(`exists_prime_modEq_of_coprime`).  The round-trip is the interesting half:
prove decoding the prime factorization (exponents folding runs, residue mod 11
identifying each instruction) recovers the original brainfuck program.

### Lean interpreter equivalence (medium priority)
Prove the ported Lean interpreters match their Python references.  BF-PDA's
`find` bracket matching is done.  Remaining: EXCON's output semantics (that
the port's `to_s`/state transitions match `src/esolangs/interpreters/tape_based/excon.py`,
building on the fixed `pool[0]` handling) and the other ported interpreters.

### Albabet text generator and correctness (medium priority)
Albabet's `i` prints the accumulator as a character, so it can emit arbitrary
bytes; the extra/ roadmap note calling its output class "narrow" is
inaccurate.  Build the missing text generator (drive `x` to each byte and
print, like EXCON), round-trip it against the interpreter, then prove its
correctness.  This is new feature work, not just a proof.

### `_bf_set` multiply loop (low priority)
A Hoare-style invariant for `+a[>+b<-]>+r.` (`tools/generators/tape.py::_bf_set`):
after the loop the printed cell holds `a*b + r = value`.  Genuine but generic
brainfuck reasoning.

## Text generators: exhausted

Every language whose interpreter can emit arbitrary bytes already has a text
generator, except Albabet (see the Lean proofs section, which tracks building
and proving its generator).  The remaining interpreter-only languages
(ArrowQueue, Back, BitDeque, DSDLAI, Keys, Lightlang, Minsky Swap, Movesum,
RAM0) either have no output, print numeric state, or print a fixed string, so
none can emit arbitrary text.  The newly assessed boolean candidates that fell
through (Temporary, Movesum, WII2D, EXCON, Huf, Lightlang, DSDLAI) are
recorded in `docs/limitations.md`.
