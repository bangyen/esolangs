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

## brainfuck minterm boolean-function generator correctness

A proof that the brainfuck minterm boolean-function generator
(`tools/generators/booleans/tape.py::_bf_minterm`) is *correct*: for a truth
table the generated program reads the `n` input bits and prints `48 + sum`
where `sum` is the sum of the table's one-rows' minterms (each minterm is the
product of the input bits or their complements selecting that row, so exactly
the one matching the input combination contributes `1`).  `BfMintermCorrect.lean`
extends the `_bf_set` brainfuck model with a `,` input command and an input
list, and proves the scratch machinery the generator relies on — `run_copy`
(the `[>a+ >b+ >src-]` spread and the move-back loops), `run_complement`,
`run_add`, and `run_and` (the nested AND loop) — then shows the whole program
reads the bits (`run_readProg`), folds each one-row's factors into the product
(`run_factorStep`, `run_mintermPrefix`, `run_mintermRow`), accumulates them
into the sum (`run_rows`), and prints `48 + sum` (`bf_minterm_correct`),
sanity-checked with `native_decide` round-trips.  This proof is kept
self-contained rather than part of the main `lake build` (which now holds
only the totality proofs).

## Building

Requires [elan](https://github.com/leanprover/elan) and mathlib:

```
cd extra/lean/esolangs
lake build
```
