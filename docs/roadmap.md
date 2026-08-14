# Roadmap

Planned work, in priority order.  Language assessments, documented walls,
and ruled-out ideas live in `docs/limitations.md`; completed ideas live in
the commit history.  This file only tracks what is still on the table.

## New interpreters: exhausted

Every candidate from the esolangs wiki's Category:Unimplemented with a usable
file-based I/O protocol, a complete specification, and a plausible generator
or boolean story now has an interpreter.  Ruled-out candidates (Gravity,
Earfuck, Conveyor, Chainlang, Binary ///, Fourfuck, Aaargh++, Bitwise Cyclic
Teast) are recorded in `docs/limitations.md`, and A Painter Ant, the last
addition, ships as a no-I/O grid interpreter whose final state is printed as
an observability convention.

## Boolean generators (in priority order)

### 123 boolean generator for one input (low priority)
The ``3`` jump does not route a decision tree: a TRUE bit jumps to the
*nearest preceding* ``3`` and a FALSE bit to the nearest following one (not
bracket-matched), so the only constructible pattern is a "repeat the region
before the ``3`` while TRUE" loop, and no ``3``-based branch is found at any
length (a random search finds no NOT even at n == 1).  The single data byte
also makes multi-bit state impossible (every read overwrites it).  The four
one-input functions are pure bit arithmetic, however, so a generator covers
n == 1 (const-0, identity, NOT, const-1) and n >= 2 stays a wall; the
reachable set is recorded in `docs/limitations.md`.

### Minifuck partial boolean generator (medium priority)
The documented wall was re-verified and is *partially wrong*: a search past
the original length-14 cap finds NOT and const-1 for one input (lengths
17-18), so all four one-input functions are reachable; the two-input set is
still the 0-preserving eight (AND, OR, XOR, echoes, const-0), with the
non-0-preserving tables (XNOR, NAND, NOR, NOT-b) unfound to length 34.  A
generator covering n == 1 fully plus the n == 2 0-preserving subset is now
worth building; the exact reachable set is recorded in `docs/limitations.md`.

Painfuck previously listed here is done: its ``a``/``b`` while-nonzero loops
and ``j``/``u`` byte I/O make it brainfuck-compatible, so the brainfuck
minterm and decision-tree strategies translate directly (``>`` maps to
``rl`` since ``r`` moves +2 and ``l`` -1, and the source is pre-shifted
through the interpreter's substitution cycles).

bit~ previously listed here is done: each ``)`` read leaves the input bit at
``8i+7`` with the ``00110000`` byte pattern in the low cells, every (input,
constant) cell a minterm tests is pre-copied unconditionally (so a skipped
branch cannot break the copy chain), and each ``1`` row is a nested
``{ bit ... }`` test that forces the result cell, printed as ``48 + result``.

## Lean proofs (in priority order)

Completed proofs live in the commit history: MAMMALIAN generator totality
(`extra/lean/esolangs/Esolangs.lean`), EXCON generator correctness
(`ExconCorrect.lean`), CircleFuck generator correctness
(`CircleFuckCorrect.lean`), BF-PDA bracket matching (`BfpdaCorrect.lean`),
EXCON interpreter equivalence (`ExconSemanticsCorrect.lean`), AlbaBet
generator correctness (`AlbabetCorrect.lean`), AlbaBet interpreter
equivalence (`AlbabetSemanticsCorrect.lean`), Number Seventy-Four
interpreter equivalence (`SeventyFourSemanticsCorrect.lean`), BF-PDA
interpreter equivalence (`BfpdaSemanticsCorrect.lean`), the Sophie, BIO,
6-5, and Qoibl generator correctness proofs (`SophieCorrect.lean`,
`BioCorrect.lean`, `SixFiveCorrect.lean`, `QoiblCorrect.lean`), and the
`_bf_set` multiply loop (`BfSetCorrect.lean`).  The candidates below go
beyond totality, in increasing payoff order.

### Factor: Dirichlet totality and encode/decode round-trip (medium priority)
`_factor_encode` (`tools/generators/tape.py`) searches for a prime with a given
residue mod 11; totality needs mathlib's Dirichlet theorem
(`exists_prime_modEq_of_coprime`).  The round-trip is the interesting half:
prove decoding the prime factorization (exponents folding runs, residue mod 11
identifying each instruction) recovers the original brainfuck program.

### Lean interpreter equivalence (medium priority)
Done.  All four ported Lean interpreters are proved to match their Python
references: BF-PDA's `find` bracket matching and full output semantics
(`BfpdaCorrect.lean`, `BfpdaSemanticsCorrect.lean`), EXCON's output
semantics, AlbaBet's output semantics, and seventy_four's output semantics
(`ExconSemanticsCorrect.lean`, `AlbabetSemanticsCorrect.lean`,
`SeventyFourSemanticsCorrect.lean`).  The guards reflect where the
interpreters genuinely diverge: EXCON's pointer underflow (the reference
raises `HaltError`, the port wraps), AlbaBet's invalid-scalar `i` (the
reference zeroes `x`), seventy_four's pass-boundary halting, and BF-PDA's
bracket validation (the reference rejects unbalanced brackets up front).

### Simple text generator correctness proofs (medium priority)
Done.  The four small generator/interpreter pairs are proved correct through
the interpreters' own transitions (`SophieCorrect.lean`, `BioCorrect.lean`,
`SixFiveCorrect.lean`, `QoiblCorrect.lean`): Sophie's `#<char>,` accumulator
load-and-print, BIO's `1`-prefix repeat blocks driving `x` between values,
6-5's 6/2 and 9/5 runs moving the cell by divmod arithmetic, and Qoibl's
`tt y|e ... tt` binary decoding.  Remaining under this umbrella: huf's
`# +*a | +*b ! +*r >@` segments share the multiply-loop invariant with
`_bf_set` below.

### `_bf_set` multiply loop (low priority)
Done.  `BfSetCorrect.lean` models a minimal brainfuck interpreter and proves
the `+a[>+b<-]>+r.` invariant (`tools/generators/tape.py::_bf_set`): after
`a` iterations of `[>+b<-]` the first cell is zeroed and the second holds
`a*b`, so the printed cell holds `a*b + r = value`.  This unblocks the huf
generator proof below.

## Toolchain consolidation

Done.  The `extra/` cross-check implementations are consolidated onto two
native toolchains plus Lean: one systems language (Rust) and one ISA
(RISC-V).  The C++ and Ruby cross-checks moved into `extra/rust` (Forþ,
Basicfuck, 2dFish, Painfuck, %^2^-1, Kak, Trash, bit~, 3x, LaserFuck,
Unsquare, and a pass-boundary Number Seventy-Four — the Lean port has
diverged semantics); the x86 reference interpreters (123, 2 Bits 1 Byte,
Brainpocalypse, NoComment, Stun Step) and the assembly compilers in
`src/esolangs/compilers/assembly/` (bfstack, home-row, jaune, suffolk,
unsquare) now emit/run RISC-V; and the x86/nasm toolchain is dropped.  The
differential corpora in `scripts/verify_differential.py`, the generator
round-trips in `scripts/verify_extra_generators.py`, and the RISC-V unicorn
round-trips in `scripts/verify_riscv_unicorn.py` were the acceptance tests.

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
