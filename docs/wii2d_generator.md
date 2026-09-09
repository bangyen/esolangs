# WII2D boolean generator

The implementation in `src/esolangs/tools/boolean/wii2d.py` is authoritative.
These limits are source-size and runtime policies, not language walls.

- `_WII2D_SHORTLIST = 4` compresses the four lowest-magnitude candidate
  folds. It is the measured quality/time balance; do not assume an
  uncompressed magnitude predicts a compressed result.
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
