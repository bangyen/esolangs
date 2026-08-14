# Lean proofs for the text generators

## EXCON generator correctness

A proof that the EXCON text generator
(`src/esolangs/tools/generators/tape.py::excon`) is *correct*: for every text
the generated program prints exactly that text.  `ExconCorrect.lean` embeds
the EXCON interpreter's pure state transitions (the 8-cell bit pool,
`gets`/`flips`/`to_s`, which reads the pool back as `128*pool[0] + ... +
pool[7]`) and proves the generator's pointer walk: each set bit of the byte
is flipped exactly once, so ``!`` prints the byte.  The main theorem is
stated for byte-range texts, with the byte range verified by computation.

## MAMMALIAN generator totality

A Lean 4 + mathlib proof that the MAMMALIAN text generator
(`src/esolangs/tools/generators/tape.py::mammalian`) is total over the byte
range: for every byte-range text it emits a program that prints it, and the
per-character search never fails.  (Like the other byte-oriented generators,
`mammalian` rejects codepoints above 255 with a documented `ValueError`
before the search runs.)

### The two structural facts

1. **Number theory** (`even_q_solvable`): every even array `q < 23` has
   `gcd (q+1) 256 = 1`, so the value equation `(q+1)*final ≡ target`
   (mod 256) is always solvable.
2. **Reachability** (`walk_reaches_even`): the SPRINT walk from every
   pointer reaches an even array in steps 1..46 (at SEED count 1 the walk is
   the affine bijection `q ↦ 2q+1 mod 23`, whose orbits have period dividing
   11).  The start array is *not* counted as reached, matching the reference
   walk table.

### Totality (`search_total`)

The per-character search is formalised as `searchOne` (mirroring the
reference generator) and its success is verified by computation over the
full finite state space: 23 pointers × 256 SEED counts × 256 targets.
Reachability uses the same step range (1..46) as the reference
`_mammalian_walk`, so the theorem certifies the actual generator's search:
it never hits the `ValueError` branch.  The reference implementation reports
the same zero failures.

## AlbaBet generator correctness

A proof that the AlbaBet text generator
(`src/esolangs/tools/generators/register.py::albabet`) is *correct*: for
every text the generated program prints exactly that text.  `AlbabetCorrect.lean`
models the tape interpreter's transitions (`a`/`b` move the accumulator, `c`
zeroes it, `i` prints it) and proves the per-character program: `c` zeroes
the accumulator, the `a` run sets it to the byte, and `i` prints it.

## CircleFuck generator correctness

A Lean 4 + mathlib proof (`Esolangs/CircleFuckCorrect.lean`) that the
CircleFuck text generator (`src/esolangs/tools/generators/tape.py::circlefuck`)
is *correct*.  CircleFuck's tape *is* the program text, so the generator reads
the byte already sitting at each cell position and emits the shortest
`+`/`-` run to the target value (mod 256).  The proof shows that running the
generated program through a pure model of the interpreter
(`runInstructions`) prints exactly the text.

The proof has three parts:

1. **The self-reference is consistent.**  The byte the generator reads at
   position `i` (`prog[i]`) really is the value of cell `i` when the data
   pointer first reaches it: blocks are appended rightward, each block's
   instructions lie to the right of the cell they target, and the pointer
   moves exactly one cell per block.  The main lemma `circle_aux` carries
   the mutable cells explicitly, with an invariant tying them to the program
   being constructed.
2. **Delta arithmetic.**  With `delta = (target - base) mod 256`, a run of
   `delta` `+`s (or `256 - delta` `-`s, or nothing when `delta = 0`) moves
   the cell from `base` to `target`, including the wrap-around cases and the
   fixed first-cell run.
3. **The pointer never wraps**, so the interpreter's `>` is a plain `+1`.

The main theorem `circle_correct` states that for every `List Char` text
whose codes are below 256, the output of `runInstructions` on the generated
program is exactly `String.ofList t`.

## Sophie generator correctness

A proof that the Sophie text generator
(`src/esolangs/tools/generators/tape.py::sophie`) is *correct*: for every text
the generated program prints exactly that text.  The generator emits `#c,`
per character, using the `#$<code>,` digit form for `\n` and `$` (whose
literal forms would be read as Sophie syntax).  The proof covers the run
machinery (`run`, `run_charProg`), the digit form (`readDigits`/`renderDigits`,
`Nat.toDigits`), and `exec_correct`, and is sanity-checked with `native_decide`
round-trips.

