"""Executed command and snapshot-bit bounds."""


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Identify the direct constant program."""
    return {"C": int(program.startswith("Package : IO {\n  Char c;\n"))}


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
