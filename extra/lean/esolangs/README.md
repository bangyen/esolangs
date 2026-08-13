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
