"""Line workspace witnesses for the default layout."""

from random import Random


def resource_tables(n: int) -> tuple[str, ...]:
    """Retain the loaded tree at small arity and the inline tree above it."""
    small = (
        "11",
        "1110",
        "11111001",
        "1111010010111110",
        "11100110001111100101010001000110",
    )
    if n <= len(small):
        return (small[n - 1],)
    rows = 1 << n
    if n <= 14:
        return (f"{Random(1).getrandbits(rows):0{rows}b}",)
    width = 1 << (n - 1).bit_length()
    count = rows // (4 * width)
    words = [f"{i:0{width}b}" for i in range(count)]
    first = "".join(word + word for word in words)
    second = "".join(word + words[(i + 1) % count] for i, word in enumerate(words))
    return (first + second,)
