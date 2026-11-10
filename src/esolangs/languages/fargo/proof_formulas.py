"""Executed command bounds."""


def workspace(_n: int, program: str) -> int:
    """Bound the false literal and the retained evaluation frames."""
    # Typed `$` writes 11 bits; retain the established 18-bit ceiling.
    # Input number and input cursor stay read-only; n=1,3,6,8,12 executed.
    if program == "$":
        return 18
    length = len(program)
    return 16 * (length - 3) + length.bit_length() + 11
