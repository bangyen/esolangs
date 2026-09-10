# Line: open questions and constraints

Line remains a standalone image-language tool: it has no text format and is
not registered as an `esolangs.run` language. The renderer, extractor,
simulator, and lattice module docstrings are authoritative.

Boolean-generation limits are measured, not open: twelve inputs round-trips
in 289s at 2.60GiB on a 1.01Gpx canvas, all sampled parity rows correct.
`docs/roadmap.md` carries that entry and the per-arity costs.

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
