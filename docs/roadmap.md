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

### 123 decision-tree generator (medium priority)
The ``3`` jump does not route a decision tree cleanly: a TRUE bit jumps to
the *nearest preceding* ``3`` and a FALSE bit to the nearest following one
(not bracket-matched), so the constructible pattern is a "repeat the region
before the ``3`` while TRUE" loop rather than a branch, and a random search
finds no ``3``-based NOT even at n == 1.  The single data byte also makes
multi-bit state impossible (every read overwrites it), so the generator
would need a genuinely new construction, not an adaptation.

### bit~ generator (medium priority)
A bit pool with ``{``/``}`` loops and byte I/O, so boolean logic is its
native idiom; the main open question is normalizing a read byte down to the
single bit a tree level tests.

### Minifuck partial boolean generator (low priority)
The documented wall caps Minifuck at 0-preserving tables with `n <= 3`.  A
generator for exactly that subset is possible but low value; the working
prefixes and the exact reachable table set are recorded in
`docs/limitations.md`.

Painfuck previously listed here is done: its ``a``/``b`` while-nonzero loops
and ``j``/``u`` byte I/O make it brainfuck-compatible, so the brainfuck
minterm and decision-tree strategies translate directly (``>`` maps to
``rl`` since ``r`` moves +2 and ``l`` -1, and the source is pre-shifted
through the interpreter's substitution cycles).

## Lean proofs (in priority order)

Completed proofs live in the commit history: MAMMALIAN generator totality
(`extra/lean/esolangs/Esolangs.lean`), EXCON generator correctness
(`ExconCorrect.lean`), CircleFuck generator correctness
(`CircleFuckCorrect.lean`), BF-PDA bracket matching (`BfpdaCorrect.lean`),
EXCON interpreter equivalence (`ExconSemanticsCorrect.lean`), AlbaBet
generator correctness (`AlbabetCorrect.lean`), AlbaBet interpreter
equivalence (`AlbabetSemanticsCorrect.lean`), Number Seventy-Four
interpreter equivalence (`SeventyFourSemanticsCorrect.lean`), BF-PDA
interpreter equivalence (`BfpdaSemanticsCorrect.lean`), and the Sophie,
BIO, 6-5, and Qoibl generator correctness proofs (`SophieCorrect.lean`,
`BioCorrect.lean`, `SixFiveCorrect.lean`, `QoiblCorrect.lean`).  The
candidates below go beyond totality, in increasing payoff order.

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
A Hoare-style invariant for `+a[>+b<-]>+r.` (`tools/generators/tape.py::_bf_set`):
after the loop the printed cell holds `a*b + r = value`.  Genuine but generic
brainfuck reasoning.

## Toolchain consolidation (in priority order)

Consolidate the `extra/` cross-check implementations onto fewer toolchains:
one systems language (Rust) and one ISA (RISC-V), with Lean kept for proofs.
The differential corpora in `scripts/verify_differential.py` and the generator
round-trips in `scripts/verify_extra_generators.py` are the acceptance test:
a port is done when the same corpora pass against the new binary.

The C++ and Ruby cross-checks are done: every native oracle now lives in
`extra/rust` (Forþ, Basicfuck, 2dFish, Painfuck, %^2^-1, Kak, Trash, bit~,
3x, LaserFuck, Unsquare, and a pass-boundary Number Seventy-Four — the Lean
port has diverged semantics), and the `cxx` and Ruby parts of CI are gone.

### Port x86 reference interpreters to RISC-V (medium priority)
`extra/assembly/`'s x86 refs (123, 2 Bits 1 Byte, Brainpocalypse, NoComment,
Stun Step) follow the existing `123-riscv.s` port; the Python RISC-V simulator
and ELF runner already exist.  The x86 compilers in
`src/esolangs/compilers/assembly/` are the hard part: they emit x86 and are
verified under unicorn, so they must be ported to emit RISC-V too before the
nasm/unicorn toolchain and the x86 refs can be dropped.

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
