"""Nandypants execution witnesses."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Return a table attaining the command maximum."""
    if n <= 3:
        return (("10", "1001", "11010001")[n - 1],)
    repeat = "10" * (1 << (n - 3))
    peer = "11" + repeat[2:]
    return (peer + repeat + "0" * len(repeat) + repeat,)
