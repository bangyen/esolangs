"""Semantic workspace bounds for the straight default lookup."""


def workspace(n: int, program: str) -> int:
    """Bound one flat walker, n input numbers and its result; exact when all matter."""
    # Each one-character name costs 8 bits; an ASCII-bit rational costs 6+1.
    # The result has the same cost. Row/heading cost 3, halt 1, column
    # reaches L-4, and both input cursors reach n. No list or pending AST
    # survives a command. After 25 inputs, a0, a1, ... add their digit bytes.
    extra_names = 8 * sum(len(str(index)) for index in range(max(0, n - 25)))
    return (
        15 * n + 19 + extra_names + (len(program) - 4).bit_length() + 2 * n.bit_length()
    )
