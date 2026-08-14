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
