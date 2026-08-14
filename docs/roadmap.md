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
(`CircleFuckCorrect.lean`), BF-PDA bracket matching (`BfpdaCorrect.lean`),
EXCON interpreter equivalence (`ExconSemanticsCorrect.lean`), AlbaBet
generator correctness (`AlbabetCorrect.lean`), AlbaBet interpreter
equivalence (`AlbabetSemanticsCorrect.lean`), and Number Seventy-Four
interpreter equivalence (`SeventyFourSemanticsCorrect.lean`).  The
candidates below go beyond totality, in increasing payoff order.

### Factor: Dirichlet totality and encode/decode round-trip (medium priority)
`_factor_encode` (`tools/generators/tape.py`) searches for a prime with a given
residue mod 11; totality needs mathlib's Dirichlet theorem
(`exists_prime_modEq_of_coprime`).  The round-trip is the interesting half:
prove decoding the prime factorization (exponents folding runs, residue mod 11
identifying each instruction) recovers the original brainfuck program.

### Lean interpreter equivalence (medium priority)
Prove the ported Lean interpreters match their Python references.  BF-PDA's
`find` bracket matching, EXCON's output semantics, AlbaBet's output
semantics, and seventy_four's output semantics are done (`BfpdaCorrect.lean`,
`ExconSemanticsCorrect.lean`, `AlbabetSemanticsCorrect.lean`,
`SeventyFourSemanticsCorrect.lean`): for EXCON, programs that do not underflow
the pointer; for AlbaBet, programs that never run `i` on an invalid scalar
(the reference zeroes `x` there, the port keeps it, and both print NUL, so
only a later `i` can diverge); for seventy_four, programs whose output first
starts with `H` at the last meaningful command (the reference halts at pass
boundaries, the port mid-pass, so they agree only there).  Remaining:
BF-PDA's full output semantics (a stack-and-loop proof building on the
completed `find` bracket matching).

### Simple text generator correctness proofs (medium priority)
A correctness proof for the small generator/interpreter pairs, run through
the interpreter's own transitions as in `AlbabetCorrect.lean`: Sophie
(`#<char>,` loads the code into the accumulator and prints it), BIO (the
generator emits only `0ox`/`1ox`/`1ix`, driving `x` from the previous value
to the next — the AlbaBet proof with deltas instead of resets), 6-5
(`_six_five_path`'s 6/2 and 9/5 runs with 62/95 pairs move the cell exactly;
pure divmod arithmetic on one cell), and Qoibl (`tt y|e ... tt` prints the
value the digits encode; a binary-decoding induction).  huf's
`# +*a | +*b ! +*r >@` segments share the multiply-loop invariant with
`_bf_set` below.

### `_bf_set` multiply loop (low priority)
A Hoare-style invariant for `+a[>+b<-]>+r.` (`tools/generators/tape.py::_bf_set`):
after the loop the printed cell holds `a*b + r = value`.  Genuine but generic
brainfuck reasoning.

## Toolchain consolidation (in priority order)

Consolidate the `extra/` cross-check implementations onto fewer toolchains:
one systems language (Rust) and one ISA (RISC-V), with Lean kept for proofs.
The differential corpora in `scripts/verify_differential.py` and the generator
round-trips in `scripts/verify_extra_generators.py` are the acceptance test:
a port is done when the same corpora pass against the new binary.

### Port C++ and Ruby cross-checks to Rust (medium priority)
`extra/c++/` (Forþ, Painfuck, 2dFish, %^2^-1, Basicfuck, Kak, Trash) and the
unique Ruby oracles (`extra/ruby/3x.rb`, `bit.rb`) move into the existing
`extra/rust` workspace; the Ruby duplicates (`74.rb` has a Lean twin,
`unsquare.rb` a Rust twin) are deleted outright.  Rust is memory-safe — the
C++ Painfuck reference segfaults on its own corpus, and the asm runner
catches faults — and one cargo workspace replaces the `cxx` and
`extra-languages` CI jobs.  No coverage is lost: every Python interpreter
with a native oracle keeps one.

### Port x86 reference interpreters to RISC-V (medium priority)
`extra/assembly/`'s x86 refs (123, 2 Bits 1 Byte, Brainpocalypse, NoComment,
Stun Step) follow the existing `123-riscv.s` port; the Python RISC-V simulator
and ELF runner already exist.  The x86 compilers in
`src/esolangs/compilers/assembly/` are the hard part: they emit x86 and are
verified under unicorn, so they must be ported to emit RISC-V too before the
nasm/unicorn toolchain and the x86 refs can be dropped.

## Text generators: exhausted

Every language whose interpreter can emit arbitrary bytes already has a text
generator, now including AlbaBet (its `c`+`a`-run+`i` generator and
correctness proof landed with the other Lean proofs).  The remaining
interpreter-only languages (ArrowQueue, Back, BitDeque, DSDLAI, Keys,
Lightlang, Minsky Swap, Movesum, RAM0) either have no output, print numeric
state, or print a fixed string, so none can emit arbitrary text.  The newly
assessed boolean candidates that fell through (Temporary, Movesum, WII2D,
EXCON, Huf, Lightlang, DSDLAI) are recorded in `docs/limitations.md`.
