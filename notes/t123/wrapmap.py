r"""Check whether a segment position map is genuinely pass-dependent.

A sweep of wrap-crossing guards found nothing, but per the liveness rule a zero means
little until the intended mechanism is confirmed present.  The mechanism
here is that the segment's pointer map must differ between pass one and
pass two -- which happens only if one pass crosses the ``-4 -> 0`` wrap and
the other does not.

This computes the map directly: for a segment of ``1``/``2`` characters and
each possible entry position, where does the pointer end up, and is the map
a plain translation over the range the guard actually uses?
"""

from gen import _Sim


def endpoint(seg, start):
    """Return the pointer position after running ``seg`` from ``start``."""
    m = _Sim()
    m.pos = start
    for ch in seg:
        m.exec(ch)
        if m.dead:
            return None
    return m.pos


def main():
    """Tabulate the position map for candidate segments."""
    for seg in ("1111", "11111", "111111", "1111111"):
        print(f"segment {seg!r}")
        pairs = []
        for start in range(-3, 10):
            end = endpoint(seg, start)
            pairs.append((start, end))
        print(f"  map {pairs}")
        # a translation has a constant difference wherever it is defined
        diffs = {e - s for s, e in pairs if e is not None}
        print(f"  distinct displacements: {sorted(diffs)}")
        print(f"  pass-dependent: {len(diffs) > 1}\n")


if __name__ == "__main__":
    main()
