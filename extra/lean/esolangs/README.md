# Lean proofs for the text generators

## MAMMALIAN generator totality

A Lean 4 + mathlib proof that the MAMMALIAN text generator
(`src/esolangs/tools/text/tape.py::slow_acv_mammalian`) is total over the byte
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
   11).  The start array is *not* counted as reached, matching the Python
   walk table.

### Totality (`search_total`)

The per-character search is formalised as `searchOne` (mirroring the
Python generator) and its success is verified by computation over the
full finite state space: 23 pointers × 256 SEED counts × 256 targets.
Reachability uses the same step range (1..46) as the Python
`_mammalian_walk`, so the theorem certifies the actual generator's search:
it never hits the `ValueError` branch.  The Python generator reports
the same zero failures.

## Factor correctness

A proof that the Factor encoder is *total* and that decoding recovers the
program: `decode (encode code) = code`.  The encoder
(`src/esolangs/tools/text/tape.py::_factor_encode`) walks the runs of a
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

## %^2^-1 boolean-generator wall

A proof that `%^2^-1` has **no two-input boolean generator, at any program
length** (`Esolangs/PctBooleanWall.lean`).  The language has one accumulator
and one control-flow command, `t` (rewind to position 0 when the accumulator
is nonzero) — no forward jump, no skip.

`computes_ignores` is the wall: every program meeting the boolean contract
(on all four combinations: halt cleanly, consume both bits, print exactly one
character) computes a function that **ignores one of its two inputs**, so
`no_xor` and `no_and` follow.  Two structural facts carry it:

1. **A read erases the past** (`read_erases`): `n` overwrites the
   accumulator, so the state at the last read is a function of the last bit
   alone.
2. **Reads cannot be skipped** (`count_le_of_halts`): `t` jumps only to
   position `0`, so a cleanly-halting run needs at least as much remaining
   input as there are reads ahead of the cursor.  This refutes the two runs
   diverging at a `t` — the branch that rewinds must pay for the reads it
   re-crosses.

Those give a *canonical* split position (`firstReadFrom`, plus
`read_pos_unique` for the single-`n`-read-twice shape), so the output factors
as `A b₁ ++ B b₂`; a one-character output forces one factor empty.

This is an induction on the execution, **not** a bounded search — the claim
quantifies over unbounded program length, and non-termination of a `t` loop
is not decidable by simulation.  `Esolangs/PctWallCheck.lean` audits the
axioms: only `propext`, `Classical.choice`, and `Quot.sound` — no `sorryAx`
and no `Lean.ofReduceBool`, so nothing rests on `native_decide`.  The model's
`stepCmd` was differentially tested against the shipped Python interpreter
over 44,280 program/input pairs (status, exact output, input consumed) with
zero mismatches.

Note the `n == 1` case is *not* walled: all four one-input functions are
expressible (identity `ne`; NOT is `nss` + `i`×31 + `pe`, computing
`x ↦ -x + 97`).  The wall is exactly at `n ≥ 2`.  This file is not in the
default `lake build` target, so check it explicitly:

```
lake env lean Esolangs/PctBooleanWall.lean
lake env lean Esolangs/PctWallCheck.lean     # axiom audit
```

## Building

Requires [elan](https://github.com/leanprover/elan) and mathlib:

```
cd extra/lean/esolangs
lake build
```
