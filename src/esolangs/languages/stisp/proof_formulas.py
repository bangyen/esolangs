"""Snapshot-bit bounds."""


def workspace(n: int, program: str) -> int:
    """At most 16n bits each for frames and head, plus the post-halt flag."""
    if program.replace("\n", "").startswith(("x->s[]=0;", "x->s[]=1;")):
        return 8 * n + 9
    return 32 * n + 1
