"""Named witnesses for the generated resource bounds."""


# 1 xor parity, the last input ignored at even n: the longest loop sums.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (
        *(("11101001",) if n == 3 else ()),
        "".join(str((1 + (r >> 1 - n % 2).bit_count()) % 2) for r in range(1 << n)),
    )
