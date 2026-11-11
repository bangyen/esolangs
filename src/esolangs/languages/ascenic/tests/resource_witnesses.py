"""Named witnesses for the generated resource bounds."""


# Size and steps: the alternating table ignores all but its last input, so
# the worst keeps every input and flips the first pair.  Workspace: the
# mirrored scan is chosen for a constant prefix then alternating (prefix 2
# at n = 6, 7; T/8, and T/4 where T/8 stays forward: n = 4).
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (
        ("11" if n % 2 == 0 else "10") + "01" * ((1 << n - 1) - 1),
        # AND takes the mirror at every n, whose wider Horner value is the bound.
        "0" * ((1 << n) - 1) + "1",
        *(
            "0" * p + ("01" * (1 << n))[: (1 << n) - p]
            for p in (2, *((1 << n - 3, 1 << n - 2) if n >= 3 else ()))
        ),
    )
