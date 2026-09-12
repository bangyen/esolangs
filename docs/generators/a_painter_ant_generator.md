# A Painter Ant boolean generator

The generator is valid only when its program reaches the same cycle state for
every input row. Keep these invariants:

- every leaf has a distinct, separated coordinate;
- the head walk cannot target a different leaf;
- magnitude collapse finishes before the fixed cycle-2 dance;
- the final dance is paint-free and input-independent.

Tests cover the constructed arities; extending arity requires checking both
rendered output and cycle stability, not merely source size.
