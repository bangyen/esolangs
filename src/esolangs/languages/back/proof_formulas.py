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


def workspace(n: int, program: str) -> int:
    """Global bit envelope including halt/dump flags, attained at n=3/6.

    Default area is below 16T from n=6, so beam-counter bit widths sum to at most
    n+5, within the old envelope. Small loaders cross no old bit threshold.
    """
    if _constant(n, program):
        bit = program.endswith("-*")
        return n + 3 + (3 * n + bit).bit_length() + n.bit_length()
    return (
        n
        + 7
        + max(6 * n - 2, (1 << n) - 1).bit_length()
        + (3 * n + 4).bit_length()
        + n.bit_length()
    )
