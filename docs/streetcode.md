# Streetcode interpretation

The interpreter follows the road graph, car heading, and junction rules in
`src/esolangs/interpreters/grid_based/streetcode.py`. Its validator rejects
ink that cannot belong to a reachable road or bounding wall.

Keep the following distinctions intact: a junction is a runtime road choice,
not a compile-time branch; merge state records the pending turn rather than a
heading; and lane/ring optimizations rely on their documented entry geometry.
Four-way junction behavior is pinned to the implementation rather than to a
confirmed trace, and the wiki cannot settle it — neither junction-bearing
example contains a four-way at any cell or heading, and the page's rule names
only a leftmost and a second-leftmost road. It is a convention; see
[limitations](limitations.md).
Post-corner behavior is not open — the car cornering into a mouth it never met
head-on is the most exercised of `_road_mouth`'s three near depths.
