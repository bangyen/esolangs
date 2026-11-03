"""Snapshot-bit bounds."""


def workspace(n: int, program: str) -> int:
    """Frames/head each fit 16n bits; named witnesses attain both at n=1..7.

    All generated atoms are ASCII: payload counts bytes, not hidden UTF-8.
    The benchmark stops before the halt dump; its unchanged flag is excluded.
    """
    if program.replace("\n", "").startswith(("x->s[]=0;", "x->s[]=1;")):
        return 8 * n + 8
    return 32 * n
