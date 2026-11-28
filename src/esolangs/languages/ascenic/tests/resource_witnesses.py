"""Named witnesses for the generated resource bounds."""


# Workspace: the
# mirrored scan is chosen for a constant prefix then alternating (prefix 2
# at n = 6, 7; T/8, and T/4 where T/8 stays forward: n = 4).
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    execution = (
        ("10", "1101", "10101000")[n - 1]
        if n <= 3
        else "01" * ((1 << n - 1) - 1) + "00"
    )
    rows = 1 << n
    if n <= 3:
        size = ("10", "1101", "10101011")[n - 1]
    else:
        # At odd arity, the two nearest missing indices tie. Use the even
        # one so the change of phase retains every input.
        missing = 2 * ((rows + 3 * n + 11) // 4) if n % 2 else 0
        size = "".join(str(1 ^ (row % 2) ^ (row > missing)) for row in range(rows))
    return (
        execution,
        size,
        ("11" if n % 2 == 0 else "10") + "01" * ((1 << n - 1) - 1),
        # AND takes the mirror at every n, whose wider Horner value is the bound.
        "0" * ((1 << n) - 1) + "1",
        *(
            "0" * p + ("01" * (1 << n))[: (1 << n) - p]
            for p in (2, *((1 << n - 3, 1 << n - 2) if n >= 3 else ()))
        ),
    )
