"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program.

    A wide level costs at most 60 commands, on its one arm: ``>+,`` 3,
    48 ``-``, ``[<-`` 3, ``>]`` 2, the retested ``[`` 1, then the skipped zero
    arm's ``<[`` and the closing ``<`` 3 (59 on a zero arm).  The worst
    seven-input block runs 894, 895 with its trailing ``<``.
    """
    return 60 * (n - 7) + 895


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program.

    Past seven inputs the root level is a zero arm (its sentinel is popped,
    so the stack peaks at ``n + 6``) or a one arm (its loop opens at position
    51, at most six bits against ``bl(L)`` >= 10): never both at full width.
    """
    bl = int.bit_length
    return (
        n
        + 6
        + (n < 8)
        + bl(n)
        + (max(n - 7, 0) + (3 * min(1 << n, 128) + 1) // 5 + 3) * bl(len(p))
    )
