# A Painter Ant generator: uniform correctness

For every input count, the construction maps each truth-table row to a unique
leaf, walks to that leaf, collapses its magnitude, and enters one paint-free
cycle-2 state.

The proof depends on four facts: leaf coordinates are distinct and separated;
a head walk cannot reach a sibling leaf; collapse cannot alter the selected
verdict; and the final dance preserves the grid. The implementation and tests
are the authoritative executable counterpart.
