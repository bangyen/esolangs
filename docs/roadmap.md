# Roadmap

This page lists work that is still open. Finished work lives in the git
history; standing rules and proved limits are in [limitations](limitations.md).

## Generator linearity

For truth-table length `T`, target O(T) generation time and emitted size.
Generation includes input ordering and writing the program. Close a gap with
an executed, loop-less construction or a language-wide lower bound; measured
scaling alone does not prove linearity. Preserve totality, execution, and
workspace contracts.

The [scaling status](proofs/index.md#scaling-status) records current verdicts.
Edit the `[proof_status]` section of the language's own `language.toml` and run
`just docs` to update it. Proved limits remain
evidence, not optimization tasks.

- Polynomial has a documented language lower bound.
- Unary has a documented language lower bound.
- Befunge has a finite-source totality exception.

- **Malbolge:** generation at seventeen inputs is open (2026-10-21): a
  table cell cannot carry eight address-independent meanings (window
  conflict graph: independence number 8, twelve classes), lockstep
  adjacent-cell reads reach 110 of 512 triples a phase, and the
  seven-meaning build's 1,994 gotos have 2.77 cells each in the
  complement against a 3.6-cell routing floor
  ([limitations](limitations.md)). Reopen only with a layout that needs a
  quarter fewer gotos at that floor, or a decoder whose per-cell meaning
  is not a function of the window cell.
- **Vandevelo:** settle structural output scaling; generation time follows,
  since it includes writing the program and the shipped source is
  `Omega(T log n)` ([the audit](proofs/index.md#vandevelo-identifier-and-fallback-audit)).
  The peel's per-entry work is measured flat through n=15 (2026-10-20).
  The odd-prefix family does not bound the language: `x < m` is a union of
  one cube per 1-bit of `m`, an `O(n**2 log n)` program (324 characters at
  n=8 by hand, executed). A language-wide bound has to handle conditional
  reads, whose offset histories give one guard line exponentially many
  effective cosets, so it is open in both directions.
  Without conditional reads it is an affine-subspace question (2026-10-21):
  a dimension-`d` guard needs `n - d` distinct names, so a dense table whose
  1-set holds no flat above `O(n)` points forces `Omega(T log n)`. Gowers
  norms force flats of only about `n` points; random sets hold `n log n`.
  Each guard is one term of a DNF of parities, whose worst-case size
  Cohen and Shinkar (ITCS 2016, ECCC TR14-099) bound between
  `Omega(2**n/(n log n))` and `O(2**n/n)`: the same `log n` gap, open
  since 2014. Closing it here needs an affine disperser for dimension
  `log2 n + O(1)` with a dense 1-set, or a cover beating their Theorem 1.2.
  Conversely, a cover counting each flat once per `ceil(log2 n)` of its
  dimension, weight `W`, gives a program of `O(n log n (W + 1))` characters
  without conditional reads (executed through n=9), so an `omega(T)` bound
  needs a cover bound beyond counting. The converse fails: conditional reads
  beat every cover exponentially. `k` selector reads, a line `s? :: Inp?`
  per selector, then `Inp? :: L?` read bit `k + 1 + wt(s)` in `O(n log n)`
  characters, yet no flat in that 1-set exceeds dimension
  `2k - k/log2(k+1)` (polynomial-method bound on distinct weights), so a
  cover needs `2**(k/log2(k+1))` flats (executed to n=9, sampled to n=61).
  A linear construction is therefore not blocked by the cover gap; the
  only bound known for all programs is counting. Random tables are `O(T)`: with
  probability `1 - 2/log n` the 1-set is at most `220*2**n/(n log n)` flats of
  dimension at most `log n + log log n` (phased transversal greedy with a
  random translation per block; two referee passes). That proof needs
  `log n >= 2**20` and gives no algorithm, so the worst case stays open.
  Shipped text is flat at about 8 characters an entry through n=15, since
  names stay one character to n=62. Guards that are graphs of affine maps
  from fixed inputs reach 0.73x shipped at n=13, but only with
  candidate scans growing faster than `T`; a fixed cap of 64 gives 0.98x at n=14.

Keep the registry-wide scaling regressions in `tests/proofs/deep/linearity.py`.
An unresolved bound stays open; it does not authorize removing its regression
check or weakening a contract.

## Engineering

Dead-code leads, unmeasured against the
[10% size bar](CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping).
A removal must leave the generated corpus byte-identical (tiled, constant and
ignored-input tables included).

- **Plain-rewrite audits are one-off:** Streetcode and LaserFuck were each
  audited once -- write the plain canonical construction, price every
  bespoke trick against it, and remove the ones whose saving is a fixed
  amount rather than a genuine percentage (see
  [CONTRIBUTING](CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping)):
  Streetcode's lift and tail overlap, LaserFuck's sized leaf retirement and
  Dig's default banded tree came out this way, and four of SStack's six
  sharing routes (2026-10-21). Flowchart and Circlefuck kept every trick and
  Ascenic has none (2026-10-21). The audit is repeatable per generator.
- **The S*bleq variants are interpreter-only, and stay so unless they
  are ever registered:** the interpreter runs the store targets `a`
  (base), `ab` (S*bl*q) and `b` (Subl*q), each also in an indirect
  form, but the generator emits base S*bleq only and no public path
  selects a variant (no registry entry, no dialect setting -- they are
  distinct languages, not readings of one spec). Not scheduled work:
  if the variants are ever registered, generalizing the hoisted tree
  and the packed decoder across the other two store targets belongs to
  that project, execution-gated per variant and re-audited afterwards,
  against the plain-rewrite sweep's S*bleq prices as the baseline. The
  indirect forms would stay out of scope even then: their operands are
  dereferenced, so a generated program can embed no literal address and
  every operand would need a materialized pointer cell -- a different
  construction, not a parameter of this one.
- **FRACTRAN's one-literal guards (retirement candidate #19) wait on the
  index:** writing each guard as one literal (`11*29` as `319`) leaves
  programs the interpreter's index refuses -- the literals are products of
  two of the program's primes and outgrow any linear cap on its bases
  (36,041 against a 4,337-character program at n=10), so runs scan the
  fraction list. It ships only with an index that factors guards over the
  program's own primes; its saving is 8.4% at n=10.
