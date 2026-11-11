"""Snapshot-bit bounds."""


# Atomic muxes use three slots instead of six (four with a root NOT);
# prefix definitions are not outer-machine state. Primitive copied pools
# retain their geometry and slots. Balanced pools admit atomic leaves only
# when their expanded primitive count stays <= T+n. Latches never clear: 3T - 6 + n flat
# slots, 6T - 10 + n under the
# H-layout. Same-state pulses are an antichain: T/2 + n flat, T + n after.
def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Identify the direct port route with no intermediate pool."""
    return {"C": int(program in ("-\n" * n + "(-:", "-\n" * n + ")-:"))}
