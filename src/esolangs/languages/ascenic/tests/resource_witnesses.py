"""Named witnesses for the generated resource bounds."""


# Size: the alternating table ignores all but its last input, so the
# quadratic witness keeps every input and flips the first pair. Workspace: the
# mirrored scan is chosen for a constant prefix then alternating (prefix 2
# at n = 6, 7; T/8, and T/4 where T/8 stays forward: n = 4).
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    execution = (
        ("10", "1101", "10101000")[n - 1]
        if n <= 3
        else "01" * ((1 << n - 1) - 1) + "00"
    )
    return (
        execution,
        ("11" if n % 2 == 0 else "10") + "01" * ((1 << n - 1) - 1),
        # AND takes the mirror at every n, whose wider Horner value is the bound.
        "0" * ((1 << n) - 1) + "1",
        *(
            "0" * p + ("01" * (1 << n))[: (1 << n) - p]
            for p in (2, *((1 << n - 3, 1 << n - 2) if n >= 3 else ()))
        ),
    )
