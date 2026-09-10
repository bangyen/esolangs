# Line: open questions and constraints

Line remains a standalone image-language tool: it has no text format and is
not registered as an `esolangs.run` language. The renderer, extractor,
simulator, and lattice module docstrings are authoritative.

## Boolean generation: measured, not open

Twelve inputs round-trips in 289s at 2.60GiB peak on a 33760x29920 canvas
(1.01Gpx, within a rounding of the 33600x29920 projection), all sampled parity
rows correct — inside the 2-5 minute projection and *below* the 4-8GiB one. The
n=11 control is 85.5s at 2.68GiB. There is no resource wall, so **subtree
sharing and a denser layout stay unpursued**: the condition that would have
justified them was never met, and re-opening them needs new evidence rather
than a new goal.

The cost is the reader. `extract` is 70.4s of 85.5s at n=11 and 237.6s of
288.8s at n=12 — a steady 82% — while drawing and saving the canvas is 4% and
`compile` 12-13%. `compile` scales cleanly at 4x per arity (0.16 / 0.62 / 2.48
/ 10.1 / 38.0s for n=8..12), so it is predictable and small; `extract` is the
stage any future work belongs in. Re-measured at the cheap end: n=8 compiles in
0.15s with `extract` 86% of a 6.32s round trip, n=9 in 0.59s with `extract` 88%
of 12.96s, every row correct at both.

**Measure one arity per process.** Running n=11 and n=12 in one process gave
268s and 642s — 3.1x and 2.2x the true figures, with `compile` inflated 10x at
n=11 (105s against 10.1s). Nothing is cached between calls, so this is not
warm-up: a repeated `compile_program` on one stroke is flat to the millisecond,
and repeated `extract` likewise. It is the billion-pixel canvas still resident
while the next arity is measured.

## Open work

- Validate extraction on genuine anti-aliased camera or scan input.
- Derive the lattice probe length from `UNIT` before supporting smaller grid
  units.
- Define behavior for genuinely ambiguous arrowheads rather than choosing the
  larger candidate.

## Do not regress

- Keep opcode geometries distinct and retain the two-pixel extraction coverage
  threshold.
- Construct loop returns from reserved geometry. Do not restore global
  search-based routing; nested returns enclose its corridors.
- Keep PNG-only input unless full image-format support is deliberately added.
- Do not add an arbitrary step limit to simulation; use semantic cycle
  detection if that capability is ever needed.
- Preserve the hand-decoded multiplication fixture behavior exercised by the
  Line tests.