## BIO generator correctness

A proof that the BIO text generator
(`src/esolangs/tools/generators/tape.py::bio`) is *correct*: for every text
the generated program prints exactly that text.  BIO uses one instruction per
byte and `1`-prefix blocks to repeat a byte `1 + n` times.  The proof is
`repTok`, the repeat lemmas (`run_rep0_append`, `run_rep1_append`,
`run_1ix_rest`), `run_charProg_rest`, and `exec_correct`, sanity-checked with
`native_decide` round-trips.

## 6-5 generator correctness

A proof that the 6-5 text generator
(`src/esolangs/tools/generators/tape.py::six_five`) is *correct*: for every
text the generated program prints exactly that text.  6-5's instructions move
an integer cell by ±1; the generator emits a path of `9`/`6` steps.  The proof
models the cell as an integer (`ℤ`), proves the path moves the cell by the
right amount (`run_path_append`, via `Int.emod_add_ediv_mul`), and
`exec_correct`, sanity-checked with `native_decide` round-trips including
paths that cross the display boundary.

## Qoibl generator correctness

A proof that the Qoibl text generator
(`src/esolangs/tools/generators/register.py::qoibl`) is *correct*: for every
text the generated program prints exactly that text.  Qoibl's `tt <expr> tt`
expressions parse binary digits and print a character.  The generator emits
`tt` followed by the character's binary digits as `y` (1) / `e` (0), followed
by `tt`.  The proof covers the bit parsing (`bitVal`, `binVal`, `bitsOf`,
`binVal_eq_binValNat`), the `tt` framing (`takeBits_bits`, `dropBits_bits`,
`run_charProg_rest`), and `exec_correct`, sanity-checked with `native_decide`
round-trips.

## `_bf_set` multiply loop

A proof of the brainfuck "set and print" primitive
(`src/esolangs/tools/generators/tape.py::_bf_set`), which emits
``+a[>+b<-]>+r.`` to set the next cell to ``a*b + r`` (the ``divmod`` of the
target value) and print it, in ``O(sqrt)`` rather than ``O(value)``.  The
file `BfSetCorrect.lean` models a minimal brainfuck interpreter (a tape of
natural-number cells, a pointer, and an output list) with a fuel-bounded
loop, proves the loop invariant `runLoop_mult` (after `a` iterations of
``[>+b<-]`` the first cell is zeroed and the second holds ``a*b``), and
combines it into `bf_set_correct` / `bf_set_value`, sanity-checked with
`native_decide` round-trips.  This is the multiply-loop invariant that the
huf generator's `# +*a | +*b ! +*r >@` segments share.

## huf generator correctness

A proof that the huf text generator
(`src/esolangs/tools/generators/register.py::huf`) is *correct*: for every
text the generated program prints exactly that text.  Huf keeps two
registers, `num` and `mul`; each character is a multiply segment
``# +*a | +*b ! +*r >`` in which a run of `a` builds `num = a`, `|` starts
the multiplier, a run of `b` raises it to `b + 1`, and `!` multiplies `num`
by `mul - 1` so it becomes `a*b`; the final run of `r` tops it up to the
character code, which `>` prints.  The file `HufCorrect.lean` models the
interpreter (`State` of `num`/`mul`/output, `step`, `run` as a foldl),
proves the per-segment correctness `seg_correct` (the `_bf_set` multiply
invariant again: the segment prints `a*b + r`, and the `>`-guard holds for
code points), and composes segments in `progAux_correct` / `huf_value`,
sanity-checked with `native_decide` round-trips.

## Factor correctness

A proof that the Factor encoder is *total* and that decoding recovers the
program: `decode (encode code) = code`.  The encoder
(`src/esolangs/tools/generators/tape.py::_factor_encode`) walks the runs of a
program, assigning each run `(c, e)` the least prime `p ≥ candidate` with
`p % 11 = res c` and folding `num *= p^e`.  The file `FactorCorrect.lean`
models the commands (`Cmd`, residue `res`), the run-length machinery
(`splitRun`/`runGroup`/`expand`), and the prime search `nextPrimeWithRes`,
whose totality is exactly the Dirichlet theorem
(`Nat.forall_exists_prime_gt_and_modEq`): every residue class mod 11 coprime
to 11 contains infinitely many primes.  It then proves the decoder
(`decodeRuns`) recovers each run: `decodeRuns_encodeRuns` (and hence
`decode_encode`) shows that the sorted distinct prime factors of the encoded
integer are precisely the chosen primes, in order, with the right exponents
(`encodeRuns_factorization_at`, `chosenExp_pos_iff`, `primeFactors_encodeRuns`).

