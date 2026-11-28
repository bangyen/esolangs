"""Witnesses for Brainfuck's exact resource bounds."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Reach the repeated nonzero branch after the leading zero row."""
    size = ("10", "1001", "10010111", "1110100110000110")
    extra = (size[n - 1],) if 1 <= n <= len(size) else ()
    previous = ("0" + "1" * ((1 << n) - 1),) if n >= 3 else ()
    return (*previous, *extra)
