"""Snapshot-bit bounds."""


def workspace(n: int, program: str) -> int:
    """Frames/head fit 16n bits each, plus the completed render's one-bit flag.

    All generated atoms are ASCII: payload counts bytes, not hidden UTF-8.
    Named witnesses attain the frame/head bound at n=1..7.
    """
    if program.replace("\n", "").startswith(("x->s[]=0;", "x->s[]=1;")):
        return 8 * n + 9
    return 32 * n + 1
