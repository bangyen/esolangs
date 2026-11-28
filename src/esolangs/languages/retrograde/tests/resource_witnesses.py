"""Named witnesses for Retrograde workspace."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Preserve a full branch at each new level and reverse on row zero."""
    if n == 1:
        return ("10",)
    first, second = "1110", "1011"
    for _ in range(n - 2):
        first, second = first + second, second + first
    return (first,)
