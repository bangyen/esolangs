"""Named witnesses for the generated resource bounds."""

from itertools import permutations


# 1 xor parity, the last input ignored at even n: the longest loop sums.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    if n == 4:
        blocks = (f"{value:04b}" for value in range(1, 15))
        banks = tuple(a + b + b + a for a, b in permutations(blocks, 2))
    else:
        banks = ()
    return (
        *banks,
        *(("1011",) if n == 2 else ("11101001",) if n == 3 else ()),
        "".join(str((1 + (r >> 1 - n % 2).bit_count()) % 2) for r in range(1 << n)),
    )
