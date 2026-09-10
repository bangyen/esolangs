# WII2D boolean generator

The implementation in `src/esolangs/tools/boolean/wii2d.py` is authoritative.
These limits are source-size and runtime policies, not language walls.

- `_WII2D_SHORTLIST = 8` compresses the eight lowest-magnitude candidate
  folds. It is the measured quality/time balance; do not assume an
  uncompressed magnitude predicts a compressed result. It is tied to the
  compression rule below and must be re-measured with it: that rewrite at
  shortlist 4 emits 286669 characters over the 532-table corpus, slightly
  worse than the 285903 it replaced, and only 8 makes it a win at 261019.
- `_WII2D_MAX_INDEX_DOMAIN = 128` admits dense eight-input tables (18466
  characters, 0.8s, all 256 rows executed) while preserving cheap structured
  decodes. The generator charges the real domain when it is smaller than the
  worst case. It was 64, which refused that table; nine inputs would need
  256 and is untested.
- `_WII2D_MAX_REAL_DOMAIN = 256` stops rare non-merging chains before they
  emit impractical programs.
- `_WII2D_MAX_CENTRE = 4096` bounds rendered width. It is not arithmetic
  correctness bound.

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

Domain 256 (dense n=9) is therefore reachable but **not total** — the two
stragglers ratchet into the doubling trap under both rankings and never
return — so `_WII2D_MAX_INDEX_DOMAIN` stays at 128, where a refusal is
prompt. Domain 512 (dense n=10) failed every seed: the live count crawls
512 -> 373 while the bit length climbs past 670000, with every candidate
compressed. Structured n=10 is unaffected and builds through the popcount
and merging-chain paths — parity, majority, AND, OR, a 3-input xor-subset
and a 3-to-8 mux all build and execute all 1024 rows correctly.
