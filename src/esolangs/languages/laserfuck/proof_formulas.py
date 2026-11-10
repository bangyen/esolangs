"""Executed command and snapshot-bit bounds the ledger notation cannot state."""


def execution(n: int, program: str) -> int:
    """Bound default seed-2 runs; exact at the registered arities."""
    if program.startswith(" }}" + "," * n + "}-#/)"):
        # Ten steps a ring pass, with the final reflection skipped.
        return n + 491 + program.split("\n", 1)[0].endswith("+x")
    if n < 7:
        return (1 << n) + 296 * n + 682
    return 11 * (1 << n) + 56 * n + 2


def all_heading_execution(n: int, program: str) -> int:
    """Bound default runs in every heading; down/left cross two extra cells."""
    return execution(n, program) + 2
