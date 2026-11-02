"""Constant paths and Church-pair envelopes, also bounding majority identities."""


def execution(n: int, program: str) -> int:
    """Four rewrites per input for constants; otherwise the pair-tree bound."""
    if program.startswith("A0"):
        return 4 * n + 3
    # [ablations.majority_pair_rule]: each replacement takes fewer rewrites.
    # The unchanged non-majority witnesses still attain the envelope.
    return 35 * n + 45


def workspace(n: int, program: str) -> int:
    """Constant spine characters, pending bit, output flags and input cursor."""
    if program.startswith("A0"):
        return 32 * n + 27 + n.bit_length()
    # The shorter bottom terms duplicate only literal bits; their local
    # snapshot peaks are below the replaced pairs, with the same context.
    t = 1 << n
    return max(88 * t + 232 * n + 235, 132 * t + 24 * n - 53) + n.bit_length()
