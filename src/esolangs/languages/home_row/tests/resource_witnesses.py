"""Named witnesses for the generated resource bounds."""


# Pairs 01, 10 alternating but for a last 11: every input essential, no two
# adjacent pairs agree, so each is a leaf (size, steps).  Workspace: the
# first pairs 00, so the reversed twin is shorter yet as long as the worst.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    if n < 2:
        return ()
    base = "0110" * ((1 << n) // 4 - 1) + "0111"
    if n == 2:
        return (base,)
    head = 2 * min(4, n - 1)
    return base, "0" * head + base[head:]
