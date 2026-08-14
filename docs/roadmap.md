# Roadmap

Planned work, in priority order.  Language assessments, documented walls,
and ruled-out ideas live in `docs/limitations.md`; completed ideas live in
the commit history.  This file only tracks what is still on the table.

## New interpreters: exhausted

Every candidate from the esolangs wiki's Category:Unimplemented with a usable
file-based I/O protocol, a complete specification, and a plausible generator
or boolean story now has an interpreter.  Ruled-out candidates (Gravity,
Earfuck, Conveyor, Chainlang, Binary ///, Fourfuck, Aaargh++, Bitwise Cyclic
Teast) are recorded in `docs/limitations.md`.  A Painter Ant (from the
original scan) ships as a no-I/O grid interpreter whose final state is
printed as an observability convention, and AddSubJump (a self-modifying
OISC found by a fresh scan of Category:Unimplemented) ships as a
register-based interpreter with a text generator.  Future additions will
come from re-scanning the category, which keeps gaining new languages.

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

### Huf text generator correctness proof (medium priority)
`BfSetCorrect.lean` unblocked this: huf's `# +*a | +*b ! +*r >@` segments
share the multiply-loop invariant with `_bf_set`
(`tools/generators/tape.py::_bf_set`), so the generator/interpreter proof
follows the same shape as the AlbaBet one, run through the interpreter's own
transitions.

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
