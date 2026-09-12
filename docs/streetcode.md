# Streetcode interpretation

The spec of record.  `src/esolangs/interpreters/grid_based/streetcode.py`
holds the road graph, car heading and junction rules; its validator rejects
ink that cannot belong to a reachable road or bounding wall.

Keep these distinctions intact:

- a junction is a runtime road choice, not a compile-time branch;
- merge state records the pending turn, not a heading;
- lane and ring optimizations rely on their documented entry geometry.

**The four-way junction is a convention.**  It is pinned to the
implementation rather than to a confirmed trace, and the wiki cannot settle
it: neither junction-bearing example contains a four-way at any cell or
heading, and the page's rule names only a leftmost and a second-leftmost
road.  See [limitations](limitations.md) for the scan behind that.

Post-corner behaviour is *not* open -- the car cornering into a mouth it
never met head-on is the most exercised of `_road_mouth`'s three near
depths.
