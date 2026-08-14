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
Grapheme and Point Break, both Category:Unimplemented; the rest of that
list is either implemented, a joke, non-deterministic, no-I/O, or
file/OS-based, and is recorded in `docs/limitations.md`.

### Grapheme (high priority)
A Turing-complete stack language where every command is a single uppercase
Latin letter, with normal/intmode/stringmode/funcmode, an untyped variable
system, and full I/O (`W` reads a string, `Y` outputs).  Fully specified
with working Hello World, cat, and truth-machine examples, and it is a
genuine Category:Unimplemented gap.

### Point Break (low priority)
A Turing-complete language with four commands (`LET`, `POINT`, `BREAK`,
`END`) that simulates Minsky machines; `?` reads an integer in a `LET`.  It
has no output at all, so like Crement and A Painter Ant it can only be a
self-contained interpreter without a generator.  A genuine
Category:Unimplemented gap.

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

Completed proofs live in the commit history: MAMMALIAN generator totality
(`extra/lean/esolangs/Esolangs.lean`), CircleFuck generator correctness
(`CircleFuckCorrect.lean`), the Sophie, BIO,
6-5, and Qoibl generator correctness proofs (`SophieCorrect.lean`,
`BioCorrect.lean`, `SixFiveCorrect.lean`, `QoiblCorrect.lean`), the
`_bf_set` multiply loop (`BfSetCorrect.lean`), the huf generator
correctness proof (`HufCorrect.lean`), the brainfuck generator correctness
proof (`BfCorrect.lean`), the Eval generator correctness proof
(`EvalCorrect.lean`), the Factor Dirichlet totality /
encode-decode round-trip (`FactorCorrect.lean`), the Collatz Multiverse
generator correctness proof (`CollatzMultiverseCorrect.lean`), and the
Sophie and 6-5 boolean-function generator correctness proofs
(`SophieBoolCorrect.lean`, `SixFiveBoolCorrect.lean`).  The four ported
Lean interpreters, their equivalence proofs, and the EXCON and AlbaBet text
generator proofs (whose models were the ports) were dropped: the ports were
redundant with the Python interpreters and the equivalence proofs only
certified them, so neither earned the maintenance cost.  The candidates
below go beyond totality, in increasing payoff order.

### Factor: Dirichlet totality and encode/decode round-trip (medium priority)
Done.  `FactorCorrect.lean` models the commands/residues, the run-length
machinery, and the prime search `nextPrimeWithRes`, whose totality is exactly
mathlib's Dirichlet theorem (`Nat.forall_exists_prime_gt_and_modEq`).  The
round-trip `decodeRuns_encodeRuns` / `decode_encode` proves the sorted distinct
prime factors of the encoded integer are precisely the chosen primes, in
order, with the right exponents (`encodeRuns_factorization_at`,
`chosenExp_pos_iff`, `primeFactors_encodeRuns`).

### Boolean generator correctness proofs (low priority)
The boolean-function generators (`tools/generators/booleans/`) emit, for a
truth table, a program that reads the input bits and prints the table's
output.  Correctness proofs run the generated program through the
interpreter's own transitions for every input combination.  Done: the Sophie
decision tree (`SophieBoolCorrect.lean`) and the 6-5 decision tree
(`SixFiveBoolCorrect.lean`) — `B` + eight `2`s normalize each bit to 8/9,
`78` skips the `8n` jump on a zero bit and the `4` markers route a one bit,
and `treeOf_correct` shows reading the input bits descends to the leaf for
the indexed row.  The brainfuck minterm (`_bf_minterm`) is the shared core
for painfuck/ascii_art/three_d_bf/dimensional but needs the bf model
extended with ``,`` input and the copy/AND scratch machinery, so it is a
larger effort.

### Minifuck boolean reachability (low priority)
A language-power theorem rather than a generator-correctness proof: Minifuck
computes exactly the four one-input functions plus the eight 0-preserving
two-input tables (`f(0, 0) == 0`), because `[` followed by `<` is a
conditional pointer move that leaves the tested bit's value in the pointer
displacement, and the decode suffix pins the pointer orientation so no
complemented read can select the other tables (re-verified in
`docs/limitations.md`).  The reachable half is a machine analysis of the
`[<`-walk and the suffix search; the wall is structural.

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

Still worth doing, low priority.  `CollatzMultiverseCorrect.lean` models the
register interpreter's Collatz transform and proves the constant-table
bootstrap reaches every byte value and the output lines print the bytes.
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
