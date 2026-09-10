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
  the bound), while a ratchet doubles its bit length every step.
  **Load-bearing, not belt-and-suspenders**: with the bound lifted a
  ratchet does not stop on its own. Three domain-256 tables that abort in
  0.45-1.59s ran 136s, 183s and 214s unbounded, reaching 299526, 1173459
  and 644663 bits and still climbing. Without it the 256 guard would ship
  hangs. Deterministic (no wall clock), and checked on the decode state
  rather than the candidates, so it cannot change which candidate a
  succeeding table takes.

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
10 ratchets into the doubling trap or dead-ends. Those failures return only
because `_WII2D_MAX_MAGNITUDE` aborts them; a ratchet left unbounded does
not stop. So the guard sits at 256 and a bad table costs a prompt
`ValueError` rather than a hang, and that promptness rests on the abort.
Measured over 64 adversarial n=9 tables: 48 built, 16 refused, 0 hung,
worst build 21.5s and worst refusal 5.3s.

Domain 512 (dense n=10) is a wall of the **exactly-once embed convention**,
not of the machine and not a guard choice. Drop the convention and it goes:
a per-node re-embed (a grid decision tree, one row per level, leaves as
literal digits so the accumulator decodes nothing) builds dense n=10 in
14432 characters and dense n=13 in 146540, every row executed. It embeds
input `i` `2**i` times — 512 copies of `{X9}` at n=10 — which
`tests/tools/test_boolean_parameterized.py` forbids and for which Dotlang
and 2dFish were removed rather than exempted.

Under the convention the construction *is* closed, and the audit below is
what closes it. The load-bearing step is that `^v<>` fills set the heading
absolutely, so every prefix leaves a junction at an identical position and
heading with only the accumulator differing — position cannot serve as a
second register, and a revisited junction cell always loops rather than
terminating.

- **Greedy, fully enumerated.** With every legal candidate compressed (no
  shortlist), best-per-step: live count crawls 512 -> 373 over 19 steps
  while the bit length climbs 14 -> 670597, steps reaching 210s. Squaring
  doubles width faster than merges repay it. Survivors-first,
  magnitude-first and bucketed rankings, a magnitude-triggered restart, and
  wider pre-scales/centre caps were all tried; none change the ratchet.
- **The single-embed construction is closed.** The interpreter has no
  accumulator-conditional control flow (`@`, `|` are static; `?` is
  random), and `^v<>` fills steer *absolutely*, so all prefixes leave a
  junction at the same position and heading and only the accumulator
  differs. Position is therefore not a usable second register, and a
  junction cell can be revisited (a single `{X0}` can execute 6+ times)
  but only in a loop. So any single-embed construction is ops interleaved
  with the n branch pairs, and its merging power is exactly the fold
  algebra's. This is *not* a claim about the machine — see the tree above.
- **No op removes high bits** (`/` discards low bits, digits discard
  everything), so a table constant shifted by the accumulated index can
  never be read out: the answer digit always sits under unbounded
  higher-order garbage that no threshold survives. This kills the
  shift-loaded-table and cross-term-multiply family analytically.
- **Moving work into the chain is strictly harder.** A mid-chain collapse
  must merge under refined labels: entering the last junction the states
  carry 4-class cofactors. Probed with full enumeration: real 4-ary
  cofactor labels on 512 values ratchet (474 live at 3113 bits by step 11,
  reproduced on four seeds).

  Two corrections to an earlier version of this entry. Its positive
  control (`v >> 7`, `v >> 4`) was **vacuous** — those labels collapse in
  the *initial compression* with zero legal folds, so they never exercised
  `_wii2d_folds`, the machinery whose stall was the evidence. Controls
  that do use folds (uneven-block 3- and 4-class labels) collapse in 1-11
  real folds at both 256 and 512, so the 4-ary ratchet stands. And the
  "16-ary has no legal first move" result is **counting, not cofactors**:
  a fold at centre `c` merges every pair summing to `2c` and is legal only
  if all merged pairs share a label, which at `k` classes has probability
  about `k**-(D/2)`. 16 classes have no legal fold at D=64 either. It says
  nothing about mid-chain collapse and should not be cited for it.

What would change the verdict: an accumulator-conditional op or a second
register in the language (there is none), or paying for a non-greedy fold
*schedule* search over states whose steps already cost minutes at the
ratcheted magnitudes.

Structured n=10 is unaffected and builds through the popcount and
merging-chain paths — parity, majority, AND, OR, a 3-input xor-subset and
a threshold all build and execute all 1024 rows correctly.

The 3-to-8 mux is the honest edge case, and "a mux builds" overstates it:
of the 1680 n=10 spellings (choice of 3 select bits x which data line
repeats x MSB/LSB indexing) only **3 build, 0.18%**, all with the selects
at positions 6-8/6-9 — that is, read *last*, so the chain merges the data
inputs away before the selects arrive. The other 1677 leave a real domain
of 512 against the 256 guard. The 3 that build do execute all 1024 rows
correctly. Whether a table builds depends on input *order*, not only on
the function.
