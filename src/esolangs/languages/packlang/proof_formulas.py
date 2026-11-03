"""Executed command and snapshot-bit bounds."""


def execution(n: int, program: str) -> int:
    """The previous painting ceiling minus its removed final VALUE command."""
    if program.startswith("Package : IO {\n  Char c;\n"):
        return n + 2
    if n <= 7:
        return 19 * (1 << n) // 2 - n - 5
    return 3 * (1 << n) // 64 + 1205 - n


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    if p.startswith("Package : IO {\n  Char c;\n"):
        # Package/function names, c and its byte, frame cursor, two read cursors.
        return 159 + (n + 1).bit_length() + 2 * n.bit_length()
    bl = int.bit_length
    return (
        min(1 << n, 128)
        + 2 * n
        + min(n, 7)
        + 192
        + 16 * (n > 7)
        + bl(len(p))
        + 2 * bl(n)
    )
