r"""Check whether a row exit is decided by step count alone.

The obstruction found so far is empirical: no layout in the families swept
both terminates and diverges.  The geometry suggests a reason that would
make it general rather than family-specific.

Pointer motion in ``1``/``2`` does not read the tape, so after a fixed
string of moves the pointer position is a function of the *starting*
position and the move string only.  Two rows that enter a segment at the
same position therefore leave it at the same position, whatever their bits.
The closing ``3`` halts a row exactly when it is reached at ``pos < 0``, so
if the rows share an entry position they share an exit verdict -- all halt
or none do -- and a guard cannot both diverge in pass count and have some
rows exit while others loop.

The escape is for the rows to enter the segment at *different* positions,
which needs a setter whose two instantiations displace the pointer
differently -- the +-1 setter, not the neutral pair.  But that setter is
exactly the one whose spread analysis showed rows drifting apart by bit
count, never converging to print together.

This checks the first half directly: do same-entry rows always share an
exit verdict?
"""


from gen import _Sim


def exit_pos(seg, start):
    """Position after running ``seg`` from ``start``; None if it reads."""
    m = _Sim()
    m.pos = start
    for ch in seg:
        m.exec(ch)
        if m.dead:
            return None
    return m.pos


def main():
    """Confirm the position map ignores the tape, then state the corollary."""
    print("--- does the position map depend on tape contents? ---")
    segs = ["1111", "1212", "2121", "11211", "12112"]
    for seg in segs:
        results = []
        for preset in ([], [0], [3], [0, 3, 7]):
            m = _Sim()
            for cell in preset:
                m.bits[cell] = True
            m.pos = 5
            for ch in seg:
                m.exec(ch)
            results.append(m.pos)
        same = len(set(results)) == 1
        print(f"  {seg!r:8} from pos 5 with varied tapes -> {results} "
              f"identical={same}")

    print("\n--- so rows entering together leave together ---")
    print("  the closing 3 halts a row iff reached at pos < 0,")
    print("  hence same entry position => same halt verdict for all rows.")
    print("  Divergent pass counts need divergent entry positions,")
    print("  which needs the +-1 setter -- whose rows never reconverge.")


if __name__ == "__main__":
    main()
