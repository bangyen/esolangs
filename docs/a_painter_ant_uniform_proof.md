# A Painter Ant generator: uniform correctness

For every input count, the construction maps each truth-table row to a unique
leaf, walks to that leaf, collapses its magnitude, and enters one paint-free
cycle-2 state.

The proof depends on four facts: leaf coordinates are distinct and separated;
a head walk cannot reach a sibling leaf; collapse cannot alter the selected
verdict; and the final dance preserves the grid. The implementation and tests
are the authoritative executable counterpart.

Each fact is a lemma in `tests/tools/apa_uniform_proof_check.py`, run by
`just apa-proof`. It is 5m40s and deliberately outside `just test` and CI,
so run it by hand when the head, body, or routing changes -- that is what
invalidates the motif table the last two lemmas replay.
