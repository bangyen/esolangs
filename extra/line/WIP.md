# Line: open questions and constraints

Line remains a standalone image-language tool: it has no text format and is not registered as an `esolangs.run` language.

## Boolean generation: measured, not open

Twelve inputs round-trips in 289s at 2.60GiB peak on a 33760x29920 canvas (1.01Gpx, within a rounding of the 33600x29920 projection), all sampled parity rows correct — inside the 2-5 minute projection and *below* the 4-8GiB one.

The cost is the reader.

**Measure one arity per process.** Running n=11 and n=12 in one process gave 268s and 642s — 3.1x and 2.2x the true figures, with `compile` inflated 10x at n=11 (105s against 10.1s).

## Open work

- Validate extraction on genuine anti-aliased camera or scan input.
- Derive the lattice probe length from `UNIT` before supporting smaller grid units.
- Define behavior for genuinely ambiguous arrowheads rather than choosing the larger candidate.

## Do not regress

- Keep opcode geometries distinct and retain the two-pixel extraction coverage threshold.
- Construct loop returns from reserved geometry.
- Keep PNG-only input unless full image-format support is deliberately added.
- Do not add an arbitrary step limit to simulation; use semantic cycle detection if that capability is ever needed.
- Preserve the hand-decoded multiplication fixture behavior exercised by the Line tests.
