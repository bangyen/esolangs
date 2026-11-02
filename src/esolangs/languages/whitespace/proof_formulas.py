"""Power-accumulator command and written-snapshot maxima."""


def execution(n: int, _program: str) -> int:
    """One inline step, or n calls each executing mark, nine steps and return."""
    return 16 if n == 1 else 12 * n + 7


def workspace(n: int, _program: str) -> int:
    """The full-essential, top-bit-one table and all-one row attain the bound."""
    # U=2**m: stack peaks at 3U-2, heap at 2U-2, plus one halt bit.
    # PC peaks at n+17, the return address at n+2, IO at 2n-1.
    # q ignored reads add at most two heap bits and q to each code cursor.
    # 5*(2**n-U) >= 2q+2 dominates that cost. One essential input instead
    # needs <=10+bl(2n+14)+bl(2n-1) bits; constants also stay below this.
    if n == 1:
        return 14
    return (
        5 * (1 << n)
        - 3
        + (n + 17).bit_length()
        + (n + 2).bit_length()
        + (2 * n - 1).bit_length()
    )
