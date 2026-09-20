# Factor: the language lower bound

A Factor program is one decimal integer.  The interpreter factors it and reads
each prime's exponent as a run of the command its residue mod 11 selects
(`src/esolangs/interpreters/tape_based/factor.py:120-123`), so a program's
behaviour depends only on the sequence of `(residue, exponent)` pairs ordered
by prime -- not on the primes' magnitudes.  The generator emits
`Theta(T log T)` digits: the folded brainfuck tree has `Theta(T)` maximal runs
and the k-th prime of a residue class carries `Theta(log k)` digits.  The floor
proved here is `Omega(T log T / log log T)` for some table under every
encoding; the two agree up to a `log log T` factor.

## The count

Fix a digit count `D`, so `log N = Theta(D)` nats.

- Let `m` be the number of distinct primes in `N`.  They are distinct, so
  `log N >= log p_1 + ... + log p_m >= log(m!)`, giving `m log m = O(D)` and
  `m = O(D / log D)`.
- The exponents satisfy `sum e_i log p_i <= D log 10`; with `p_i >= 2` this
  bounds `sum e_i <= D log2 10 = O(D)`.
- The decoded program is the sequence of `(p_i mod 11, e_i)`.  The number of
  exponent vectors with `sum e_i <= E` into `m` parts is at most `C(E, m)`,
  and with `m = O(D/log D)`, `E = O(D)` this is
  `exp(O(D log log D / log D))`.
- The residues contribute at most `8**m = exp(O(D / log D))` command
  sequences, subsumed.

So at most `exp(O(D log log D / log D)) = 2**o(D)` distinct programs have at
most `D` digits.  Different primes with the same residues yield the same
program, which is why the many-to-one collapse happens at all.

## The floor

A table of length `T` is a Boolean function, and two tables need two different
programs, so covering all `2**T` tables needs `2**T` distinct programs.  Then
`2**o(D) >= 2**T`, i.e. `D log log D / log D = Omega(T)`, which inverts to

    D = Omega(T log T / log log T).

Every encoding is counted: the bound is only the pigeonhole on how many
distinct programs fit in `D` digits, and the residue class is the interpreter's
(`1..8 mod 11`; other residues decode to nothing).

## Provenance

The argument stood in `docs/limitations.md` until `b473ded0` trimmed that
document to a single sentence.  It is restored here because both the roadmap's
audit table and the `proofs.md` ledger cite it as a language lower bound, and a
cited bound should be readable in the tree.  The count's premise was re-checked
against the current `decode` (only `p % 11` and the exponent survive) and the
current `_factorint` (which collapses each prime to one entry), so repeated
primes contribute one run, as the count assumes.
