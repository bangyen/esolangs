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
scan.  A second pass over the PythonshellDebugwindow languages produced the
batch below (Jumplang, ROTfuck, UFSA, Suptiftam, Stackint, Queuenanimous);
the joke, non-deterministic, no-I/O, and file/OS-based ones from that list
are recorded in `docs/limitations.md`.

### Jumplang (high priority)
A Turing-complete brainfuck derivative that replaces the loops with `?`
(skip the next command if the cell is zero) and `!` (absolute jump to the
`cell pointer + 1`th command; jumping out of bounds halts), plus `^`/`v`
that step by 2.  Well specified with a cat example, and as a brainfuck
family member with full I/O it has a text-generator and boolean story.

### ROTfuck (high priority)
A Turing-complete brainfuck variant where every executed command rotates
all non-comment characters of the source one step along `+-><,.[]`.  The
program text is self-modifying, but the spec is complete and there is a
Hello World; the rotation-invariant construction is the interesting part.

### UFSA (high priority)
A finite-state-automaton meta-language: the first line names the initial
and halt states, and each later line is `original transition trigger`
followed by optional output tokens (`\*N*` octal escapes, `\\`).  Simple,
deterministic, and fully specified with Hello World, cat, and truth-machine
examples, and full I/O.

### Suptiftam (medium priority)
Two-dimensional tape-tapes of bytes or integers, permissive function
definitions, includes, and I/O via the `read`/`term` tapes.  The spec is
complete but has undefined behaviors and its examples are untested, so it is
a heavier, riskier implementation.

### Stackint (medium priority)
A stack-based language with `?`/`!` computed jumps, arithmetic, and
duplication.  Deterministic and well specified, but the only output is the
stack printed as an array at the end of the program, which fits the repo's
print-text protocol only awkwardly.

### Queuenanimous (low priority)
A Turing-complete queue-based language (`0 + - >` and while loops) with a
complete translation table.  It has no I/O, so like Crement and A Painter
Ant it can only be a self-contained interpreter without a generator.

### Crement (low priority)
A self-modifying language with ADDRESS/DATA/JUMP opcodes and a polarity
field, fully specified including a Minsky-machine reduction.  It has no
I/O, so like A Painter Ant it can only be a self-contained interpreter
without a generator.

Decleq previously listed here is done: the memory-mapped I/O falls through
(the `-2` output and `-1` input do not jump), `a b c` stores `memory[a]-1`
into `memory[b]` and jumps when it is `<= 0`, and the generator simply
places each byte in a data cell and prints it with a `-2` instruction, so
the program is linear and compact.

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
`_bf_set` multiply loop (`BfSetCorrect.lean`), the huf generator
correctness proof (`HufCorrect.lean`), the brainfuck generator correctness
proof (`BfCorrect.lean`), the Eval generator correctness proof
(`EvalCorrect.lean`), the 3D Brainfuck generator correctness proof
(`ThreeDbfCorrect.lean`), and the Factor Dirichlet totality /
encode-decode round-trip (`FactorCorrect.lean`).  The candidates below go beyond
totality, in increasing payoff order.

### Factor: Dirichlet totality and encode/decode round-trip (medium priority)
Done.  `FactorCorrect.lean` models the commands/residues, the run-length
machinery, and the prime search `nextPrimeWithRes`, whose totality is exactly
mathlib's Dirichlet theorem (`Nat.forall_exists_prime_gt_and_modEq`).  The
round-trip `decodeRuns_encodeRuns` / `decode_encode` proves the sorted distinct
prime factors of the encoded integer are precisely the chosen primes, in
order, with the right exponents (`encodeRuns_factorization_at`,
`chosenExp_pos_iff`, `primeFactors_encodeRuns`).

### Huf text generator correctness proof (medium priority)
Done.  `HufCorrect.lean` models the register interpreter (`num`/`mul`/output,
`step`, `run` as a foldl) and proves huf's `# +*a | +*b ! +*r >@` segments
correct through the interpreter's own transitions: `seg_correct` reuses the
`_bf_set` multiply invariant (`tools/generators/tape.py::_bf_set`), the
segment prints `a*b + r`, and `progAux_correct` / `huf_value` compose
segments for a whole text.

### Remaining generator correctness proofs (low priority)
Done: `bf` and `eval`.  `BfCorrect.lean` completes the `_bf_set` multiply-loop
work over the brainfuck interpreter model: the per-character choice
(delta-reuse when the next character is close, else `[-]` + `_bf_set`) moves
the pointer right one cell and prints exactly the text (`run_minusN`,
`run_zero`, `bf_set_at`, `progAux_correct`).  `EvalCorrect.lean` proves the
backtick-escaped string literal `"<text with " → \`>".` over Eval's
two-stack interpreter: the literal scan round-trips backticks to quotes
(`scan_aux`) and `.` prints the text (`eval_correct`).

Still worth doing, low priority.  `collatz_multiverse` has a substantive
in-progress proof (`CollatzMultiverseCorrect.lean`) modeling the register
interpreter's Collatz transform and the constant-table bootstrap.
`ascii_art` reduces to a mechanical per-command rendering round-trip
(`parse (bf_to_ascii_art prog) = prog`) over the `BfCorrect` proof.  `suffolk`
is bf-family (its `!` op) and reuses the bf model structure.  The rest
(three_d_bf, dig, polynomial, wii2d, dotlang, bfstack, brainif, minifuck,
add_sub_jump) are full language-specific interpreter models for obscure
languages, so they are dropped rather than restated.

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
