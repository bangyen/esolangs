# WII2D boolean generator

The implementation in `src/esolangs/tools/boolean/wii2d.py` is authoritative.

- `_WII2D_SHORTLIST = 8` compresses the eight lowest-magnitude candidate folds.
- `_WII2D_MAX_INDEX_DOMAIN = 256` admits dense nine-input tables when both branch decodes land: the deterministic witness (sha256-derived, see the grid tests) builds in 1.1s at 78362 characters with all 512 rows executed.
- `_WII2D_MAX_REAL_DOMAIN = 256` stops rare non-merging chains before they emit impractical programs.
- `_WII2D_MAX_CENTRE = 4096` bounds rendered width.
- `_WII2D_MAX_MAGNITUDE = 2**20` aborts a decode whose live values ratchet.

The single-candidate rule is exhaustive through domain 16.

`_wii2d_compress` searches the whole add-then-halve family at once rather than one halving at a time.

Domain 256 (dense n=9) is reachable but **not total** — about 1 pattern in 10 ratchets into the doubling trap or dead-ends.

`_wii2d_folds` reads the pair sums once instead of rescanning the domain per centre.

Domain 512 (dense n=10) is a wall of the **exactly-once embed convention**, not of the machine and not a guard choice.

Under the convention the construction *is* closed, and the audit below is what closes it.

- **Greedy, fully enumerated.** With every legal candidate compressed (no shortlist), best-per-step: live count crawls 512 -> 373 over 19 steps while the bit length climbs 14 -> 670597, steps reaching 210s.
- **The single-embed construction is closed.** The interpreter has no accumulator-conditional control flow (`@`, `|` are static; `?` is random), and `^v<>` fills steer *absolutely*, so all prefixes leave a junction at the same position and heading and only the accumulator differs.
- **No op removes high bits** (`/` discards low bits, digits discard everything), so a table constant shifted by the accumulated index can never be read out: the answer digit always sits under unbounded higher-order garbage that no threshold survives.
- **Moving work into the chain is strictly harder.** A mid-chain collapse must merge under refined labels: entering the last junction the states carry 4-class cofactors.

  Two corrections to an earlier version of this entry.

What would change the verdict: an accumulator-conditional op or a second register in the language (there is none), or paying for a non-greedy fold *schedule* search over states whose steps already cost minutes at the ratcheted magnitudes.

Structured n=10 is unaffected and builds through the popcount and merging-chain paths — parity, majority, AND, OR, a 3-input xor-subset and a threshold all build and execute all 1024 rows correctly.

The 3-to-8 mux is the honest edge case, and "a mux builds" overstates it: of the 1680 n=10 spellings (choice of 3 select bits x which data line repeats x MSB/LSB indexing) only **3 build, 0.18%**, all with the selects at positions 6-8/6-9 — that is, read *last*, so the chain merges the data inputs away before the selects arrive.
