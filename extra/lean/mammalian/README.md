# MAMMALIAN generator totality (Lean 4)

A Lean 4 + mathlib proof that the MAMMALIAN text generator
(`src/esolangs/tools/generators/tape.py::mammalian`) is total: for every
text it emits a program that prints it, and the per-character search never
fails.

## The two structural facts

1. **Number theory** (`even_q_solvable`): every even array `q < 23` has
   `gcd (q+1) 256 = 1`, so the value equation `(q+1)*final ≡ target`
   (mod 256) is always solvable.
2. **Reachability** (`walk_reaches_even`): the SPRINT walk from every
   pointer reaches an even array in steps 1..46 (at SEED count 1 the walk is
   the affine bijection `q ↦ 2q+1 mod 23`, whose orbits have period dividing
   11).  The start array is *not* counted as reached, matching the reference
   walk table.

## Totality (`search_total`)

The per-character search is formalised as `searchOne` (mirroring the
reference generator) and its success is verified by computation over the
full finite state space: 23 pointers × 256 SEED counts × 256 targets.
Reachability uses the same step range (1..46) as the reference
`_mammalian_walk`, so the theorem certifies the actual generator's search:
it never hits the `ValueError` branch.  The reference implementation reports
the same zero failures.

## Building

Requires [elan](https://github.com/leanprover/elan) and mathlib:

```
cd extra/lean/mammalian
lake build
```

## Ported Lean 3 interpreters

The four Lean 3 ``#eval`` interpreters that used to live in ``extra/lean``
have been ported to Lean 4 and now compile as modules in this project
(``LeanMammalian/Excon.lean``, ``Albabet.lean``, ``bfpda.lean``,
``seventy_four.lean``).  Each is a faithful port of the original: the
recursive iterator walk, the stack/tape semantics, and the ``#eval`` driver
reading ``test.txt``.  EXCON's output was cross-checked against the in-repo
Python interpreter.
