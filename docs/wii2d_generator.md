# WII2D boolean generator

The implementation in `src/esolangs/tools/boolean/wii2d.py` is authoritative.
These limits are source-size and runtime policies, not language walls.

- `_WII2D_SHORTLIST = 8` compresses the eight lowest-magnitude candidate
  folds. It is the measured quality/time balance; do not assume an
  uncompressed magnitude predicts a compressed result. It is tied to the
  compression rule below and must be re-measured with it: that rewrite at
  shortlist 4 emits 286669 characters over the 532-table corpus, slightly
  worse than the 285903 it replaced, and only 8 makes it a win at 261019.
- `_WII2D_MAX_INDEX_DOMAIN = 256` admits dense nine-input tables when both
  branch decodes land: the deterministic witness (sha256-derived, see the
  grid tests) builds in 6.6s at 78362 characters with all 512 rows
  executed; 45 of 50 sampled domain-256 patterns decode in ~3s, and 6 of 10
  sampled dense n=9 tables build (5-12s, 50-94k characters). Every sampled
  failure returns promptly (0.7-9.4s), which is what allowed the raise from
  128. The generator charges the real domain when it is smaller than the
  worst case.
- `_WII2D_MAX_REAL_DOMAIN = 256` stops rare non-merging chains before they
  emit impractical programs.
- `_WII2D_MAX_CENTRE = 4096` bounds rendered width. It is not arithmetic
  correctness bound.
- `_WII2D_MAX_MAGNITUDE = 2**20` aborts a decode whose live values ratchet.
  A divergence certificate, not a step budget: successes peak at 1922 over
  the 532-table corpus and 13499 over eight domain-256 samples (78x below
  the bound), while a ratchet doubles its bit length every step. Measured
  with the bound lifted, every sampled ratchet also dead-ends on its own
  within seconds -- the centre cap starves it of folds -- so the abort
  fires just ahead of a natural stop (1.7s vs 2.2s on the worst sample);
  it makes that promptness a guarantee rather than a property of the
  sample, deterministically (no wall clock).

The single-candidate rule is exhaustive through domain 16. Ranking by emitted
width or live-count was measured worse; retain magnitude-first selection.
Live-count-first was re-tested against the steered compression, where bulk
merging makes it tempting, and is still worse: 396131 characters against
261019, a 39% regression.

`_wii2d_compress` searches the whole add-then-halve family at once rather
than one halving at a time. A run of `k` halvings with an optional `+`
before each is `v -> (v + S) // 2**k`; a different-bit pair at gap
`g < 2**k` forbids `2**k - g` shifts as a cyclic arc, so the legal shifts
are the arc union's complement, and legality is monotone in `k`. The rule
takes the `(k, S)` merging the most values. This makes compression the
merging half and the fold merely reshaping, which is what carries width:
dense domain 256 decodes 18 of 20 sampled patterns against 3 of 10 before.

Domain 256 (dense n=9) is reachable but **not total** — about 1 pattern in
10 ratchets into the doubling trap or dead-ends. Under the shipped
compression those failures *return* (aborted by `_WII2D_MAX_MAGNITUDE` or
starved of folds by the centre cap, seconds either way), so the guard sits
at 256 and a bad table costs a prompt `ValueError`, not a hang.

Domain 512 (dense n=10) is a wall of the fold algebra, not a guard choice.
The construction space was audited, not just the greedy:

- **Greedy, fully enumerated.** With every legal candidate compressed (no
  shortlist), best-per-step: live count crawls 512 -> 373 over 19 steps
  while the bit length climbs 14 -> 670597, steps reaching 210s. Squaring
  doubles width faster than merges repay it. Survivors-first,
  magnitude-first and bucketed rankings, a magnitude-triggered restart, and
  wider pre-scales/centre caps were all tried; none change the ratchet.
- **The machine model is closed.** The interpreter has no
  accumulator-conditional control flow and no memory beyond the one
  accumulator (`@`, `|` are static; `?` is random), and every input
  combination's path passes through every junction cell, leaving at most
  two op-string segments between junctions. So any construction is ops
  interleaved with the n branch pairs, and its merging power is exactly
  the fold algebra's.
- **No op removes high bits** (`/` discards low bits, digits discard
  everything), so a table constant shifted by the accumulated index can
  never be read out: the answer digit always sits under unbounded
  higher-order garbage that no threshold survives. This kills the
  shift-loaded-table and cross-term-multiply family analytically.
- **Moving work into the chain is strictly harder.** A mid-chain collapse
  must merge under refined labels: entering the last junction the states
  carry 4-class cofactors, one junction earlier 16-class. The machinery is
  label-agnostic, so this was probed with full enumeration: real 4-ary
  cofactor labels on 512 values ratchet (474 live at 3113 bits by step
  11); 16-ary on 256 values has no legal first move at all. The positive
  control — structured labels `v >> 7`, `v >> 4` — collapses to the class
  count in the initial compression under the same code path.

What would change the verdict: an accumulator-conditional op or a second
register in the language (there is none), or paying for a non-greedy fold
*schedule* search over states whose steps already cost minutes at the
ratcheted magnitudes.

Structured n=10 is unaffected and builds through the popcount and
merging-chain paths — parity, majority, AND, OR, a 3-input xor-subset and
a 3-to-8 mux all build and execute all 1024 rows correctly.
