"""Named witnesses for Pilas resource bounds."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Join the two longest leaf pairs in both orders at each level."""
    first, second = "10", "11"
    for _ in range(n - 1):
        first, second = first + second, second + first
    return (first, "1100" + first[4:]) if n >= 2 else (first,)
