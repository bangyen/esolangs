"""Named witnesses for the generated resource bounds."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional cases in the order used for resource measurement."""
    width = 1 << n
    tables: tuple[str, ...] = ()
    if n >= 3:
        # The most zeros a 128-row fill block may punch, in every block;
        # zeros are isolated, since a run of ones would be a shorter loop.
        block = min(width, 128)
        zeros = (block - 4) // 2
        tail = block - 2 * (zeros - 1)
        # The odd tail zero keeps every input essential.
        head = "10" * (zeros - 1) + "11" + "0" + "1" * (tail - 3)
        # Swap pair j of 16-row block j, so no two blocks are equal: equal
        # ones alias at a smaller block (n=7: 311 steps, not 1205).
        cells = list(head)
        for j in range(block // 16 - 1):
            at = 16 * j + 2 * j % 16
            cells[at], cells[at + 1] = cells[at + 1], cells[at]
        tables += ("".join(cells) * (width // block),)
    return tables
