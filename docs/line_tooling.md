# Line renderer and extractor

The renderer, extractor, simulator, and lattice modules contain the current
implementation rationale. Preserve these constraints:

- raster coverage needs one-pixel clearance; loosening it creates false
  junctions rather than useful compactness;
- loop returns are constructed from measured extent, not globally searched;
  free-form routing encloses its own departure corridor at depth;
- extent caches are per render because geometry depends on the rendered tree.

Use the Line tests for any geometry change; visual plausibility is not evidence
that a drawing still extracts or simulates correctly.
