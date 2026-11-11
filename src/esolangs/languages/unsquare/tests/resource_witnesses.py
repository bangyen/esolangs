"""Named witnesses for the generated resource bounds."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional cases in the order used for resource measurement."""
    width = 1 << n
    tables: tuple[str, ...] = ()
    if n >= 8:
        # One leaf of 12- and 14-cell runs (12a + 14b = S, 3 a cell); the
        # others alternate, so every input stays essential.
        leaf = 2 ** (n - max(0, (n - 3) // 2))
        b = (leaf // 2) % 6
        a = (leaf // 2 - 7 * b) // 6
        runs = [*[12] * a, *[14] * b]
        head = "".join(str(i % 2) * c for i, c in enumerate(runs))
        tables += (head + "01" * (leaf // 2) * (width // leaf - 1),)
    return tables
