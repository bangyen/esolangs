"""Eval's largest Gray-layout lookup, reached by full-support parity."""


def _chars(n: int, _: str) -> int:
    """One-stack through five; the two-stack literal's maximum one-run count."""
    t = 1 << n
    return 2 * t + 7 * n if n < 6 else 7 * t // 4 + 9 * n + 1


def _workspace(n: int, program: str) -> int:
    """Full parity attains the frame, Boolean stacks and active-stack bit."""
    # One-stack lookup peaks at R+n staged cells; dual at R+2n, R<=T.
    # Dual requires R>=8n+4, so it cannot occur when T<8n+4.
    # Constants need at most n+1 cells and never change the active stack.
    length = len(program)
    copies = 1 if (1 << n) < 8 * n + 4 else 2
    return 8 * length + (1 << n) + copies * n + 1 + length.bit_length()


FORMULAS = {
    "scaling": (_chars, True, (4, 6)),
    "workspace": (_workspace, True, (4, 6)),
}
