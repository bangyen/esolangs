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

## Python interpreters for the extra/ languages (in priority order)

Nine languages already have a native (C++/Ruby/Rust/assembly) implementation in
`extra/` and a generator that is round-trip verified against it, but no Python
interpreter.  An in-package interpreter completes the standard workflow
(generator -> interpreter -> round-trip test in `tests/`) and makes
`esolangs run <language>` work.  The remaining `extra/` languages (Kak, Trash,
Number Seventy-Four, 2 Bits 1 Byte, Brainpocalypse, Stun Step, Albabet, BF-PDA)
have no generator (narrow output classes / no file-based I/O) and are ruled
out here.

### 123 (high priority)
An x86/RISC-V assembly reference (`esolangs.org/wiki/123`).  Its generator is
already differentially verified across the x86 and RISC-V interpreters and
`scripts/riscv_sim.py`, which implements the bytecode fetch/execute loop in
Python — a natural starting point for the interpreter.

### Forþ (high priority)
A C++ reference (`esolangs.org/wiki/For%C3%BE`); both its text and boolean
generators are verified against it.

### Basicfuck (medium priority)
A C++ reference (`esolangs.org/wiki/Basicfuck`); text and boolean generators
verified.

### 3x (medium priority)
A Ruby reference (`esolangs.org/wiki/3x`); text and boolean generators
verified.

### Unsquare (medium priority)
Ruby and Rust references (`esolangs.org/wiki/Unsquare`); text and boolean
generators verified, plus x86 and C compilers.

### %^2^-1 (medium priority)
A C++ reference (`esolangs.org/wiki/%25%5E2%5E-1`); text generator verified.

### 2dFish (medium priority)
A C++ reference (`esolangs.org/wiki/2dFish`); text generator verified.

### Painfuck (medium priority)
A C++ reference (`esolangs.org/wiki/Painfuck`); text generator verified.

### bit~ (low priority)
A Ruby reference (`esolangs.org/wiki/Bit~`); text generator verified.

## Boolean generators (in priority order)

### Minifuck partial boolean generator (low priority)
The documented wall caps Minifuck at 0-preserving tables with `n <= 3`.  A
generator for exactly that subset is possible but low value; the working
prefixes and the exact reachable table set are recorded in
`docs/limitations.md`.

## Lean proofs (in priority order)

The MAMMALIAN generator totality proof (`extra/lean/esolangs/Esolangs.lean`)
establishes the per-character search never fails.  The candidates below go
beyond totality, in increasing payoff order.

### EXCON generator-to-interpreter correctness (high priority)
Prove that running the Lean EXCON interpreter port (`Esolangs/Excon.lean`) on
the program from the `excon` generator (`tools/generators/tape.py`) prints the
input text exactly: a bit-flip induction over the 8-cell pool, reconciling the
generator's MSB-first flips with `to_s`'s bit order.  The first *correctness*
(not totality) result, and it connects a generator proof to an interpreter
proof already in the repo.

### Factor: Dirichlet totality and encode/decode round-trip (medium priority)
`_factor_encode` (`tools/generators/tape.py`) searches for a prime with a given
residue mod 11; totality needs mathlib's Dirichlet theorem
(`exists_prime_modEq_of_coprime`).  The round-trip is the interesting half:
prove decoding the prime factorization (exponents folding runs, residue mod 11
identifying each instruction) recovers the original brainfuck program.

### CircleFuck self-referential tape correctness (medium priority)
The tape is the program text, so correctness is a fixpoint over the program's
own encoding (`tools/generators/tape.py::circlefuck`): each cell's base is the
instruction that occupies it, and the `% 256` shortest run must land each cell
on its target.

### Lean interpreter equivalence (medium priority)
Prove the ported Lean interpreters match their Python references, starting
with `bfpda`'s `find` bracket matching (`Esolangs/bfpda.lean`) — that the
iterator walk terminates and lands on the matching bracket — and EXCON's
output semantics.  Lifts the "faithful port" README claim into a proof.

### `_bf_set` multiply loop (low priority)
A Hoare-style invariant for `+a[>+b<-]>+r.` (`tools/generators/tape.py::_bf_set`):
after the loop the printed cell holds `a*b + r = value`.  Genuine but generic
brainfuck reasoning.

## Text generators: exhausted

Every language whose interpreter can emit arbitrary bytes already has a text
generator.  The remaining interpreter-only languages (ArrowQueue, Back,
BitDeque, DSDLAI, Keys, Lightlang, Minsky Swap, Movesum, RAM0) either have no
output, print numeric state, or print a fixed string, so none can emit
arbitrary text.  The newly assessed boolean candidates that fell through
(Temporary, Movesum, WII2D, EXCON, Huf, Lightlang, DSDLAI) are recorded in
`docs/limitations.md`.
