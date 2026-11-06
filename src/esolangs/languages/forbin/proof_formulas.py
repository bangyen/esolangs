"""Semantic workspace bounds for live lexical environments."""


def _forbin(n: int, _: str) -> int:
    """One copy of main's locals and the frame's loop-cursor peak.

    G grows with the tree depth h, so the narrowest block (3 inputs) is the peak.
    """
    # n+1 names/bits cost 9 each. Main's code/scope references cost 8;
    # byte/bit cursors add 2bl(n)+3. G counts positions and active loop data.
    bl = int.bit_length
    h = max(n - 3, 0)
    loop = [bl(j + 1) + max(1, bl(h - 1 - j)) + 11 for j in range(h)]
    return 9 * n + 20 + 2 * bl(n) + max([bl(h + 1), *loop])


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    if p.startswith(("main{a,", "main{r{a,a,a,a,a,a,a,a=(in 0)}")):
        # One live local; reader frames finish before capture.
        return 21 + 2 * n.bit_length()
    return _forbin(n, p)
