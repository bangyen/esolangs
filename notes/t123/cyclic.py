r"""Why the wrap gives a pass-dependent map but still no exit.

``wrapmap.py`` confirms the maps are genuinely pass-dependent -- ``1111``
sends 5 to 1 and 1 to -3 -- so ``wrapexit.py``'s zero is not a dead-code
artifact.  The obstruction is visible in the same table.

Below location 0 the pointer moves only left, and the ``-4 -> 0`` wrap
returns it to 0, so the four positions ``0, -1, -2, -3`` form a **cycle**
under ``1``.  A row that drops into that region does not escape it by
running the segment again: it walks round the cycle.  So the closing ``3``
alternates between NOP (``pos < 0``) and test (``pos == 0``) with period 4,
and a guard whose exit depends on reaching ``pos < 0`` reaches it on some
passes and leaves it on others -- the oscillation ``twomodes.py`` traced,
now explained by the geometry rather than by the guard cell.

Escaping the cycle needs a ``2``, which moves right; but a ``2`` at -3 is a
read, and a ``2`` at -2 prints.  So the only exits from the negative region
are the two IO positions, which is why a terminating divergent guard has
not been found.
"""

from gen import _Sim


def orbit(start, steps=10):
    """Return the positions visited by successive ``1`` moves."""
    m = _Sim()
    m.pos = start
    seen = [m.pos]
    for _ in range(steps):
        m.exec("1")
        seen.append(m.pos)
    return seen


def main():
    """Show the negative-region cycle and its only exits."""
    print("successive '1' moves from each negative position:")
    for start in (0, -1, -2, -3):
        print(f"  from {start:3}: {orbit(start, 8)}")

    print("\nthe only rightward move is '2', and in the negative region:")
    print("  pos -3: '2' reads stdin  (fatal for a parameterized program)")
    print("  pos -2: '2' prints       (the endgame, one shot)")
    print("  pos -1: '2' steps to 0   (the sole free exit)")

    m = _Sim()
    m.pos = -1
    m.exec("2")
    print(f"\n  checked: '2' at -1 lands at {m.pos}, printed {m.out}")


if __name__ == "__main__":
    main()
