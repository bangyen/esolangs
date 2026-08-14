# Lean proofs for the text generators

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

## EXCON generator correctness

A Lean 4 + mathlib proof (`Esolangs/ExconCorrect.lean`) that the EXCON text
generator (`src/esolangs/tools/generators/tape.py::excon`) is *correct*, not
just total: for every byte-range text, running the generated program through
the interpreter's own pure state transitions (`Excon.to_s`, `Excon.flips`,
`Excon.gets`, `Excon.empty_list`) prints exactly that text.

The proof is a bit-flip induction over the 8-cell pool:

1. **Bit-flip induction** (`run_charProgAux`): the generator's pointer walk
   visits each set bit exactly once (moving only left, so the pointer never
   wraps), so after the flips `gets pool k = bit v k` for every cell `k`.
   The `GoodPool` invariant tracks which high bits are already correct and
   which low bits are still zero.
2. **Binary value** (`byte_value`): `to_s` reads the pool back as
   `128*pool[0] + 64*pool[1] + ... + pool[7]`, which equals the character's
   code for every byte (the byte range is verified by computation).

The main theorem `exec_correct` states that for every `List Char` text whose
codes are below 256, `exec (textProg t) = String.ofList t`.

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

## BF-PDA bracket matching

A Lean 4 + mathlib proof (`Esolangs/BfpdaCorrect.lean`) of the BF-PDA
interpreter's `find` bracket matching (`Esolangs/bfpda.lean`): the walk that
counts bracket depth (`[` adds 1, `]` subtracts 1, stopping at 0) is correct
for balanced programs.  The depth walk is formalised purely over `List Char`
(what `find`'s recursion over the string iterator does, character by
character), with a `Balanced` grammar that admits non-bracket characters
interspersed like real BF-PDA programs.

The main theorem `match_forward` states that for a balanced `[ l ]` block,
walking from the opening bracket the depth returns to zero *exactly* at the
matching closing bracket — it is strictly positive at every position in
between (so the walk never stops early) and reaches zero at the `]` itself
(so the walk stops there, within the program).  The interpreter's bracket
handling inherits a quirk from the Lean 3 original — `find` always returns
the position after the bracket itself — so the certified property is the
matching logic `find` computes, not the jump it returns.

## EXCON interpreter equivalence

A Lean 4 + mathlib proof (`Esolangs/ExconSemanticsCorrect.lean`) that the
ported EXCON interpreter (`Esolangs/Excon.lean`) computes exactly the
reference Python interpreter's output (`src/esolangs/interpreters/tape_based/excon.py`)
for every program that does not walk the pointer off the pool.  The reference
model (`pRun`) reuses the ported transitions (`flips`, `to_s` via `pyToS`),
so the theorem certifies the port itself; `pyToS` expands `to_s` as the
binary read `128*pool[0] + 64*pool[1] + ... + pool[7]` that the reference's
`int("".join(pool), 2)` computes.

The two interpreters agree on `:` (reset), `^` (flip), `!` (print), and on
`<` within the valid pointer range.  The one divergence is the reference's
error handling: when `<` runs at cell 0 the Python interpreter raises
`HaltError`, while the port's `(n - 1) % 8` keeps the pointer at 0 and
continues.  The theorem `output_eq` is therefore stated under the guard that
the reference run succeeds — when it does not halt, both interpreters print
exactly the same string (`output_eq_exec` states it from a reset pool, in
terms of `exec`).

## AlbaBet generator correctness

A Lean 4 + mathlib proof (`Esolangs/AlbabetCorrect.lean`) that the AlbaBet
text generator (`src/esolangs/tools/generators/register.py::albabet`) is
*correct*.  AlbaBet is a two-register language (`x` and `y` start at 0): `a`
moves `x` up by one, `c` zeroes `x`, and `i` prints `Char.ofNat x`.  The
generator emits, for each byte `v`, the program `c` followed by `v` copies of
`a` followed by `i`.

The proof runs the generated program through the ported interpreter's own
pure state transitions (`step`/`runList` over a `(x, y, out)` state), with
three parts:

1. **The `a` run** (`runList_replicate_a`): `v` copies of `a` add `v` to the
   accumulator, wherever it started.
2. **One character** (`run_charProgC`): `c` zeroes the accumulator, so the
   `a` run sets it to exactly `v` and `i` appends `Char.ofNat v` to the
   output; `y` is never touched.
3. **The whole text** (`runList_textProg`): every character's program
   preserves `y` and only appends, so the characters' outputs concatenate.

The main theorem `exec_correct` states that for every `List Char` text whose
codes are below 256, `exec (textProg t) = String.ofList t`.

## AlbaBet interpreter equivalence

A Lean 4 + mathlib proof (`Esolangs/AlbabetSemanticsCorrect.lean`) that the
ported AlbaBet interpreter (`Esolangs/Albabet.lean`) computes exactly the
reference Python interpreter's output (`src/esolangs/interpreters/other/albabet.py`).
The reference is *total* — every character is a defined operation or a no-op —
so unlike EXCON there is no underflow halt to guard against.  The reference
model `pstep` reuses the ported transitions (`AlbabetCorrect.step`), so the
theorem certifies the port itself.

