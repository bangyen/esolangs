# Roadmap

Planned work, in priority order.  Language assessments, documented walls,
and ruled-out ideas live in `docs/limitations.md`; completed ideas live in
the commit history.  This file only tracks what is still on the table.

## New interpreters (in priority order)

Candidates from re-scanning the esolangs wiki's Category:Unimplemented.  The
original scan is exhausted: every candidate with a usable file-based I/O
protocol, a complete specification, and a plausible generator or boolean
story now has an interpreter.  Ruled-out candidates (Gravity, Earfuck,
Conveyor, Chainlang, Binary ///, Fourfuck, Aaargh++, Bitwise Cyclic Teast)
are recorded in `docs/limitations.md`, and A Painter Ant (a no-I/O grid
interpreter) and AddSubJump (a self-modifying OISC with a text generator)
shipped from that scan.

### Decleq (medium priority)
An OISC whose instruction `a b c` means `b = a - 1`, then jump to `c` if
`b <= 0`, with optional memory-mapped I/O (`-2` outputs, `-1` reads).  The
wiki page is a stub, so the loose edges (unconditional fall-through, jump
targets, the I/O protocol) need pinning down as conventions before an
interpreter can be verified.  A decrement-based text generator is plausible
(OISC value-building like AddSubJump).

### Crement (low priority)
A self-modifying language with ADDRESS/DATA/JUMP opcodes and a polarity
field, fully specified including a Minsky-machine reduction.  It has no
I/O, so like A Painter Ant it can only be a self-contained interpreter
without a generator.

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
`BioCorrect.lean`, `SixFiveCorrect.lean`, `QoiblCorrect.lean`), the
`_bf_set` multiply loop (`BfSetCorrect.lean`), and the huf generator
correctness proof (`HufCorrect.lean`).  The candidates below go beyond
totality, in increasing payoff order.

### Factor: Dirichlet totality and encode/decode round-trip (medium priority)
`_factor_encode` (`tools/generators/tape.py`) searches for a prime with a given
residue mod 11; totality needs mathlib's Dirichlet theorem
(`exists_prime_modEq_of_coprime`).  The round-trip is the interesting half:
prove decoding the prime factorization (exponents folding runs, residue mod 11
identifying each instruction) recovers the original brainfuck program.

### Huf text generator correctness proof (medium priority)
Done.  `HufCorrect.lean` models the register interpreter (`num`/`mul`/output,
`step`, `run` as a foldl) and proves huf's `# +*a | +*b ! +*r >@` segments
correct through the interpreter's own transitions: `seg_correct` reuses the
`_bf_set` multiply invariant (`tools/generators/tape.py::_bf_set`), the
segment prints `a*b + r`, and `progAux_correct` / `huf_value` compose
segments for a whole text.

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
