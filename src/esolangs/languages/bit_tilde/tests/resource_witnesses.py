"""Named witnesses for the generated resource bounds."""


# Every pair differs and half the pairs start with a one: all the planted
# cells the minority rule leaves, in a table that is not affine.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (
        "".join(
            f"{e}{1 - e}"
            for e in (
                [1] * (2 ** (n - 2) - 1) + [0, 1] + [0] * (2 ** (n - 2) - 1)
                if n >= 2
                else [1]
            )
        ),
    )
