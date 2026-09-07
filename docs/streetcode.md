# Streetcode interpretation

The interpreter follows the road graph, car heading, and junction rules in
`src/esolangs/interpreters/grid_based/streetcode.py`. Its validator rejects
ink that cannot belong to a reachable road or bounding wall.

Keep the following distinctions intact: a junction is a runtime road choice,
not a compile-time branch; merge state records the pending turn rather than a
heading; and lane/ring optimizations rely on their documented entry geometry.
Four-way junctions and post-corner behavior remain the reference semantics to
pin before any general control-flow lowering.
