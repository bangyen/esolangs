"""Named witnesses for the generated resource bounds."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional cases in the order used for resource measurement."""
    tables: tuple[str, ...] = ()
    if n == 6:
        # 322 commands: shared names run their bodies per reference, past 5T + 1.
        tables += ("1000001000110001000001001111000100000100010100000110010000011000",)
    return tables