The two interpreters agree on every instruction except the state `i` leaves
behind when it prints an invalid scalar value (the surrogate range
0xD800-0xDFFF, or values at or above 0x110000): the reference zeroes `x`,
while the port keeps it (Lean's `Char.ofNat` yields NUL without touching
`x`).  Both print NUL at that `i`, so the current output agrees, but the
different `x` changes what a *later* `i` prints.  The theorem `output_eq` is
therefore stated under the guard `Clean` (the program never runs `i` with an
invalid scalar in `x`): under that guard both interpreters reach the same
state and print the same string.  Every generated program is clean
(`Clean_textProg`), so `generator_output_eq` ties this back to the generator
proof.

## Number Seventy-Four interpreter equivalence

A Lean 4 + mathlib proof (`Esolangs/SeventyFourSemanticsCorrect.lean`) that
the ported 74 interpreter (`Esolangs/seventy_four.lean`) computes exactly the
reference Python interpreter's output (`src/esolangs/interpreters/other/seventy_four.py`)
for the programs where the two control flows coincide.  The push semantics
(`push`) are identical: `0`/`1` push their bit, `H` writes an `H` only if the
output starts with `0`.  The control flow differs: the reference scans in
repeated passes and halts only when the output starts with `H` at a *pass
boundary* (restarting forever otherwise), while the port walks the program
once, checks before every command, and stops after `limit` commands.

So the equivalence is stated under the guard `NoEarlyH` (no proper prefix of
the meaningful commands makes the output start with `H`, so the port never
halts early) plus `prog.length ≤ limit` (the port reaches the last meaningful
command) plus `front (outOf (meany prog)) = 'H'` (the run halts at all).
Under it `interpreter_eq` says both print the same string — the port at the
next command's check, the reference at the pass boundary.  The divergence is
real and proven: `0H0H` makes the output start with `H` mid-pass, so the port
prints `H0` while the reference finishes the pass and prints `H0H0`
(`NoEarlyH` fails there).

## BF-PDA interpreter equivalence

A Lean 4 + mathlib proof (`Esolangs/BfpdaSemanticsCorrect.lean`) that the
ported BF-PDA interpreter (`Esolangs/bfpda.lean`) and the reference
(`src/esolangs/interpreters/tape_based/bfpda.py`) compute the same output for
balanced programs whose run never performs an empty-stack operation.  Both
are a bit-stack brainfuck bounded at `limit` commands; both halt on an
empty-stack operation.

The bracket control is the subtle part, and it ties this file to the
bracket-matching proof.  The port's `find` and the reference's
`_forward`/`_backward` both return the position after the bracket, so a
matched pair runs its body exactly once rather than looping.  The walk
(`hitsAux`, counting `[` as +1 and `]` as -1) is formalised and proved to
reach depth 0 for balanced blocks — `hitsAux_block` for a forward `[` at its
matching `]`, `hitsAux_back_block` for a backward `]` at its matching `[` —
reusing `BfpdaCorrect`'s `Balanced`/`depth` results.  Under `Balanced` both
interpreters are therefore the same `runAux`, and `interpreter_eq` states
they print the same output.

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

## Collatz Multiverse generator correctness

A proof that the Collatz Multiverse text generator
(`src/esolangs/tools/generators/register.py::collatz_multiverse`) is
*correct*: for every text the generated program prints exactly that text.
`CollatzMultiverseCorrect.lean` models the register interpreter (the
registers `k`/`o`, the Collatz transform `collatz t a b := if Odd t then
t*a+b else t/2`, `init`) and proves the generator's two parts: the constant
table is bootstrapped from `negativeOne` so every byte value up to `maxval`
is reachable (`constProg`, the `constInv` invariant, `constProg_inv`), and
the per-character output lines copy the byte from the table and print it
(`outProg`, `outProgFrom_correct`); `cm_correct` composes them,
sanity-checked with `native_decide` round-trips.

## Building

Requires [elan](https://github.com/leanprover/elan) and mathlib:

```
cd extra/lean/esolangs
lake build
```

## Ported Lean 3 interpreters

The four Lean 3 ``#eval`` interpreters that used to live in ``extra/lean``
have been ported to Lean 4 and now compile as modules in this project
(``Esolangs/Excon.lean``, ``Albabet.lean``, ``bfpda.lean``,
``seventy_four.lean``).  Each is a faithful port of the original: the
recursive iterator walk and the stack/tape semantics.  Each is also exposed
as a ``lean_exe`` (via a thin ``*Main.lean`` wrapper), so the interpreters
read their program from a text file at runtime like every other interpreter
in the repo:

```
lake build
.lake/build/bin/albabet program.txt
.lake/build/bin/excon program.txt
.lake/build/bin/bfpda program.txt
.lake/build/bin/seventy_four program.txt
```

No file is read at build time — the original Lean 3 ``#eval`` drivers read
``test.txt`` during compilation, which broke ``lake build``, so the drivers
became runtime executables instead.  EXCON's output was cross-checked against
the in-repo Python interpreter; the Lean 3 ``to_s`` dropped the most
significant ``pool[0]`` bit (so ``!`` printed ``value mod 128`` for bytes
>= 128), and the Lean 4 port restores it with ``128 * gets l 0`` in the base
case, which ``ExconCorrect.lean`` relies on.
