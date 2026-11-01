"""Direct constants and the unchanged packed-literal envelopes."""


def execution(n: int, program: str) -> int:
    """A constant reads n times then prints; a lookup adds five statements."""
    return n + (1 if program.startswith("we e we et we") else 6)


def workspace(n: int, program: str) -> int:
    """Constants store one six-bit byte, its key and two cursors."""
    if program.startswith("we e we et we"):
        return 7 + (n + 1).bit_length() + n.bit_length()
    return 2 * (1 << n) + 19 + n.bit_length()
