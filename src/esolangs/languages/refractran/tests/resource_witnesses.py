"""Named witnesses for REFRACTRAN resource maxima."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Return the smallest-arity maximizers from the exhaustive sweep."""
    return {
        1: ("01",),
        2: ("0111", "1101"),
        3: ("10110111",),
        4: ("1101101110010111", "1110110111001011"),
    }.get(n, ())
