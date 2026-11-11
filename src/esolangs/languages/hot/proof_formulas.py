"""Constant paths and Church-pair envelopes, also bounding majority identities."""


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Mark the constant spine; the majority replacement stays below the tree bound."""
    return {"C": int(program.startswith("A0"))}


def workspace(n: int, program: str) -> int:
    """Constant spine characters, pending bit, output flags and input cursor."""
    if program.startswith("A0"):
        return 32 * n + 27 + n.bit_length()
    # The shorter bottom terms duplicate only literal bits; their local
    # snapshot peaks are below the replaced pairs, with the same context.
    t = 1 << n
    return max(88 * t + 232 * n + 235, 132 * t + 24 * n - 53) + n.bit_length()
