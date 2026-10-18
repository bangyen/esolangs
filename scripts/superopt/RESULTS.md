# Superoptimizer results log

Runs of the tool in this directory, newest first. A claim appears here
only when a program was executed or a search space exhausted; winners
are certified against the full spec before they are recorded.

## 2026-10-18 — the digits gadget is minimal as a whole program, not only as a suffix

Target: any program over the full alphabet (`/ 0 1 2 K0 K1 K2`) that,
from zeroed cells, reads the three input bits and leaves them
injectively in trit 0 of cells 1 and 2. The repo proved the shipped
gadget's *suffix* uniquely shortest after its hand-designed 10-op
wipe prefix; whether some interleaving of reads and applies beats
16 ops in total was open, and the staged prefix looked like the kind
of human design choice a search could improve on. It cannot, in this
model: breadth-first search over full row-state signatures exhausted
depth 15 with no hit, and at depth 16 the first hit is the shipped
gadget itself, certified.

```
PYTHONPATH=src:scripts python -m superopt novel --max-depth 15 --budget-seconds 1500 --node-cap 2000000
  signatures by depth: 1, 7, 19, 52, 163, 377, 843, 1700, 3270, 5962,
  10831, 21002, 45257, 105173, 246174, 549060
  no injective program up to depth 15 (shipped: 16 ops)   [19.0 s wall]
PYTHONPATH=src:scripts python -m superopt novel --max-depth 16 --budget-seconds 1500 --node-cap 3000000
  hit at 16 ops (shipped: 16): / 0 / 1 K2 0 K2 1 / 2 0 1 0 K1 0 2  certified: True   [20.4 s wall]
```

Priced before running from the depth-≤12 calibration (45,257
signatures, 1.5 s): under ~2 CPU-minutes to depth 15; actual total for
both runs ≈ 26 s CPU, inside the stated ≈30 CPU-minute cap.

Scope of the claim: the trit-0 model with zeroed starts. The model is
faithful to the shipped build at that resolution — the wipe prefix
leaves identical post-prefix states from all five groups' real
initial trit patterns as from zeroed cells (checked by running the
prefix from each), and the machine is pinned to the interpreter by
tests. It says nothing about the full 10-trit machine.

## 2026-10-18 — positive control: the shipped suffix, rediscovered

```
PYTHONPATH=src:scripts python -m superopt control
  candidates evaluated: 55987; rows evaluated: 218538
  first injective length: 6; hits: 1
    0 1 0 K1 0 2  certified: True
  control passed
```

No injective suffix of length 0–5 after the wipe prefix; at length 6
exactly one, the shipped suffix. The early-exit filter is measurable
in the counters: 55,987 candidates took 218,538 row evaluations
(≈3.9 of 8 rows per candidate), against 447,896 for full-table
evaluation of every candidate.

## Idioms

- The unique shortest suffix is apply-heavy: `0 1 0 K1 0 2` — five
  cell applies and a single constant. Constants set up one trit
  pattern; the applies do the separating.
- Wipe-then-compute is size-optimal here as a whole: the from-scratch
  optimum (16) equals prefix + suffix (10 + 6), so staging the reads
  in a wipe costs nothing against free interleaving.

## Negative results

- No injective suffix of length ≤5 after the digits wipe prefix
  (exhaustive, this run and the repo's own test).
- No injective full program of length ≤15 over the full alphabet from
  zeroed cells (breadth-first, exhaustive to depth 15).
- The wipe prefix alone leaves only 4 of 8 inputs distinct in
  (cell 1, cell 2); any suffix must manufacture the other four
  distinctions, which is why none is shorter than 6.
