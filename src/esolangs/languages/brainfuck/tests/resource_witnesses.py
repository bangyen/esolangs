"""Witnesses for Brainfuck's exact resource bounds."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Reach the repeated nonzero branch after the leading zero row."""
    return ("0" + "1" * ((1 << n) - 1),) if n >= 3 else ()
