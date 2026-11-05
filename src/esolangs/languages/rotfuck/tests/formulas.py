"""ROTfuck source maxima from phased Horner and walk stencils."""


def _walk_chars(stride: int) -> int:
    """Inner4s+8 and outside(4s+16(1+[log2s even]))/3, plus opener."""
    even = (stride.bit_length() - 1) % 2 == 0
    return 4 * stride + 9 + (4 * stride + 16 * (1 + even)) // 3


def _chars(n: int, _: str) -> int:
    """A lone zero maximizes the strip; every emitted prefix has this size."""
    raw = n >= 7
    radix = 5 if raw else 6
    widths = ([n % radix] if n % radix else []) + [radix] * (n // radix)
    length = 3 * (1 << n) - 2 + 50
    shift = 0
    for width in widths:
        length += (1 if raw else 49) + (31 if raw else 79) * (width - 1)
        if raw:
            back = -48 * ((1 << width) - 1) % 256
            length += min(back, 256 - back)
        length += _walk_chars(2 << shift)
        shift += width
    return length
