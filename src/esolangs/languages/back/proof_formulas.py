"""Default pair-tree execution caps and the preserved global workspace bound."""


def _constant(n: int, program: str) -> bool:
    """Whether ``program`` is the compact constant build.

    The complete compact template distinguishes it from mirrored nonconstant
    and width layouts; a first-character test confuses their loader primers.
    """
    return program == "$-" * n + ">" * n + ("-*" if program.endswith("-*") else "*")


def layout_terms(n: int, program: str) -> dict[str, int]:
    """Identify the compact constant and its value."""
    return {"C": int(_constant(n, program)), "B": int(program.endswith("-*"))}
