"""Default pair-tree execution caps and the preserved global workspace bound."""


def _constant(n: int, program: str) -> bool:
    """Whether ``program`` is the compact constant build.

    The complete compact template distinguishes it from mirrored nonconstant
    and width layouts; a first-character test confuses their loader primers.
    """
    return program == "$-" * n + ">" * n + ("-*" if program.endswith("-*") else "*")


def execution(n: int, program: str) -> int:
    """Exact through n=9; the original global envelope remains above that.

    Pair leaves cap the comb at T/2 rows. At n=8/9 the folded-area comparison
    restricts selected combs to 114/218 rows; owned geometric witnesses attain it.
    """
    if _constant(n, program):
        return 3 * n + 2 + program.endswith("-*")
    if n < 3:
        return 13 if n == 1 else 27
    if n <= 7:
        pairs = 1 << (n - 1)
        return max(pairs, 6 * n + 1) + pairs + 3 * n + 6
    if n in (8, 9):
        # Fold area limits a selected full-width comb to 114/218 rows.
        return 258 if n == 8 else 469
    return max(3 * (1 << n) // 4 + 1, 6 * n - 1) + 3 * (1 << n) // 4 + 1 + 3 * n + 6


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Identify the compact constant and its value."""
    return {"C": int(_constant(n, program)), "B": int(program.endswith("-*"))}