## brainfuck generator correctness

A proof that the brainfuck text generator (`src/esolangs/tools/generators/tape.py::bf`)
is *correct*: for every text the generated program prints exactly that text.
`BfCorrect.lean` reuses the `_bf_set` model from `BfSetCorrect.lean` and adds
the missing pieces: ``-`` runs (`run_minusN`), the ``[-]`` zeroing loop
(`run_zero`), and the ``_bf_set`` multiply segment at an arbitrary cell
(`bf_set_at`, a generalisation of the earlier proof).  The generator walks the
tape right one cell per character, either adjusting the current cell in place
(delta path, `delta_run`) or zeroing it and building the byte in the next cell
(rebuild path, `rebuild_run`); `progAux_correct` composes the per-character
choice into the whole-text correctness theorem.

## Eval generator correctness

A proof that the Eval text generator (`src/esolangs/tools/generators/register.py::eval`)
is *correct*: for text with no literal backtick (which the generator refuses),
the program ``"<text with " -> `>".`` prints exactly that text.
`EvalCorrect.lean` models the two-stack interpreter (values, the stacks, the
string-literal scan `scanString` with backticks expanded back to quotes, and
`run`), proves the literal scan undoes the generator's escaping
(`scan_aux`), and shows the trailing ``.`` prints the pushed string
(`eval_correct`), sanity-checked with `native_decide` round-trips.

## Collatz Multiverse generator correctness

A proof that the Collatz Multiverse text generator
(`src/esolangs/tools/generators/register.py::collatz_multiverse`) is
*correct*: for every text the generated program prints exactly that text.
Collatz Multiverse is an OISC whose every line is
`[var1] = [var2] x + [var3], [DO|NOT] PRINT.`, applying the Collatz rule to
`var1` (odd or zero values become `var1 * var2 + var3`, even values halve).
The generator first bootstraps a constant table `k1..kmaxval` out of
`negativeOne` (`tools/generators/helpers.py::_cm_constants`) using the copy
trick and parity-aware `k1 x + k1`/`k1 x + k2` increments, then emits one
`o{i} = negativeOne x + k<byte>, DO PRINT.` line per character.  The file
`CollatzMultiverseCorrect.lean` models the Collatz transform and the exact
line shapes, proves the table satisfies `k n = n` (`constProg_inv`), and that
each output line prints its byte (`outProgFrom_correct`), composing into
`cm_correct`, sanity-checked with `native_decide` round-trips.

## Sophie boolean-function generator correctness

A proof that the Sophie boolean-function generator
(`tools/generators/booleans/register.py::sophie`) is *correct*: for a truth
table with `n` inputs, the generated decision tree prints the table's output
bit for every input combination.  `SophieBoolCorrect.lean` models the
interpreter's accumulator, input, and output and the decision tree (`;` reads
a bit, `@$48{T}{E}` branches on it, leaves print `#$48`/`#$49`), and proves
`treeOf_correct`: reading the input bits descends the tree to the leaf for
the row they index, printing `tt[row]`.

## 6-5 boolean-function generator correctness

A proof that the 6-5 boolean-function generator
(`tools/generators/booleans/tape.py::six_five`) is *correct*: for a truth
table with at most five inputs, the generated decision tree prints the
table's output bit for every input combination.  `SixFiveBoolCorrect.lean`
models the interpreter's cell, tape, input, and the commands the boolean
program uses (`B` reads a bit and eight `2`s normalize it to 8/9; `78`
skips the following `8n` jump on a zero bit, routing to the left subtree,
while a one bit jumps to the matching `4` marker and the right subtree; a
leaf's `6`/`62` arithmetic adds `48 + tt - base` before `A` prints), and
proves `treeOf_correct`: reading the input bits descends to the leaf for the
row, printing `tt[row]`.

## Building

Requires [elan](https://github.com/leanprover/elan) and mathlib:

```
cd extra/lean/esolangs
lake build
```
